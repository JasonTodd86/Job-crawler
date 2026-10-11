import unittest
from pathlib import Path
from unittest import mock

import requests
import yaml

from jobmail.sources import jsearch

CRITERIA = yaml.safe_load((Path(__file__).resolve().parent.parent / "criteria.yaml").read_text())
ITEM = {
    "job_id": "abc", "job_title": "Salesforce Admin", "employer_name": "Acme",
    "job_city": "Example City", "job_state": "MO", "job_apply_link": "https://linkedin.com/jobs/1",
    "job_publisher": "LinkedIn", "job_employment_type": "FULLTIME", "job_is_remote": False,
    "job_min_salary": 50, "job_max_salary": 60, "job_salary_period": "HOUR",
    "apply_options": [{"publisher": "LinkedIn", "apply_link": "https://linkedin.com/jobs/1"},
                      {"publisher": "Acme", "apply_link": "https://acme.com/jobs/1", "is_direct": True}],
}


def response(payload, status=200):
    resp = mock.Mock(status_code=status, text="")
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class JSearchTests(unittest.TestCase):
    def fetch(self, resp, env={"JSEARCH_API_KEY": "k"}):
        problems = []
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("requests.get", return_value=resp) as get:
            jobs = jsearch.fetch(CRITERIA, problems)
        return jobs, problems, get

    def test_prefers_employer_link_and_annualizes_pay(self):
        jobs, problems, get = self.fetch(response({"data": [ITEM]}))
        self.assertEqual(problems, [])
        self.assertEqual(get.call_count, 2)  # remote search + Example City search
        job = jobs[0]
        self.assertEqual(job.url, "https://acme.com/jobs/1")
        self.assertTrue(job.from_employer)
        self.assertEqual(job.location, "Example City, MO")
        self.assertEqual(job.salary_max, 60 * 2080)

    def test_remote_flag_and_query(self):
        _, _, get = self.fetch(response({"data": []}))
        first, second = (c.kwargs["params"] for c in get.call_args_list)
        self.assertEqual(first["remote_jobs_only"], "true")
        self.assertEqual(second["query"], "salesforce in Example City, MO")
        self.assertEqual(first["date_posted"], "week")

    def test_missing_key_reported(self):
        jobs, problems, get = self.fetch(response({}), env={})
        self.assertEqual(jobs, [])
        self.assertIn("JSEARCH_API_KEY", problems[0])
        get.assert_not_called()

    def test_quota_used_up_reported_once(self):
        jobs, problems, get = self.fetch(response({}, status=429))
        self.assertEqual(problems, ["Google for Jobs: HTTP 429 (monthly free allowance used up)"])
        self.assertEqual(get.call_count, 1)

    def test_error_body_included(self):
        resp = response({}, status=404)
        resp.text = '{"message":"API doesn\'t exists"}'
        _, problems, _ = self.fetch(resp)
        self.assertEqual(problems, ['Google for Jobs: HTTP 404: {"message":"API doesn\'t exists"}'])


if __name__ == "__main__":
    unittest.main()
