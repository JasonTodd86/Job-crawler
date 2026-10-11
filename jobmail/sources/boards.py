"""Free remote-job boards with public APIs. No sign-up or key needed.

Employers pay these boards to post, so their listings are far less likely to
be fake than LinkedIn's. Each board is called once per day, well inside their
published limits, and every job links back to the board as their terms ask.
"""
import requests

from ..models import Job, strip_html

TIMEOUT = 60
SEARCH = "salesforce"  # the title filter in criteria.yaml narrows it from here
HEADERS = {"User-Agent": "jobmail daily job digest (personal use)"}


def _usd(amount) -> float | None:
    try:
        return float(amount) or None
    except (TypeError, ValueError):
        return None


def remotive() -> list[Job]:
    resp = requests.get("https://remotive.com/api/remote-jobs", params={"search": SEARCH},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return [
        Job(
            source="Remotive",
            source_id=f"remotive:{item['id']}",
            title=item.get("title") or "",
            company=item.get("company_name") or "",
            location=item.get("candidate_required_location") or "",
            url=item.get("url") or "",
            # Pay is free text here ("$120k - $150k"); the filter reads it from the description.
            description=f"{item.get('salary') or ''}\n{strip_html(item.get('description') or '')}",
            work_mode="remote",
            employment_type=item.get("job_type") or "",
            posted_at=item.get("publication_date") or "",
        )
        for item in resp.json().get("jobs", [])
    ]


def remoteok() -> list[Job]:
    resp = requests.get("https://remoteok.com/api", params={"tag": SEARCH},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    # The first element is the API's legal notice, not a job.
    return [
        Job(
            source="Remote OK",
            source_id=f"remoteok:{item['id']}",
            title=item.get("position") or "",
            company=item.get("company") or "",
            location=item.get("location") or "",
            url=item.get("url") or "",
            description=strip_html(item.get("description") or ""),
            work_mode="remote",
            salary_min=_usd(item.get("salary_min")),
            salary_max=_usd(item.get("salary_max")),
            posted_at=item.get("date") or "",
        )
        for item in resp.json()
        if isinstance(item, dict) and item.get("id") and item.get("position")
    ]


def jobicy() -> list[Job]:
    resp = requests.get("https://jobicy.com/api/v2/remote-jobs",
                        params={"count": 50, "tag": SEARCH, "geo": "usa"},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        usd = (item.get("salaryCurrency") or "USD") == "USD"
        jtype = item.get("jobType") or ""
        jobs.append(Job(
            source="Jobicy",
            source_id=f"jobicy:{item['id']}",
            title=strip_html(item.get("jobTitle") or ""),
            company=item.get("companyName") or "",
            location=item.get("jobGeo") or "",
            url=item.get("url") or "",
            description=strip_html(item.get("jobDescription") or item.get("jobExcerpt") or ""),
            work_mode="remote",
            employment_type=", ".join(jtype) if isinstance(jtype, list) else jtype,
            salary_min=_usd(item.get("annualSalaryMin")) if usd else None,
            salary_max=_usd(item.get("annualSalaryMax")) if usd else None,
            posted_at=item.get("pubDate") or "",
        ))
    return jobs


BOARDS = {"remotive": remotive, "remoteok": remoteok, "jobicy": jobicy}


def fetch(criteria: dict, problems: list[str]) -> list[Job]:
    jobs: list[Job] = []
    for name, enabled in (criteria.get("job_boards") or {}).items():
        if not enabled or name not in BOARDS:
            continue
        try:
            jobs += BOARDS[name]()
        except Exception as exc:  # one board being down shouldn't sink the rest
            problems.append(f"{name} job board: couldn't load ({type(exc).__name__})")
    return jobs
