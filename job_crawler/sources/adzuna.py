"""Adzuna job search API (free tier).

Keys: https://developer.adzuna.com/  (env ADZUNA_APP_ID, ADZUNA_APP_KEY)
Adzuna only returns a short description snippet, so benefits are rarely
detectable from its listings.
"""
import os

import requests

from ..models import Job

URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def _to_job(item: dict) -> Job:
    predicted = str(item.get("salary_is_predicted", "0")) == "1"
    return Job(
        source="adzuna",
        source_id=str(item["id"]),
        title=item.get("title") or "",
        company=(item.get("company") or {}).get("display_name") or "",
        location=(item.get("location") or {}).get("display_name") or "",
        url=item.get("redirect_url") or "",
        description=item.get("description") or "",
        employment_type=" ".join(
            t for t in (item.get("contract_type"), item.get("contract_time")) if t
        ),
        # Adzuna's predicted salaries are estimates, not what the employer posted.
        salary_min=None if predicted else item.get("salary_min"),
        salary_max=None if predicted else item.get("salary_max"),
        posted_at=item.get("created") or "",
    )


def fetch(config: dict) -> list[Job]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("adzuna: ADZUNA_APP_ID/ADZUNA_APP_KEY not set, skipping")
        return []
    s = config["searches"]
    jobs: list[Job] = []
    for query in s["queries"]:
        for page in (1, 2):
            resp = requests.get(
                URL.format(country=s["country"], page=page),
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": query,
                    "max_days_old": s["max_days_old"],
                    "results_per_page": 50,
                    "full_time": 1,
                    "content-type": "application/json",
                },
                timeout=60,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            jobs += [_to_job(item) for item in results]
            if len(results) < 50:
                break
    return jobs
