"""Find new jobs matching criteria.yaml and email them.

    python -m jobmail.main                 # search and send the email
    python -m jobmail.main --preview       # write preview.html instead of sending
    python -m jobmail.main --preview --all # include jobs already emailed before
    python -m jobmail.main --once-per-day  # do nothing if today's email already went out
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

from . import digest, mailer
from .filters import evaluate
from .models import Job
from .sources import boards, employers, jsearch

ROOT = Path(__file__).resolve().parent.parent
SEEN_FILE = ROOT / "data" / "seen.json"
# The date (UTC) the last email went out, so extra scheduled runs know to stop.
LAST_SENT_FILE = ROOT / "data" / "last_sent.txt"
# Employers' sites go first so their copy of a job wins over a job board's.
SOURCES = [employers, jsearch, boards]
# The same title from one company in this many cities is usually a recruiter
# collecting résumés or an "evergreen" ad with no real opening behind it.
MASS_POSTING_CITIES = 5


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=1, sort_keys=True) + "\n")


def sort_key(match):
    job, verdict = match
    # Employer-posted first, then fewest caveats, then highest pay.
    return (not job.from_employer, len(verdict.notes),
            -(job.salary_max or job.salary_min or 0))


def find_matches(jobs: list[Job], criteria: dict, seen: dict, include_seen: bool):
    cities = defaultdict(set)
    for job in jobs:
        cities[job.dedupe_key].add(job.location.lower())

    matches, keys = [], set()
    for job in jobs:
        if job.dedupe_key in keys:
            continue
        keys.add(job.dedupe_key)
        verdict = evaluate(job, criteria)
        if not verdict.keep:
            continue
        spread = len(cities[job.dedupe_key])
        if not job.from_employer and spread >= MASS_POSTING_CITIES:
            verdict.notes.append(f"same ad in {spread} cities (often a recruiter or evergreen ad)")
        if job.dedupe_key in seen and not include_seen:
            continue
        matches.append((job, verdict))
    matches.sort(key=sort_key)
    return matches


def already_sent_today() -> bool:
    return LAST_SENT_FILE.exists() and LAST_SENT_FILE.read_text().strip() == date.today().isoformat()


def run(criteria_path: Path, preview: bool, include_seen: bool, once_per_day: bool = False) -> None:
    if once_per_day and already_sent_today():
        print("Today's email already went out; nothing to do.")
        return
    criteria = yaml.safe_load(criteria_path.read_text())
    jobs: list[Job] = []
    problems: list[str] = []
    for source in SOURCES:
        jobs += source.fetch(criteria, problems)
    for problem in problems:
        print(problem)

    seen = load_seen()
    matches = find_matches(jobs, criteria, seen, include_seen)
    day = date.today().strftime("%a %b %-d")
    print(f"{len(jobs)} jobs fetched, {len(matches)} new matches")

    subject = digest.subject(matches, day)
    text = digest.plain_text(matches, day, problems)
    page = digest.html(matches, day, problems)
    if preview:
        (ROOT / "preview.html").write_text(page)
        print("Wrote preview.html (no email sent)")
        return
    if matches or criteria.get("email", {}).get("send_when_nothing_new", True):
        mailer.send(subject, text, page)
        print(f"Sent: {subject}")
    # Only remember jobs once the email has gone out, so a failed send retries them next run.
    today = date.today().isoformat()
    for job, _ in matches:
        seen.setdefault(job.dedupe_key, today)
    save_seen(seen)
    LAST_SENT_FILE.write_text(today + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--criteria", type=Path, default=ROOT / "criteria.yaml")
    parser.add_argument("--preview", action="store_true", help="write preview.html instead of emailing")
    parser.add_argument("--all", action="store_true", help="include jobs already emailed")
    parser.add_argument("--once-per-day", action="store_true",
                        help="do nothing if today's email already went out")
    args = parser.parse_args()
    run(args.criteria, args.preview, args.all, args.once_per_day)


if __name__ == "__main__":
    main()
