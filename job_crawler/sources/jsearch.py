"""JSearch (RapidAPI): aggregates Google for Jobs, which indexes LinkedIn,
Indeed, Glassdoor, ZipRecruiter and company career pages.

Key: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch  (env JSEARCH_API_KEY)
"""
import os

import requests

from ..models import Job

URL = "https://jsearch.p.rapidapi.com/search"
HOST = "jsearch.p.rapidapi.com"
PERIOD_TO_ANNUAL = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}
DATE_POSTED = {1: "today", 3: "3days", 7: "week"}


def _annual(amount, period):
    if amount is None:
        return None
    return float(amount) * PERIOD_TO_ANNUAL.get((period or "YEAR").upper(), 1)


def _to_job(item: dict) -> Job:
    location = ", ".join(
        p for p in (item.get("job_city"), item.get("job_state"), item.get("job_country")) if p
    )
    benefits = list(item.get("job_benefits") or [])
    benefits += (item.get("job_highlights") or {}).get("Benefits", [])
    period = item.get("job_salary_period")
    return Job(
        source="jsearch",
        source_id=item["job_id"],
        title=item.get("job_title") or "",
        company=item.get("employer_name") or "",
        location=location or item.get("job_location") or "",
        url=item.get("job_apply_link") or "",
        description=item.get("job_description") or "",
        work_mode="remote" if item.get("job_is_remote") else "unknown",
        employment_type=item.get("job_employment_type") or "",
        salary_min=_annual(item.get("job_min_salary"), period),
        salary_max=_annual(item.get("job_max_salary"), period),
        benefits=benefits,
        posted_at=item.get("job_posted_at_datetime_utc") or "",
    )


def _search(key: str, query: str, country: str, max_days_old: int, remote_only: bool) -> list[Job]:
    params = {
        "query": query,
        "page": 1,
        "num_pages": 3,
        "country": country,
        "date_posted": next((v for d, v in DATE_POSTED.items() if max_days_old <= d), "month"),
        "employment_types": "FULLTIME",
    }
    if remote_only:
        params["remote_jobs_only"] = "true"
    resp = requests.get(
        URL, params=params, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}, timeout=60
    )
    resp.raise_for_status()
    return [_to_job(item) for item in resp.json().get("data", [])]


def fetch(config: dict) -> list[Job]:
    key = os.environ.get("JSEARCH_API_KEY")
    if not key:
        print("jsearch: JSEARCH_API_KEY not set, skipping")
        return []
    s = config["searches"]
    w = config["work_mode"]
    jobs: list[Job] = []
    for query in s["queries"]:
        if w["allow_remote"]:
            jobs += _search(key, query, s["country"], s["max_days_old"], remote_only=True)
        if w["allow_hybrid"]:
            places = w.get("hybrid_locations") or [""]
            for place in places:
                q = f"{query} hybrid" + (f" in {place}" if place else "")
                jobs += _search(key, q, s["country"], s["max_days_old"], remote_only=False)
    return jobs
