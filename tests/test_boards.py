import unittest
from unittest import mock

from jobmail.sources import boards


def response(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


class BoardTests(unittest.TestCase):
    def test_remotive(self):
        with mock.patch("requests.get", return_value=response({"jobs": [
            {"id": 7, "title": "Salesforce Developer", "company_name": "Acme",
             "candidate_required_location": "USA", "url": "https://remotive.com/7",
             "salary": "$120k - $150k", "description": "<p>Apex</p>", "job_type": "full_time",
             "publication_date": "2026-10-10T00:00:00"}]})):
            jobs = boards.remotive()
        self.assertEqual(jobs[0].work_mode, "remote")
        self.assertTrue(jobs[0].description.startswith("$120k - $150k"))

    def test_remoteok_skips_legal_notice(self):
        with mock.patch("requests.get", return_value=response([
            {"legal": "API terms..."},
            {"id": "9", "position": "Salesforce Engineer", "company": "Acme", "location": "US",
             "url": "https://remoteok.com/9", "salary_min": 0, "salary_max": 0,
             "description": "Apex", "date": "2026-10-10"}])):
            jobs = boards.remoteok()
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].salary_max)

    def test_jobicy(self):
        with mock.patch("requests.get", return_value=response({"jobs": [
            {"id": 3, "jobTitle": "Salesforce Architect", "companyName": "Acme", "jobGeo": "USA",
             "url": "https://jobicy.com/3", "jobType": ["full-time"], "jobDescription": "Apex",
             "annualSalaryMin": "140000", "annualSalaryMax": "170000", "salaryCurrency": "USD"}]})):
            jobs = boards.jobicy()
        self.assertEqual((jobs[0].salary_min, jobs[0].salary_max), (140000, 170000))
        self.assertEqual(jobs[0].employment_type, "full-time")

    def test_down_board_reported_and_others_still_run(self):
        problems = []
        with mock.patch.dict(boards.BOARDS, {"remotive": mock.Mock(side_effect=OSError),
                                             "jobicy": mock.Mock(return_value=["job"])}):
            jobs = boards.fetch({"job_boards": {"remotive": True, "jobicy": True,
                                                "remoteok": False}}, problems)
        self.assertEqual(jobs, ["job"])
        self.assertEqual(problems, ["remotive job board: couldn't load (OSError)"])


if __name__ == "__main__":
    unittest.main()
