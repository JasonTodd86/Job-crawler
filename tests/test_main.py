import unittest
from pathlib import Path
from unittest import mock

import yaml

from jobmail import digest, main, mailer
from jobmail.models import Job

CRITERIA = yaml.safe_load((Path(__file__).resolve().parent.parent / "criteria.yaml").read_text())


def job(**overrides) -> Job:
    base = dict(source="Remotive", source_id="1", title="Salesforce Developer", company="Acme",
                location="USA", url="https://example.com", work_mode="remote",
                salary_min=110000, salary_max=130000)
    base.update(overrides)
    return Job(**base)


class MatchTests(unittest.TestCase):
    def test_already_emailed_jobs_left_out(self):
        jobs = [job(), job(company="Beta", source_id="2")]
        matches = main.find_matches(jobs, CRITERIA, {"acme|salesforce developer": "2026-10-01"}, False)
        self.assertEqual([j.company for j, _ in matches], ["Beta"])

    def test_employer_copy_wins_and_sorts_first(self):
        jobs = [job(company="Acme", from_employer=True, source="Acme careers site"),
                job(company="Acme Inc.", source="Remotive"),
                job(company="Beta", title="Salesforce Engineer", salary_max=200000)]
        matches = main.find_matches(jobs, CRITERIA, {}, False)
        self.assertEqual([j.source for j, _ in matches], ["Acme careers site", "Remotive"])

    def test_leadership_sorts_first(self):
        jobs = [job(), job(title="Salesforce Development Manager", company="Beta")]
        matches = main.find_matches(jobs, CRITERIA, {}, False)
        self.assertEqual(matches[0][0].company, "Beta")

    def test_mass_posting_flagged(self):
        jobs = [job(location=f"Remote - US {i}", source_id=str(i)) for i in range(6)]
        (_, verdict), = main.find_matches(jobs, CRITERIA, {}, False)
        self.assertTrue(any("6 cities" in n for n in verdict.notes))


class DigestTests(unittest.TestCase):
    def test_email_contents(self):
        matches = main.find_matches([job(title="Salesforce Dev <Lead>", salary_max=None,
                                         salary_min=None)], CRITERIA, {}, False)
        page = digest.html(matches, "Sun Oct 11", ["jobicy job board: couldn't load (OSError)"])
        self.assertIn("Salesforce Dev &lt;Lead&gt;", page)
        self.assertIn("pay not listed", page)
        self.assertIn("Problems this run", page)
        self.assertEqual(digest.subject(matches, "Sun Oct 11"), "1 new Salesforce job (Sun Oct 11)")
        self.assertIn("https://example.com", digest.plain_text(matches, "Sun Oct 11", []))

    def test_empty_day(self):
        self.assertIn("Nothing new", digest.html([], "Sun Oct 11", []))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        patches = [
            mock.patch.object(main, "SOURCES", [mock.Mock(fetch=lambda c, p: [job()])]),
            mock.patch.object(main, "load_seen", return_value={}),
            mock.patch.object(main, "save_seen", side_effect=self.saved.update),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_sends_then_remembers(self):
        with mock.patch.object(mailer, "send") as send:
            main.run(main.ROOT / "criteria.yaml", preview=False, include_seen=False)
        self.assertTrue(send.call_args.args[0].startswith("1 new Salesforce job"))
        self.assertIn("acme|salesforce developer", self.saved)

    def test_failed_send_does_not_mark_jobs_seen(self):
        with mock.patch.object(mailer, "send", side_effect=OSError("smtp down")):
            with self.assertRaises(OSError):
                main.run(main.ROOT / "criteria.yaml", preview=False, include_seen=False)
        self.assertEqual(self.saved, {})


class MailerTests(unittest.TestCase):
    def test_gmail_login_and_send(self):
        env = {"GMAIL_ADDRESS": "me@gmail.com", "GMAIL_APP_PASSWORD": "abcd efgh ijkl mnop"}
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("smtplib.SMTP_SSL") as smtp:
            mailer.send("Subject", "text", "<p>html</p>")
        conn = smtp.return_value.__enter__.return_value
        conn.login.assert_called_once_with("me@gmail.com", "abcdefghijklmnop")
        self.assertEqual(conn.send_message.call_args.args[0]["To"], "me@gmail.com")

    def test_missing_secrets_explained(self):
        with mock.patch.dict("os.environ", {"GMAIL_ADDRESS": "me@gmail.com"}, clear=True):
            with self.assertRaises(SystemExit) as caught:
                mailer.send("Subject", "text", "<p>html</p>")
        self.assertIn("GMAIL_APP_PASSWORD", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
