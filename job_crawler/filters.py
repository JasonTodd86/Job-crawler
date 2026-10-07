"""Decides whether a job matches the criteria in config.yaml.

Each check either rejects the job or lets it through, possibly with a flag
(e.g. "salary not listed") so the report shows what couldn't be verified.
"""
import re
from dataclasses import dataclass, field

from .models import Job

CONTRACT_TYPES = ("contract", "contractor", "temporary", "temp", "part", "intern")

CONTRACT_PATTERN = re.compile(
    r"\b("
    r"c2c|corp[- ]to[- ]corp|1099|w-?2 contract|"
    r"contract[- ]to[- ]hire|contract to perm|"
    r"(this is an? )?\d+[- ]?(month|mo)\s+contract|"
    r"contract (position|role|opportunity|assignment)|"
    r"duration:\s*\d+\s*(months?|weeks?)"
    r")\b",
    re.IGNORECASE,
)

BENEFIT_PATTERN = re.compile(
    r"\b("
    r"health (insurance|benefits|coverage)|medical|dental|vision|"
    r"401\s?\(?k\)?|retirement|pension|"
    r"paid time off|pto|paid holidays|"
    r"life insurance|disability insurance|hsa|fsa|"
    r"comprehensive benefits|benefits package|full benefits"
    r")\b",
    re.IGNORECASE,
)

HYBRID_PATTERN = re.compile(r"\bhybrid\b", re.IGNORECASE)
REMOTE_PATTERN = re.compile(r"\b(fully remote|100% remote|remote)\b", re.IGNORECASE)

LEADERSHIP_TITLE = re.compile(r"\b(manager|director|head of|vp|vice president)\b", re.IGNORECASE)
LEADERSHIP_TEXT = re.compile(
    r"\b("
    r"direct reports?|people manager|people leader|"
    r"(manage|lead|mentor|build|grow) (and \w+ )?an? (small |growing )?(team|group) of|"
    r"(manage|lead) (the |our )?(development|engineering|salesforce) team|"
    r"performance reviews|hiring and developing"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class Verdict:
    keep: bool
    reason: str = ""
    flags: list[str] = field(default_factory=list)
    leadership: bool = False


def guess_work_mode(text: str) -> str:
    if HYBRID_PATTERN.search(text):
        return "hybrid"
    if REMOTE_PATTERN.search(text):
        return "remote"
    return "unknown"


def is_leadership(job: Job) -> bool:
    return bool(LEADERSHIP_TITLE.search(job.title) or LEADERSHIP_TEXT.search(job.description))


def has_benefits(job: Job) -> bool:
    return bool(job.benefits) or bool(BENEFIT_PATTERN.search(job.description))


def evaluate(job: Job, config: dict) -> Verdict:
    flags: list[str] = []
    title = job.title.lower()

    # Title
    tcfg = config["title"]
    for group in tcfg["required_groups"]:
        if not any(term in title for term in group):
            return Verdict(False, f"title missing one of {group}")
    for term in tcfg["exclude"]:
        if term in title:
            return Verdict(False, f"title contains '{term}'")

    # Employment type
    if config["employment"]["exclude_contract"]:
        etype = job.employment_type.lower()
        if any(word in etype for word in CONTRACT_TYPES):
            return Verdict(False, f"employment type '{job.employment_type}'")
        match = CONTRACT_PATTERN.search(f"{job.title}\n{job.description}")
        if match:
            return Verdict(False, f"contract wording: '{match.group(0)}'")

    # Work mode
    wcfg = config["work_mode"]
    mode = job.work_mode
    if mode == "unknown":
        mode = guess_work_mode(f"{job.title}\n{job.location}\n{job.description}")
    if mode == "remote":
        if not wcfg["allow_remote"]:
            return Verdict(False, "remote not allowed")
    elif mode == "hybrid":
        if not wcfg["allow_hybrid"]:
            return Verdict(False, "hybrid not allowed")
        places = wcfg.get("hybrid_locations") or []
        if places and not any(p.lower() in job.location.lower() for p in places):
            return Verdict(False, f"hybrid outside allowed locations ({job.location})")
    else:
        return Verdict(False, "on-site or work mode not stated")
    job.work_mode = mode

    # Salary: judge by the top of the range, since that's what's negotiable.
    scfg = config["salary"]
    top = job.salary_max or job.salary_min
    if top is None:
        if not scfg["include_unlisted"]:
            return Verdict(False, "salary not listed")
        flags.append("salary not listed")
    elif top < scfg["minimum_annual"]:
        return Verdict(False, f"salary ${top:,.0f} below minimum")

    # Benefits
    if not has_benefits(job):
        if config["benefits"]["require_mention"]:
            return Verdict(False, "benefits not mentioned")
        flags.append("benefits not mentioned")

    leadership = config.get("leadership", {}).get("prefer", False) and is_leadership(job)
    return Verdict(True, flags=flags, leadership=leadership)
