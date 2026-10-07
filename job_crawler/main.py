"""Fetch jobs, filter them against config.yaml, and write a Markdown report
of matches not seen on a previous run.

    python -m job_crawler.main [--config config.yaml] [--all]
"""
import argparse
import json
from datetime import date
from pathlib import Path

import yaml

from .filters import evaluate
from .models import Job
from .sources import adzuna, jsearch

ROOT = Path(__file__).resolve().parent.parent
SEEN_FILE = ROOT / "data" / "seen.json"
REPORT_DIR = ROOT / "reports"
SOURCES = [jsearch, adzuna]


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=1, sort_keys=True))


def fmt_salary(job: Job) -> str:
    if job.salary_min is None and job.salary_max is None:
        return "not listed"
    lo, hi = job.salary_min, job.salary_max
    if lo and hi and lo != hi:
        return f"${lo:,.0f} – ${hi:,.0f}"
    return f"${(hi or lo):,.0f}"


def sort_key(item):
    job, verdict = item
    # Leadership roles first, then fully verified jobs, then by top salary.
    return (not verdict.leadership, len(verdict.flags), -(job.salary_max or job.salary_min or 0))


def render(matches, today: str, total: int, rejected: int) -> str:
    lines = [
        f"# Salesforce jobs — {today}",
        "",
        f"{len(matches)} new matches ({total} fetched, {rejected} filtered out, "
        "rest already seen). ⭐ = manager role or direct reports.",
        "",
    ]
    for job, verdict in matches:
        lines += [
            f"## {'⭐ ' if verdict.leadership else ''}[{job.title}]({job.url})",
            f"**{job.company}** · {job.location or 'location n/a'} · {job.work_mode}",
            "",
            f"- Salary: {fmt_salary(job)}",
            f"- Source: {job.source} · posted {job.posted_at[:10] or 'n/a'}",
        ]
        if verdict.flags:
            lines.append(f"- ⚠️ {'; '.join(verdict.flags)}")
        lines.append("")
    return "\n".join(lines)


def run(config_path: Path, show_all: bool) -> None:
    config = yaml.safe_load(config_path.read_text())
    jobs: list[Job] = []
    for source in SOURCES:
        try:
            jobs += source.fetch(config)
        except Exception as exc:  # one broken source shouldn't sink the run
            print(f"{source.__name__}: failed: {exc}")

    seen = load_seen()
    today = date.today().isoformat()
    matches, rejected, batch = [], 0, set()
    for job in jobs:
        if job.dedupe_key in batch:
            continue
        batch.add(job.dedupe_key)
        verdict = evaluate(job, config)
        if not verdict.keep:
            rejected += 1
            continue
        if job.dedupe_key in seen and not show_all:
            continue
        seen.setdefault(job.dedupe_key, today)
        matches.append((job, verdict))

    matches.sort(key=sort_key)
    report = render(matches, today, len(batch), rejected)
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / f"{today}.md").write_text(report)
    (REPORT_DIR / "latest.md").write_text(report)
    save_seen(seen)
    print(f"{len(matches)} new matches written to reports/latest.md")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--all", action="store_true", help="include previously seen matches")
    args = parser.parse_args()
    run(args.config, args.all)


if __name__ == "__main__":
    main()
