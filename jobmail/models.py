import html
import re
from dataclasses import dataclass, field

COMPANY_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|plc|lp)\b\.?", re.IGNORECASE)


def normalize_company(name: str) -> str:
    name = COMPANY_SUFFIX.sub("", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def strip_html(text: str) -> str:
    # Some APIs escape their HTML once more, hence unescaping on both sides.
    text = html.unescape(text or "")
    text = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(text)).strip()


@dataclass
class Job:
    source: str  # e.g. "GitLab careers site", "Remotive"
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    # "remote", "hybrid", "onsite" or "unknown"
    work_mode: str = "unknown"
    # Raw employment type from the source, e.g. "Full-time", "contract".
    employment_type: str = ""
    # Annual USD; None when the posting doesn't list pay.
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: str = ""
    # True when the employer posted this on its own careers site: the job is real.
    from_employer: bool = False

    @property
    def id(self) -> str:
        return self.source_id

    @property
    def dedupe_key(self) -> str:
        """The same job on several sites collapses to one entry."""
        return f"{normalize_company(self.company)}|{self.title.strip().lower()}"
