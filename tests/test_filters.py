import unittest
from pathlib import Path

import yaml

from job_crawler.filters import evaluate
from job_crawler.models import Job

CONFIG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text())
BENEFITS = "We offer medical, dental, vision and a 401(k) match."


def job(**overrides) -> Job:
    base = dict(
        source="test",
        source_id="1",
        title="Senior Salesforce Developer",
        company="Acme",
        location="St. Charles, MO",
        url="https://example.com",
        description=f"Build Apex and LWC. {BENEFITS}",
        work_mode="remote",
        employment_type="FULLTIME",
        salary_min=110000,
        salary_max=130000,
    )
    base.update(overrides)
    return Job(**base)


class FilterTests(unittest.TestCase):
    def test_ideal_job_passes_clean(self):
        v = evaluate(job(), CONFIG)
        self.assertTrue(v.keep)
        self.assertEqual(v.flags, [])

    def test_non_dev_title_rejected(self):
        self.assertFalse(evaluate(job(title="Salesforce Administrator"), CONFIG).keep)
        self.assertFalse(evaluate(job(title="Java Developer"), CONFIG).keep)

    def test_junior_rejected(self):
        self.assertFalse(evaluate(job(title="Junior Salesforce Developer"), CONFIG).keep)

    def test_contract_employment_type_rejected(self):
        self.assertFalse(evaluate(job(employment_type="CONTRACTOR"), CONFIG).keep)
        self.assertFalse(evaluate(job(employment_type="contract full_time"), CONFIG).keep)

    def test_contract_wording_rejected(self):
        for text in ("C2C only", "6 month contract", "Contract-to-hire role", "1099 OK",
                     "Duration: 12 months"):
            with self.subTest(text=text):
                self.assertFalse(evaluate(job(description=f"{text}. {BENEFITS}"), CONFIG).keep)

    def test_salary_below_minimum_rejected(self):
        self.assertFalse(evaluate(job(salary_min=80000, salary_max=95000), CONFIG).keep)

    def test_range_topping_above_minimum_kept(self):
        self.assertTrue(evaluate(job(salary_min=95000, salary_max=115000), CONFIG).keep)

    def test_unlisted_salary_flagged(self):
        v = evaluate(job(salary_min=None, salary_max=None), CONFIG)
        self.assertTrue(v.keep)
        self.assertIn("salary not listed", v.flags)

    def test_missing_benefits_flagged_or_rejected(self):
        j = job(description="Build Apex and LWC.")
        v = evaluate(j, CONFIG)
        self.assertTrue(v.keep)
        self.assertIn("benefits not mentioned", v.flags)
        strict = {**CONFIG, "benefits": {"require_mention": True}}
        self.assertFalse(evaluate(job(description="Build Apex."), strict).keep)

    def test_hybrid_detected_from_text(self):
        j = job(work_mode="unknown", description=f"Hybrid, 2 days in office. {BENEFITS}")
        self.assertTrue(evaluate(j, CONFIG).keep)
        self.assertEqual(j.work_mode, "hybrid")

    def test_hybrid_location_restriction(self):
        cfg = {**CONFIG, "work_mode": {**CONFIG["work_mode"], "hybrid_locations": ["Austin"]}}
        j = job(work_mode="hybrid", location="Dallas, TX")
        self.assertFalse(evaluate(j, cfg).keep)

    def test_hybrid_outside_st_louis_rejected_by_default(self):
        j = job(work_mode="hybrid", location="Kansas City, MO")
        self.assertFalse(evaluate(j, CONFIG).keep)

    def test_manager_title_kept_and_marked_leadership(self):
        for title in ("Salesforce Development Manager", "Director, Salesforce Engineering",
                      "Head of Salesforce", "Salesforce Engineering Manager"):
            with self.subTest(title=title):
                v = evaluate(job(title=title), CONFIG)
                self.assertTrue(v.keep)
                self.assertTrue(v.leadership)

    def test_direct_reports_in_description_marked_leadership(self):
        j = job(title="Lead Salesforce Developer",
                description=f"You will have 4 direct reports. {BENEFITS}")
        self.assertTrue(evaluate(j, CONFIG).leadership)
        j = job(description=f"Lead a team of 5 developers. {BENEFITS}")
        self.assertTrue(evaluate(j, CONFIG).leadership)

    def test_individual_contributor_not_leadership(self):
        self.assertFalse(evaluate(job(), CONFIG).leadership)

    def test_non_dev_manager_titles_rejected(self):
        for title in ("Salesforce Account Manager", "Salesforce Project Manager",
                      "Salesforce Account Executive"):
            with self.subTest(title=title):
                self.assertFalse(evaluate(job(title=title), CONFIG).keep)

    def test_onsite_rejected(self):
        j = job(work_mode="unknown", description=f"On-site in our office. {BENEFITS}")
        self.assertFalse(evaluate(j, CONFIG).keep)


if __name__ == "__main__":
    unittest.main()
