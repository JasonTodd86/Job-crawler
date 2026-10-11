import unittest
from pathlib import Path
from unittest import mock

import yaml

from jobmail.sources import employers

CONFIG = yaml.safe_load((Path(__file__).resolve().parent.parent / "criteria.yaml").read_text())


def response(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def run_board(url, payload, config=CONFIG):
    cfg = {**config, "employers": [{"url": url, "name": "Acme"}]}
    problems = []
    with mock.patch("requests.get", return_value=response(payload)):
        jobs = employers.fetch(cfg, problems)
    return jobs, problems


class ParseBoardTests(unittest.TestCase):
    def test_known_systems(self):
        self.assertEqual(employers.parse_board("https://boards.greenhouse.io/gitlab"),
                         ("greenhouse", {"slug": "gitlab"}))
        self.assertEqual(employers.parse_board("https://job-boards.greenhouse.io/acme/jobs/123"),
                         ("greenhouse", {"slug": "acme"}))
        self.assertEqual(employers.parse_board("jobs.lever.co/plaid"), ("lever", {"slug": "plaid"}))
        self.assertEqual(employers.parse_board("https://jobs.ashbyhq.com/ramp"), ("ashby", {"slug": "ramp"}))
        self.assertEqual(
            employers.parse_board("https://acme.wd5.myworkdayjobs.com/en-US/Acme_Careers"),
            ("workday", {"host": "acme.wd5.myworkdayjobs.com", "tenant": "acme", "site": "Acme_Careers"}),
        )

    def test_unknown_url_reported_not_raised(self):
        _, problems = run_board("https://www.linkedin.com/company/acme/jobs", {})
        self.assertEqual(len(problems), 1)


class FetcherTests(unittest.TestCase):
    def test_greenhouse(self):
        jobs, problems = run_board("https://boards.greenhouse.io/acme", {"jobs": [
            {"id": 1, "title": "Senior Salesforce Engineer", "absolute_url": "https://x/1",
             "location": {"name": "Remote - US"}, "content": "&lt;p&gt;Apex &amp;amp; LWC&lt;/p&gt;",
             "company_name": "Acme"},
            {"id": 2, "title": "Account Executive", "location": {"name": "NYC"}},
        ]})
        self.assertEqual(problems, [])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Acme")
        self.assertEqual(jobs[0].description, "Apex & LWC")
        self.assertTrue(jobs[0].from_employer)
        self.assertEqual(jobs[0].source, "Acme careers site")

    def test_lever_salary_and_mode(self):
        jobs, _ = run_board("https://jobs.lever.co/acme", [
            {"id": "a", "text": "Salesforce Developer", "hostedUrl": "https://x/a",
             "categories": {"location": "St. Louis, MO", "commitment": "Full-time"},
             "workplaceType": "hybrid", "descriptionPlain": "Build Apex.",
             "salaryRange": {"min": 110000, "max": 140000, "interval": "per-year-salary"},
             "createdAt": 1760000000000},
        ])
        self.assertEqual(jobs[0].work_mode, "hybrid")
        self.assertEqual(jobs[0].salary_max, 140000)
        self.assertTrue(jobs[0].posted_at.startswith("2025"))

    def test_ashby(self):
        jobs, _ = run_board("https://jobs.ashbyhq.com/acme", {"jobs": [
            {"id": "z", "title": "Staff Salesforce Engineer", "location": "United States",
             "isRemote": True, "employmentType": "FullTime", "descriptionPlain": "Apex",
             "jobUrl": "https://x/z", "compensation": {"summaryComponents": [
                 {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
                  "minValue": 150000, "maxValue": 190000}]}},
        ]})
        self.assertEqual(jobs[0].work_mode, "remote")
        self.assertEqual((jobs[0].salary_min, jobs[0].salary_max), (150000, 190000))

    def test_workday_fetches_details_for_matching_titles_only(self):
        listing = response({"jobPostings": [
            {"title": "Salesforce Developer", "externalPath": "/job/STL/Salesforce-Dev_R1"},
            {"title": "Nurse", "externalPath": "/job/STL/Nurse_R2"},
        ]})
        detail = response({"jobPostingInfo": {
            "title": "Salesforce Developer", "location": "St. Louis, MO", "timeType": "Full time",
            "jobDescription": "<p>Hybrid role.</p>", "jobReqId": "R1",
            "externalUrl": "https://acme.wd5.myworkdayjobs.com/Ext/job/R1"}})
        cfg = {**CONFIG, "employers": ["https://acme.wd5.myworkdayjobs.com/Ext"],
               "keywords": ["salesforce"]}
        with mock.patch("requests.post", return_value=listing), \
             mock.patch("requests.get", return_value=detail) as get:
            jobs = employers.fetch(cfg, [])
        self.assertEqual(get.call_count, 1)
        self.assertEqual(jobs[0].employment_type, "Full time")
        self.assertIn("Hybrid", jobs[0].description)


if __name__ == "__main__":
    unittest.main()
