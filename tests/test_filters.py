import unittest
from pathlib import Path

import yaml

from jobmail.filters import evaluate, salary_from_text
from jobmail.models import Job

CRITERIA = yaml.safe_load((Path(__file__).resolve().parent.parent / "criteria.yaml").read_text())


def job(**overrides) -> Job:
    base = dict(
        source="Remotive", source_id="1", title="Senior Salesforce Developer", company="Acme",
        location="USA", url="https://example.com", description="Build Apex and LWC.",
        work_mode="remote", employment_type="full_time", salary_min=110000, salary_max=130000,
    )
    base.update(overrides)
    return Job(**base)


class TitleTests(unittest.TestCase):
    def test_ideal_job_passes_clean(self):
        v = evaluate(job(), CRITERIA)
        self.assertTrue(v.keep)
        self.assertEqual(v.notes, [])

    def test_any_salesforce_title_kept(self):
        for title in ("Salesforce Administrator", "Salesforce Business Analyst",
                      "Sr. Salesforce Consultant", "Salesforce Development Manager",
                      "MuleSoft Integration Engineer", "SFDC Platform Owner"):
            self.assertTrue(evaluate(job(title=title), CRITERIA).keep, title)

    def test_non_salesforce_and_junior_titles_skipped(self):
        for title in ("Java Developer", "Junior Salesforce Developer", "Salesforce Intern"):
            self.assertFalse(evaluate(job(title=title), CRITERIA).keep, title)


class ContractTests(unittest.TestCase):
    def test_contract_type_skipped(self):
        self.assertFalse(evaluate(job(employment_type="contract"), CRITERIA).keep)
        self.assertFalse(evaluate(job(employment_type="part_time"), CRITERIA).keep)

    def test_contract_wording_skipped(self):
        self.assertFalse(evaluate(job(description="This is a 6 month contract."), CRITERIA).keep)
        self.assertFalse(evaluate(job(description="W2 or C2C accepted"), CRITERIA).keep)


class WhereTests(unittest.TestCase):
    def test_hybrid_near_st_louis_kept(self):
        v = evaluate(job(work_mode="hybrid", location="Example Suburb, MO"), CRITERIA)
        self.assertTrue(v.keep)

    def test_hybrid_elsewhere_skipped(self):
        self.assertFalse(evaluate(job(work_mode="hybrid", location="Chicago, IL"), CRITERIA).keep)

    def test_onsite_skipped(self):
        self.assertFalse(evaluate(job(work_mode="unknown", location="Dallas, TX",
                                      description="In office five days."), CRITERIA).keep)

    def test_work_mode_guessed_from_text(self):
        v = evaluate(job(work_mode="unknown", location="Example City, MO",
                         description="This is a hybrid role, 2 days in office."), CRITERIA)
        self.assertTrue(v.keep)

    def test_remote_outside_us_skipped(self):
        self.assertFalse(evaluate(job(location="UK only"), CRITERIA).keep)
        self.assertFalse(evaluate(job(location="Europe"), CRITERIA).keep)

    def test_remote_us_or_canada_kept(self):
        self.assertTrue(evaluate(job(location="USA, Canada"), CRITERIA).keep)


class PayTests(unittest.TestCase):
    def test_low_pay_skipped(self):
        self.assertFalse(evaluate(job(salary_min=80000, salary_max=100000), CRITERIA).keep)

    def test_unlisted_pay_kept_with_note(self):
        v = evaluate(job(salary_min=None, salary_max=None), CRITERIA)
        self.assertTrue(v.keep)
        self.assertIn("pay not listed", v.notes)

    def test_pay_read_from_description(self):
        low = job(salary_min=None, salary_max=None, description="Pay: $95,000 - $100,000.")
        self.assertFalse(evaluate(low, CRITERIA).keep)
        good = job(salary_min=None, salary_max=None, description="$120K to $150K")
        self.assertTrue(evaluate(good, CRITERIA).keep)
        self.assertEqual(good.salary_max, 150000)

    def test_salary_text_formats(self):
        self.assertEqual(salary_from_text("$118,400.00 - $177,600.00"), (118400, 177600))
        self.assertEqual(salary_from_text("$120k–150k"), (120000, 150000))
        self.assertIsNone(salary_from_text("$5,000 signing bonus"))
        self.assertIsNone(salary_from_text("$45 - $60 per hour"))


class FakePostingTests(unittest.TestCase):
    def test_staffing_agency_skipped(self):
        self.assertFalse(evaluate(job(company="Insight Global"), CRITERIA).keep)
        self.assertFalse(evaluate(job(company="Acme Staffing"), CRITERIA).keep)

    def test_our_client_wording_skipped(self):
        j = job(description="On behalf of our client, we seek an Apex developer.")
        self.assertFalse(evaluate(j, CRITERIA).keep)

    def test_no_company_skipped(self):
        self.assertFalse(evaluate(job(company="Confidential"), CRITERIA).keep)
        self.assertFalse(evaluate(job(company=""), CRITERIA).keep)

    def test_agency_names_need_whole_words(self):
        self.assertTrue(evaluate(job(company="Dicerna Pharmaceuticals"), CRITERIA).keep)

    def test_linkedin_only_noted(self):
        v = evaluate(job(publisher="LinkedIn"), CRITERIA)
        self.assertTrue(v.keep)
        self.assertIn("only found on LinkedIn, not the employer's own site", v.notes)

    def test_employer_link_from_google_has_no_note(self):
        self.assertEqual(evaluate(job(publisher="LinkedIn", from_employer=True), CRITERIA).notes, [])

    def test_recruiters_kept_with_note_when_allowed(self):
        v = evaluate(job(company="Robert Half"), {**CRITERIA, "skip_recruiters": False})
        self.assertTrue(v.keep)
        self.assertIn("posted by a recruiter, not the employer", v.notes)


if __name__ == "__main__":
    unittest.main()
