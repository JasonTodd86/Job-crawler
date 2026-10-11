"""Builds the daily email: an HTML version for reading, a plain-text fallback."""
from html import escape

from .filters import Verdict
from .models import Job

Match = tuple[Job, Verdict]


def fmt_pay(job: Job) -> str:
    lo, hi = job.salary_min, job.salary_max
    if lo is None and hi is None:
        return "Pay not listed"
    if lo and hi and lo != hi:
        return f"${lo:,.0f} – ${hi:,.0f}"
    return f"${(hi or lo):,.0f}"


def subject(matches: list[Match], day: str) -> str:
    n = len(matches)
    if n == 0:
        return f"No new Salesforce jobs today ({day})"
    return f"{n} new Salesforce job{'s' if n != 1 else ''} ({day})"


def _badges(job: Job, verdict: Verdict) -> str:
    return ("⭐ " if verdict.leadership else "") + ("✅ " if job.from_employer else "")


def plain_text(matches: list[Match], day: str, problems: list[str]) -> str:
    lines = [subject(matches, day), ""]
    for job, verdict in matches:
        lines += [
            f"{_badges(job, verdict)}{job.title}",
            f"  {job.company} · {job.location or 'location not listed'} · {job.work_mode}",
            f"  {fmt_pay(job)} · found on {job.source}",
            f"  {job.url}",
        ]
        if verdict.notes:
            lines.append(f"  Note: {'; '.join(verdict.notes)}")
        lines.append("")
    lines += ["⭐ = manager role or direct reports. ✅ = posted on the employer's own careers site.", ""]
    if problems:
        lines += ["Problems this run:"] + [f"  - {p}" for p in problems]
    return "\n".join(lines)


def html(matches: list[Match], day: str, problems: list[str]) -> str:
    cards = []
    for job, verdict in matches:
        notes = (f'<div style="color:#8a5a00;font-size:13px;margin-top:6px">⚠️ '
                 f'{escape("; ".join(verdict.notes))}</div>') if verdict.notes else ""
        cards.append(f"""
<div style="border:1px solid #ddd;border-radius:8px;padding:14px 16px;margin:0 0 12px">
  <div style="font-size:17px;font-weight:600">{_badges(job, verdict)}<a href="{escape(job.url)}"
    style="color:#0b5cad;text-decoration:none">{escape(job.title)}</a></div>
  <div style="margin-top:4px">{escape(job.company)} · {escape(job.location or "location not listed")}
    · {escape(job.work_mode)}</div>
  <div style="margin-top:4px;color:#444">{escape(fmt_pay(job))} · found on {escape(job.source)}</div>
  {notes}
</div>""")
    if not cards:
        cards.append('<p>Nothing new matched your criteria today. The search ran normally.</p>')
    trouble = ""
    if problems:
        items = "".join(f"<li>{escape(p)}</li>" for p in problems)
        trouble = (f'<h3 style="font-size:15px;margin-top:24px">Problems this run</h3>'
                   f'<ul style="color:#555;font-size:13px">{items}</ul>')
    return f"""<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#222;
  max-width:640px;margin:0 auto;padding:16px">
<h2 style="font-size:20px">{escape(subject(matches, day))}</h2>
{''.join(cards)}
<p style="color:#666;font-size:13px">⭐ = manager role or direct reports.
  ✅ = posted on the employer's own careers site, so it's a real opening.<br>
  For other jobs, check the company's own careers page before applying.</p>
{trouble}
<p style="color:#999;font-size:12px">Change what you get by editing criteria.yaml in the Job-crawler repo.</p>
</body></html>"""
