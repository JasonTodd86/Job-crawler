# Job Crawler

Weekday search for full-time Salesforce developer and development-manager jobs
that match `config.yaml`: remote anywhere, or hybrid in the St. Louis / St. Charles
area; $105k+; no contract work; benefits offered. Manager roles and roles with
direct reports are marked ⭐ and listed first.

It does **not** scrape LinkedIn (that violates LinkedIn's terms and risks your
account). It uses job-aggregator APIs instead. JSearch pulls from Google for
Jobs, which indexes most LinkedIn postings along with Indeed, Glassdoor and
company career sites.

## Setup

1. Get API keys:
   - **JSearch**: subscribe to the free plan at
     https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch and copy your RapidAPI key.
   - **Adzuna** (optional): register at https://developer.adzuna.com/ for an app ID and key.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   and add `JSEARCH_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
   JSearch's free plan has a small monthly request limit. Each run uses
   2 requests per query in `config.yaml` (one remote, one St. Louis), so the
   default 3 queries × 22 weekdays ≈ 132 requests/month. Check the limit on
   your plan page before adding queries.
3. The workflow in `.github/workflows/daily.yml` runs every weekday morning and commits
   the results to `reports/latest.md`. Run it on demand from the **Actions** tab
   with **Run workflow**.

## Reading the report

Each run lists only jobs it hasn't shown you before (tracked in `data/seen.json`).
Jobs whose details are fully confirmed come first. Jobs whose posting leaves
something unstated are kept but marked ⚠️:

- **salary not listed**: set `salary.include_unlisted: false` to drop these.
- **benefits not mentioned**: set `benefits.require_mention: true` to drop these.
  Many full-time postings leave benefits out, so dropping them hides real jobs.

Always rejected: contract, contract-to-hire, C2C, 1099, temp, part-time, on-site
only, junior/intern, and any posted salary range topping out under the minimum.

## Running locally

```
pip install -r requirements.txt
export JSEARCH_API_KEY=...
python -m job_crawler.main          # new matches only
python -m job_crawler.main --all    # include already-seen matches
python -m unittest discover -s tests
```
