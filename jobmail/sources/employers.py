"""Jobs straight from employers' own careers boards. No API key needed.

Each entry under `employers:` in criteria.yaml is the URL of a company's careers
page on one of these hiring systems (the address bar when you open their job list):

    Greenhouse  https://boards.greenhouse.io/<company>  (or job-boards.greenhouse.io)
    Lever       https://jobs.lever.co/<company>
    Ashby       https://jobs.ashbyhq.com/<company>
    Workday     https://<company>.wd5.myworkdayjobs.com/<site>

A job on the employer's own board is posted by the employer, so it can't be a
reposted or scraped fake.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from ..models import Job, strip_html

TIMEOUT = 60
WORKDAY_PAGE = 20
WORKDAY_MAX = 100
INTERVAL_TO_ANNUAL = {"year": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}


def title_matches(title: str, criteria: dict) -> bool:
    title = title.lower()
    return all(any(term in title for term in group)
               for group in criteria["title"]["must_include_one_of_each"])


def parse_board(url: str) -> tuple[str, dict]:
    """Return (system, details) for a careers-board URL."""
    u = urlparse(url if "//" in url else f"https://{url}")
    host = u.netloc.lower()
    parts = [p for p in u.path.split("/") if p]
    if host.endswith("greenhouse.io") and parts:
        return "greenhouse", {"slug": parts[0]}
    if host == "jobs.lever.co" and parts:
        return "lever", {"slug": parts[0]}
    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", {"slug": parts[0]}
    if host.endswith("myworkdayjobs.com"):
        parts = [p for p in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)]  # drop "en-US"
        if parts:
            return "workday", {"host": host, "tenant": host.split(".")[0], "site": parts[0]}
    raise ValueError(f"not a Greenhouse, Lever, Ashby or Workday careers URL: {url}")


def _greenhouse(d: dict, name: str, config: dict) -> list[Job]:
    resp = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{d['slug']}/jobs",
        params={"content": "true"}, timeout=TIMEOUT,
    )
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        if not title_matches(item.get("title") or "", config):
            continue
        jobs.append(Job(
            source=f"{name or d.get('slug') or d.get('tenant')} careers site",
            source_id=f"greenhouse:{d['slug']}:{item['id']}",
            title=item["title"],
            company=name or item.get("company_name") or d["slug"],
            location=(item.get("location") or {}).get("name") or "",
            url=item.get("absolute_url") or "",
            description=strip_html(item.get("content") or ""),
            posted_at=item.get("first_published") or item.get("updated_at") or "",
            from_employer=True,
        ))
    return jobs


def _lever(d: dict, name: str, config: dict) -> list[Job]:
    resp = requests.get(
        f"https://api.lever.co/v0/postings/{d['slug']}", params={"mode": "json"}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    jobs = []
    for item in resp.json():
        if not title_matches(item.get("text") or "", config):
            continue
        cats = item.get("categories") or {}
        lists = "\n".join(
            f"{block.get('text', '')}\n{strip_html(block.get('content', ''))}"
            for block in item.get("lists") or []
        )
        pay = item.get("salaryRange") or {}
        # Lever intervals look like "per-year-salary" or "per-hour-wage".
        unit = re.search(r"year|month|week|day|hour", str(pay.get("interval", "")))
        mult = INTERVAL_TO_ANNUAL[unit.group(0)] if unit else 1
        mode = (item.get("workplaceType") or "").lower()
        created = item.get("createdAt")
        jobs.append(Job(
            source=f"{name or d.get('slug') or d.get('tenant')} careers site",
            source_id=f"lever:{d['slug']}:{item['id']}",
            title=item["text"],
            company=name or d["slug"],
            location=cats.get("location") or "",
            url=item.get("hostedUrl") or "",
            description="\n".join(
                p for p in (item.get("descriptionPlain"), lists, item.get("additionalPlain")) if p
            ),
            work_mode=mode if mode in ("remote", "hybrid", "onsite") else "unknown",
            employment_type=cats.get("commitment") or "",
            salary_min=pay["min"] * mult if pay.get("min") else None,
            salary_max=pay["max"] * mult if pay.get("max") else None,
            posted_at=datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else "",
            from_employer=True,
        ))
    return jobs


def _ashby_salary(comp: dict) -> tuple[float | None, float | None]:
    for part in (comp or {}).get("summaryComponents") or []:
        if part.get("compensationType") == "Salary" and part.get("currencyCode", "USD") == "USD":
            unit = str(part.get("interval", "1 YEAR")).split()[-1].lower()
            mult = INTERVAL_TO_ANNUAL.get(unit, 1)
            lo, hi = part.get("minValue"), part.get("maxValue")
            return (lo * mult if lo else None, hi * mult if hi else None)
    return None, None


def _ashby(d: dict, name: str, config: dict) -> list[Job]:
    resp = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{d['slug']}",
        params={"includeCompensation": "true"}, timeout=TIMEOUT,
    )
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        if not title_matches(item.get("title") or "", config):
            continue
        mode = (item.get("workplaceType") or "").lower()
        if item.get("isRemote") and mode not in ("hybrid", "onsite"):
            mode = "remote"
        lo, hi = _ashby_salary(item.get("compensation"))
        jobs.append(Job(
            source=f"{name or d.get('slug') or d.get('tenant')} careers site",
            source_id=f"ashby:{d['slug']}:{item['id']}",
            title=item["title"],
            company=name or d["slug"],
            location=item.get("location") or "",
            url=item.get("jobUrl") or "",
            description=item.get("descriptionPlain") or strip_html(item.get("descriptionHtml") or ""),
            work_mode=mode if mode in ("remote", "hybrid", "onsite") else "unknown",
            employment_type=item.get("employmentType") or "",
            salary_min=lo,
            salary_max=hi,
            posted_at=item.get("publishedAt") or "",
            from_employer=True,
        ))
    return jobs


def _workday(d: dict, name: str, config: dict) -> list[Job]:
    api = f"https://{d['host']}/wday/cxs/{d['tenant']}/{d['site']}"
    postings = []
    # Workday has a search box, so ask it for each query rather than paging every job.
    for query in config["keywords"]:
        offset = 0
        while offset < WORKDAY_MAX:
            resp = requests.post(
                f"{api}/jobs",
                json={"appliedFacets": {}, "limit": WORKDAY_PAGE, "offset": offset, "searchText": query},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            page = resp.json().get("jobPostings") or []
            postings += page
            if len(page) < WORKDAY_PAGE:
                break
            offset += WORKDAY_PAGE

    jobs, done = [], set()
    for post in postings:
        path = post.get("externalPath") or ""
        if path in done or not title_matches(post.get("title") or "", config):
            continue
        done.add(path)
        # The search results omit the description, so fetch it for matching titles only.
        resp = requests.get(f"{api}{path}", timeout=TIMEOUT)
        resp.raise_for_status()
        info = resp.json().get("jobPostingInfo") or {}
        location = info.get("location") or post.get("locationsText") or ""
        jobs.append(Job(
            source=f"{name or d.get('slug') or d.get('tenant')} careers site",
            source_id=f"workday:{d['tenant']}:{info.get('jobReqId') or path}",
            title=info.get("title") or post["title"],
            company=name or ((resp.json().get("hiringOrganization") or {}).get("name")) or d["tenant"],
            location=location,
            url=info.get("externalUrl") or f"https://{d['host']}/{d['site']}{path}",
            description=f"{info.get('remoteType') or ''}\n{strip_html(info.get('jobDescription') or '')}",
            employment_type=info.get("timeType") or "",
            posted_at=info.get("startDate") or "",
            from_employer=True,
        ))
    return jobs


def explain(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code == 404:
            return "board not found (404) — check the link on the company's careers page"
        return f"careers site answered HTTP {exc.response.status_code}"
    if isinstance(exc, requests.RequestException):
        return f"couldn't connect ({type(exc).__name__})"
    return str(exc)


FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby, "workday": _workday}


def fetch(config: dict, problems: list[str]) -> list[Job]:
    jobs: list[Job] = []
    for entry in config.get("employers") or []:
        if isinstance(entry, str):
            entry = {"url": entry}
        url, name = entry["url"], entry.get("name", "")
        try:
            system, details = parse_board(url)
            jobs += FETCHERS[system](details, name, config)
        except Exception as exc:  # one dead careers page shouldn't sink the rest
            problems.append(f"employer board {url}: {explain(exc)}")
    return jobs
