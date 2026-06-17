"""Multi-channel notifications: email, and webhook-capable framework."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from core.models import PipelineResult, Decision
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailNotifier:
    def __init__(self):
        self.enabled = config.SEND_COMPLETION_EMAIL

    def send_completion_notification(self, result: PipelineResult) -> None:
        if not self.enabled:
            return
        try:
            subject = f"✅ Job OS — {result.emails_sent} Sent ({result.jobs_collected} Jobs)"
            self._send_email(
                to=config.SMTP_USERNAME,
                subject=subject,
                body=self._format_completion(result),
                is_html=True,
            )
            logger.info("Completion notification sent")
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")

    def send_error_notification(self, error: str) -> None:
        if not config.NOTIFY_ON_ERRORS:
            return
        try:
            self._send_email(
                to=config.SMTP_USERNAME,
                subject="❌ Job OS — Error",
                body=f"Error: {error}\nTime: {datetime.utcnow().isoformat()}\nLogs: {config.LOG_FILE}",
            )
            logger.info("Error notification sent")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    def _format_completion(self, result: PipelineResult) -> str:
        total = sum(result.decisions_made.values())
        applies = result.decisions_made.get(Decision.APPLY, 0)
        rate = (applies / total * 100) if total else 0
        dec_html = ""
        for d, c in result.decisions_made.items():
            emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(d.value, "")
            dec_html += f"<tr><td>{emoji} {d.value}</td><td style='text-align:right;font-weight:bold'>{c}</td></tr>"
        src_html = ""
        for s, c in result.source_stats.items():
            src_html += f"<tr><td>{s}</td><td style='text-align:right'>{c}</td></tr>"
        timing_html = ""
        for p, t in result.phase_timings.items():
            timing_html += f"<tr><td>{p}</td><td style='text-align:right'>{t:.1f}s</td></tr>"

        return f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:600px;margin:auto;background:white;border-radius:10px;overflow:hidden">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;text-align:center">
<h1 style="margin:0">🚀 Job OS Complete</h1>
<p style="margin:5px 0 0;opacity:.9">{result.jobs_collected} jobs in {result.duration_seconds:.1f}s</p></div>
<div style="padding:30px">
<div style="font-size:48px;font-weight:bold;color:#28a745;text-align:center">{rate:.0f}%</div>
<p style="text-align:center;color:#666">Application Success Rate</p>
<table style="width:100%;border-collapse:collapse;margin:20px 0">
<tr><td style="padding:10px;background:#f8f9fa;border-radius:5px"><b>Jobs Found</b><br><span style="font-size:24px;font-weight:bold;color:#667eea">{result.jobs_collected}</span></td>
<td style="padding:10px;background:#f8f9fa;border-radius:5px"><b>Emails Sent</b><br><span style="font-size:24px;font-weight:bold;color:#28a745">{result.emails_sent}</span></td></tr>
</table>
<h3>📋 Decisions</h3>
<table style="width:100%">{dec_html}</table>
<h3>📍 Sources</h3>
<table style="width:100%">{src_html}</table>
{"<h3>⏱️ Timings</h3><table style='width:100%'>" + timing_html + "</table>" if timing_html else ""}
<p style="color:#666;font-size:12px;margin-top:30px">
📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}<br>
⚠️ Errors: {result.errors}</p></div></div></body></html>"""

    def _send_email(self, to: str, subject: str, body: str, is_html: bool = False) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html" if is_html else "plain"))
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
