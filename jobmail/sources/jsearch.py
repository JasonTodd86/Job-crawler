"""Google for Jobs, through JSearch on RapidAPI (free plan).

Google for Jobs indexes Indeed, Glassdoor, ZipRecruiter, LinkedIn and company
careers sites. When one of a job's apply links is on the employer's own site,
the email links there and marks it ✅.

Key: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch  (env JSEARCH_API_KEY)
"""
import os

import requests

from ..models import Job

URL = "https://jsearch.p.rapidapi.com/search"
HOST = "jsearch.p.rapidapi.com"
TIMEOUT = 60
PERIOD_TO_ANNUAL = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}
DATE_POSTED = {1: "today", 3: "3days", 7: "week", 30: "month"}


def _annual(amount, period) -> float | None:
    if not amount:
        return None
    return float(amount) * PERIOD_TO_ANNUAL.get((period or "YEAR").upper(), 1)


def _to_job(item: dict) -> Job:
    location = ", ".join(p for p in (item.get("job_city"), item.get("job_state")) if p)
    direct = next((o for o in item.get("apply_options") or [] if o.get("is_direct")), None)
    url = (direct or {}).get("apply_link") or item.get("job_apply_link") or ""
    period = item.get("job_salary_period")
    return Job(
        source="Google for Jobs",
        source_id=f"jsearch:{item['job_id']}",
        title=item.get("job_title") or "",
        company=item.get("employer_name") or "",
        location=location or item.get("job_location") or item.get("job_country") or "",
        url=url,
        description=item.get("job_description") or "",
        work_mode="remote" if item.get("job_is_remote") else "unknown",
        employment_type=item.get("job_employment_type") or "",
        salary_min=_annual(item.get("job_min_salary"), period),
        salary_max=_annual(item.get("job_max_salary"), period),
        posted_at=item.get("job_posted_at_datetime_utc") or "",
        from_employer=bool(direct or item.get("job_apply_is_direct")),
        publisher=item.get("job_publisher") or "",
    )


def _search(key: str, query: str, cfg: dict, remote_only: bool) -> list[Job]:
    days = cfg.get("posted_within_days", 7)
    params = {
        "query": query,
        "page": 1,
        "num_pages": cfg.get("pages", 2),
        "country": "us",
        "date_posted": next((v for d, v in DATE_POSTED.items() if days <= d), "month"),
        "employment_types": "FULLTIME",
    }
    if remote_only:
        params["remote_jobs_only"] = "true"
    resp = requests.get(URL, params=params, timeout=TIMEOUT,
                        headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST})
    resp.raise_for_status()
    return [_to_job(item) for item in resp.json().get("data") or []]


def fetch(criteria: dict, problems: list[str]) -> list[Job]:
    cfg = criteria.get("jsearch") or {}
    if not cfg.get("enabled"):
        return []
    key = os.environ.get("JSEARCH_API_KEY")
    if not key:
        problems.append("Google for Jobs skipped: add the JSEARCH_API_KEY secret (see README)")
        return []
    where = criteria["where"]
    query = " ".join(criteria.get("keywords") or ["salesforce"])
    searches = []
    if where["remote"]:
        searches.append((query, True))
    if where["hybrid"]:
        # Local results include on-site jobs; the filter keeps only the hybrid ones.
        searches.append((f"{query} in Example City, MO", False))
    jobs: list[Job] = []
    for q, remote_only in searches:
        try:
            jobs += _search(key, q, cfg, remote_only)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            hint = {401: " (check the key)", 403: " (check you're subscribed to the free plan)",
                    429: " (monthly free allowance used up)"}.get(code, "")
            # RapidAPI explains most refusals in the body, e.g. {"message": "..."}.
            detail = (exc.response.text or "").strip()[:200] if exc.response is not None else ""
            problems.append(f"Google for Jobs: HTTP {code}{hint}" + (f": {detail}" if detail else ""))
            break
        except requests.RequestException as exc:
            problems.append(f"Google for Jobs: couldn't connect ({type(exc).__name__})")
            break
    return jobs
