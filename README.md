# Daily job email

Every morning this searches for jobs that match `criteria.yaml` and emails
you the new ones. Right now the criteria are: any full-time Salesforce job
(developer, admin, consultant, analyst, architect, manager and so on), remote
or hybrid around St. Louis / St. Charles, paying $105k or more, with no
contract work.

Each job is emailed once. Tomorrow's email only has jobs you haven't seen.

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

## One-time setup (about 10 minutes)

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
The email arrives within a few minutes. After that it runs every morning
around 7am Central.

## Changing what you get

Edit `criteria.yaml` on GitHub (click the file, then the pencil icon). Each
setting has a comment explaining it. The most useful ones:

- `pay.minimum_per_year`: your salary floor
- `where.hybrid_places`: towns that count as close enough for hybrid
- `employers`: companies whose careers sites are checked daily. Add a
  company by pasting the web address of its job list. Most large St. Louis
  employers use Workday (`<company>.myworkdayjobs.com`), which works here.

If a careers link stops working or a job board is down, the email says so
at the bottom.

## Running it yourself

```
pip install -r requirements.txt
python -m jobmail.main --preview        # writes preview.html, sends nothing
python -m unittest discover -s tests
```
