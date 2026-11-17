# Job-crawler

> **Retired.** I used this for my own job search and have turned the daily schedule off. The code is kept here as a finished project. `criteria.yaml` holds placeholder values (salary floor and towns), not my real settings.

A Python bot that runs on GitHub Actions and emails me a daily digest of new Salesforce job postings. It pulls from employer careers pages, Google for Jobs (via the JSearch API) and three remote job boards, filters them against `criteria.yaml`, and sends only the jobs I haven't seen before.

## Why I built it

Checking job boards by hand every day is slow, and a lot of what shows up is recruiter reposts, duplicate ads or contract roles. This does the checking and the screening for me and delivers the result by email.

## What it does

- Fetches jobs from three kinds of source (`jobmail/sources/`): employer careers sites (Greenhouse, Lever, Ashby and Workday), JSearch / Google for Jobs, and Remotive, Remote OK and Jobicy
- Filters by title keywords, remote/hybrid and location, pay floor, contract vs. full-time, and staffing-agency postings (`jobmail/filters.py`)
- Marks jobs posted directly by the employer, and flags suspicious ones (same ad in 5+ cities, no pay listed)
- Emails an HTML + plain-text digest through Gmail SMTP (`jobmail/digest.py`, `jobmail/mailer.py`)
- Remembers what it already sent in `data/seen.json`, which the workflow commits back to the repo
- Was scheduled four times each morning (schedule now removed) because GitHub delays or skips scheduled runs; `--once-per-day` makes the extra runs do nothing once the email has gone out
- Runs the unit test suite in `tests/` before every send

## Stack

Python 3.12, `requests`, `PyYAML`, `unittest`, GitHub Actions (cron schedule, repository secrets), Gmail SMTP

## How to run it

Locally:

```
pip install -r requirements.txt
python -m jobmail.main --preview        # writes preview.html, sends nothing
python -m unittest discover -s tests
```

On GitHub: fork the repo, add the secrets described in the setup section below, then run **Actions → Daily job email → Run workflow**. To run it daily again, add a `schedule:` cron trigger back to `.github/workflows/daily-email.yml`.

## Where the jobs come from

- **Employers' own careers sites** (the `employers:` list in `criteria.yaml`).
  The employer posted these, so they're real openings. Marked ✅.
- **Google for Jobs**, through JSearch's free plan. It covers Indeed,
  Glassdoor, ZipRecruiter, LinkedIn and company sites. When a job has an apply
  link on the employer's own site, the email links there and marks it ✅;
  otherwise it notes where the job was found (e.g. "only found on LinkedIn").
- **Remotive, Remote OK and Jobicy**, three remote-job boards where employers
  pay to post. They're much less prone to fake listings than LinkedIn.

LinkedIn itself isn't scraped: that breaks LinkedIn's terms and can get your
account banned.

## Screening out fake postings

Skipped automatically:

- staffing agencies (Robert Half, TEKsystems, Insight Global, …) and
  "on behalf of our client" posts
- postings with no company name, or "Confidential"
- contract, contract-to-hire, C2C, 1099, temp, part-time and junior roles
- remote jobs limited to other countries
- pay ranges that top out under your minimum

Flagged ⚠️ but kept: the same ad in 5+ cities (a common sign of a recruiter or
an "evergreen" ad), and postings that don't list pay. For any job without ✅,
check that it's on the company's own careers page before applying.

## Setup (about 10 minutes)

**1. Make a Gmail app password.** This is a separate password just for this
tool; your real password stays private.

1. Turn on 2-Step Verification for your Google account if it isn't already:
   https://myaccount.google.com/signinoptions/twosv
2. Go to https://myaccount.google.com/apppasswords, type a name like
   "Job email", and click **Create**.
3. Copy the 16-letter password it shows.

**2. Add it to GitHub.** In this repository on GitHub, go to
**Settings → Secrets and variables → Actions → New repository secret**, and add:

| Name                 | Value                                              |
| -------------------- | -------------------------------------------------- |
| `GMAIL_ADDRESS`      | your Gmail address                                 |
| `GMAIL_APP_PASSWORD` | the 16-letter app password                         |
| `EMAIL_TO`           | *(optional)* where to send it, if not that Gmail   |

**3. Add Google for Jobs (JSearch).**

1. Make a free account at https://rapidapi.com/auth/sign-up.
2. Open https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/pricing and
   click **Subscribe** on the free **Basic** plan.
3. Open the **Playground** (or **Endpoints**) tab. In the code example, copy
   the long value shown next to `X-RapidAPI-Key`.
4. Add it to GitHub as a secret named `JSEARCH_API_KEY`, the same way as the
   Gmail ones.

The free plan has a monthly request limit (shown on the pricing page). The
default settings use about 120 requests a month; `jsearch.pages` in
`criteria.yaml` controls that. If the limit runs out, the email says so and
the other sources keep working.

**4. Test it.** Go to the **Actions** tab → **Daily job email** → **Run workflow**.
The email arrives within a few minutes. After that it runs every day on its
own. GitHub sometimes starts scheduled jobs hours late or skips them, so the
job is scheduled four times between about 4am and noon Central; the first one
that runs sends the email and the rest do nothing. Expect it in the morning,
occasionally around midday.

## Changing what you get

Edit `criteria.yaml` on GitHub (click the file, then the pencil icon). Each
setting has a comment explaining it. The most useful ones:

- `pay.minimum_per_year`: your salary floor
- `where.hybrid_places`: towns that count as close enough for hybrid
- `employers`: companies whose careers sites are checked daily. Add a
  company by pasting the web address of its job list. Many large local
  employers use Workday (`<company>.myworkdayjobs.com`), which works here.

If a careers link stops working or a job board is down, the email says so
at the bottom.
