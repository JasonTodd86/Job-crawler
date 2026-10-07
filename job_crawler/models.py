from dataclasses import dataclass, field


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    # "remote", "hybrid", "onsite" or "unknown"
    work_mode: str = "unknown"
    # Raw employment type from the source, e.g. "FULLTIME", "CONTRACTOR", "permanent".
    employment_type: str = ""
    # Annual USD; None when the posting doesn't list pay.
    salary_min: float | None = None
    salary_max: float | None = None
    # Benefit lines the source extracted for us, if any.
    benefits: list[str] = field(default_factory=list)
    posted_at: str = ""

    @property
    def id(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def dedupe_key(self) -> str:
        """Same job posted to several boards collapses to one entry."""
        return f"{self.company.strip().lower()}|{self.title.strip().lower()}"
