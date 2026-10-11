"""Sends the digest through Gmail using an app password.

Env: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and optionally EMAIL_TO (defaults to
GMAIL_ADDRESS; separate several addresses with commas).
"""
import os
import smtplib
from email.message import EmailMessage


def send(subject: str, text: str, html: str) -> None:
    missing = [name for name in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD") if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Email not sent: add {' and '.join(missing)} under the repo's "
                         "Settings → Secrets and variables → Actions (see README).")
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")  # Google shows it in groups of 4
    to = os.environ.get("EMAIL_TO") or sender

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
