"""Decides whether a job matches criteria.yaml.

Each check either rejects the job or lets it through, possibly with a note
(e.g. "pay not listed") so the email shows what couldn't be confirmed.
"""
import re
from dataclasses import dataclass, field

from .models import Job

CONTRACT_TYPES = ("contract", "contractor", "temporary", "temp", "part", "intern", "freelance")

CONTRACT_TEXT = re.compile(
    r"\b("
    r"c2c|corp[- ]to[- ]corp|1099|w-?2 contract|"
    r"contract[- ]to[- ]hire|contract to perm|"
    r"(this is an? )?\d+[- ]?(month|mo)\s+contract|"
    r"contract (position|role|opportunity|assignment)|"
    r"duration:\s*\d+\s*(months?|weeks?)"
    r")\b",
    re.IGNORECASE,
)

HYBRID_TEXT = re.compile(r"\bhybrid\b", re.IGNORECASE)
REMOTE_TEXT = re.compile(r"\b(fully remote|100% remote|remote)\b", re.IGNORECASE)

# Staffing firms that post the same opening on every board, often for jobs
# that are contract or don't exist yet. Matched as whole words in the company name.
STAFFING_AGENCIES = (
    "robert half", "teksystems", "insight global", "randstad", "kforce",
    "apex systems", "motion recruitment", "jobot", "cybercoders", "hays",
    "aerotek", "collabera", "beacon hill", "addison group", "kelly services",
    "manpower", "experis", "adecco", "modis", "akkodis", "vaco", "lhh",
    "creative circle", "harnham", "mondo", "talentbridge", "diverse lynx",
    "cynet systems", "mindlance", "judge group", "system one",
    "staffing", "recruiting", "recruitment", "talent solutions",
)
AGENCY_NAME = re.compile(r"\b(" + "|".join(map(re.escape, STAFFING_AGENCIES)) + r")\b", re.IGNORECASE)
RECRUITER_TEXT = re.compile(
    r"\b("
    r"(on behalf of|for) (our|a) (client|customer)|"
    r"our (client|customer),? (is|a|an)|"
    r"(client|customer) of ours|"
    r"a (leading|large|fortune \d+|well[- ]known) (client|company|organization) (is|in)|"
    r"confidential (client|company|employer)"
    r")\b",
    re.IGNORECASE,
)
NO_COMPANY = re.compile(r"^(confidential|undisclosed|private|hiring now|n/?a|unknown)?$", re.IGNORECASE)

# Remote jobs restricted to somewhere other than the US.
FOREIGN_ONLY = re.compile(
    r"\b(uk|united kingdom|europe|emea|eu|canada|india|latam|latin america|apac|"
    r"australia|germany|poland|philippines|mexico|brazil)\b( only)?",
    re.IGNORECASE,
)
US_TEXT = re.compile(r"\b(us|usa|u\.s\.|united states|north america|americas|worldwide|anywhere)\b",
                     re.IGNORECASE)

# "$120,000 - $150,000", "$120K to $150K", "$120k–150k". Single figures are
# skipped: they're as often a bonus or a stipend as a salary.
_NUMBER = r"(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])"
SALARY_RANGE = re.compile(r"\$\s?" + _NUMBER + r"(?:\.\d\d)?\s*(?:-|–|—|to)\s*\$?\s?" + _NUMBER)


@dataclass
class Verdict:
    keep: bool
    reason: str = ""
    notes: list[str] = field(default_factory=list)


def _amount(text: str) -> float:
    text = text.replace(",", "").replace(" ", "")
    if text[-1] in "kK":
        return float(text[:-1]) * 1000
    return float(text)


def salary_from_text(text: str) -> tuple[float, float] | None:
    for match in SALARY_RANGE.finditer(text):
        lo, hi = _amount(match.group(1)), _amount(match.group(2))
        if 30_000 <= lo <= hi <= 1_000_000:
            return lo, hi
    return None


def guess_work_mode(text: str) -> str:
    if HYBRID_TEXT.search(text):
        return "hybrid"
    if REMOTE_TEXT.search(text):
        return "remote"
    return "unknown"


def is_recruiter(job: Job) -> bool:
    return bool(AGENCY_NAME.search(job.company) or RECRUITER_TEXT.search(job.description))


def evaluate(job: Job, criteria: dict) -> Verdict:
    notes: list[str] = []
    title = job.title.lower()

    # Title
    tcfg = criteria["title"]
    for group in tcfg["must_include_one_of_each"]:
        if not any(term in title for term in group):
            return Verdict(False, "title doesn't match")
    for term in tcfg["skip_if_contains"]:
        if term in title:
            return Verdict(False, f"title contains '{term}'")

    # Fake, ghost and recruiter postings
    if NO_COMPANY.match(job.company.strip()):
        return Verdict(False, "no company name")
    if is_recruiter(job):
        if criteria.get("skip_recruiters", True):
            return Verdict(False, "staffing agency or recruiter")
        notes.append("posted by a recruiter, not the employer")
    # Google for Jobs finds postings anywhere; say so when the employer's own site isn't among them.
    if job.publisher and not job.from_employer:
        if job.publisher.lower() == "linkedin":
            notes.append("only found on LinkedIn, not the employer's own site")
        else:
            notes.append(f"found on {job.publisher}, not the employer's own site")

    # Employment type
    if criteria.get("no_contract_work", True):
        etype = job.employment_type.lower()
        if any(word in etype for word in CONTRACT_TYPES):
            return Verdict(False, f"employment type '{job.employment_type}'")
        match = CONTRACT_TEXT.search(f"{job.title}\n{job.description}")
        if match:
            return Verdict(False, f"contract wording: '{match.group(0)}'")

    # Where
    where = criteria["where"]
    mode = job.work_mode
    if mode == "unknown":
        mode = guess_work_mode(f"{job.title}\n{job.location}\n{job.description}")
    if mode == "remote":
        if not where["remote"]:
            return Verdict(False, "remote not wanted")
        if where.get("country") == "US" and FOREIGN_ONLY.search(job.location) \
                and not US_TEXT.search(job.location):
            return Verdict(False, f"remote only in {job.location}")
    elif mode == "hybrid":
        if not where["hybrid"]:
            return Verdict(False, "hybrid not wanted")
        places = where.get("hybrid_places") or []
        if places and not any(p.lower() in job.location.lower() for p in places):
            return Verdict(False, f"hybrid, but in {job.location}")
    else:
        return Verdict(False, "on-site, or remote/hybrid not stated")
    job.work_mode = mode

    # Pay: judge by the top of the range, since that's what's negotiable.
    pay = criteria["pay"]
    if job.salary_min is None and job.salary_max is None:
        found = salary_from_text(job.description)
        if found:
            job.salary_min, job.salary_max = found
    top = job.salary_max or job.salary_min
    if top is None:
        if not pay["include_if_not_listed"]:
            return Verdict(False, "pay not listed")
        notes.append("pay not listed")
    elif top < pay["minimum_per_year"]:
        return Verdict(False, f"pay tops out at ${top:,.0f}")

    return Verdict(True, notes=notes)
