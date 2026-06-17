"""Email sender with SMTP, rate limiting, retry queue, and user approval."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List
import time
import json
from pathlib import Path

from core.models import Job, EmailStatus
from outreach.composer import EmailComposer
from outreach.resume_handler import ResumeHandler
from outreach.email_validator import EmailValidator
from observability.logger import get_logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import config


logger = get_logger(__name__)
console = Console()


class RateLimiter:
    def __init__(self, max_per_hour: int, max_per_day: int):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.hourly: List[datetime] = []
        self.daily: List[datetime] = []

    def can_send(self) -> bool:
        now = datetime.utcnow()
        self.hourly = [t for t in self.hourly if t > now - timedelta(hours=1)]
        self.daily = [t for t in self.daily if t > now - timedelta(days=1)]
        if len(self.hourly) >= self.max_per_hour:
            logger.warning(f"Hourly limit reached ({self.max_per_hour})")
            return False
        if len(self.daily) >= self.max_per_day:
            logger.warning(f"Daily limit reached ({self.max_per_day})")
            return False
        return True

    def record_send(self) -> None:
        now = datetime.utcnow()
        self.hourly.append(now)
        self.daily.append(now)

    @property
    def remaining_hourly(self) -> int:
        return self.max_per_hour - len([t for t in self.hourly if t > datetime.utcnow() - timedelta(hours=1)])

    @property
    def remaining_daily(self) -> int:
        return self.max_per_day - len([t for t in self.daily if t > datetime.utcnow() - timedelta(days=1)])


class SendQueue:
    def __init__(self, path: Path = config.DATA_DIR / "send_queue.json"):
        self.path = path
        self._queue: List[str] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._queue = data.get("queue", [])
            except (json.JSONDecodeError, KeyError):
                self._queue = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"queue": self._queue, "updated_at": datetime.utcnow().isoformat()}))

    def add(self, job_id: str) -> None:
        if job_id not in self._queue:
            self._queue.append(job_id)
            self._save()

    def remove(self, job_id: str) -> None:
        if job_id in self._queue:
            self._queue.remove(job_id)
            self._save()

    @property
    def pending(self) -> List[str]:
        return list(self._queue)

    def clear(self) -> None:
        self._queue = []
        self._save()


class EmailSender:
    def __init__(self):
        self.composer = EmailComposer()
        self.resume_handler = ResumeHandler()
        self.rate_limiter = RateLimiter(
            max_per_hour=config.MAX_EMAILS_PER_HOUR,
            max_per_day=config.MAX_EMAILS_PER_DAY,
        )
        self.send_queue = SendQueue()

    def send_application_email(self, job: Job) -> bool:
        if job.email_status == EmailStatus.SENT:
            logger.info(f"Already sent to {job.company} - {job.role}")
            console.print(f"[yellow]⚠️  Already sent to {job.company} - {job.role}[/yellow]")
            return False

        valid, reason = EmailValidator.is_valid(job.email)
        if not valid:
            logger.warning(f"Invalid email {job.email}: {reason}")
            console.print(f"[red]❌ Invalid email for {job.company}: {reason}[/red]")
            job.email_status = EmailStatus.FAILED
            job.error_log = f"Email validation failed: {reason}"
            return False

        if not self.rate_limiter.can_send():
            logger.warning("Rate limit exceeded")
            self.send_queue.add(job.job_id)
            console.print(f"[yellow]⏳ Queued {job.company} — rate limit reached ({self.rate_limiter.remaining_hourly}/hr remaining)[/yellow]")
            return False

        email_data = self.composer.compose_initial_email(job)
        if not self._get_approval(job, email_data):
            logger.info(f"Email to {job.company} rejected")
            job.email_status = EmailStatus.NOT_SENT
            return False

        success = self._send_email(
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"],
        )
        if success:
            self.rate_limiter.record_send()
            self.send_queue.remove(job.job_id)
            job.email_status = EmailStatus.SENT
            console.print(f"[green]✓ Email sent to {job.company} ({self.rate_limiter.remaining_hourly}/{config.MAX_EMAILS_PER_HOUR} hr remaining)[/green]")
            time.sleep(config.EMAIL_DELAY_SECONDS)
        else:
            job.email_status = EmailStatus.FAILED
            self.send_queue.add(job.job_id)
        return success

    def send_followup_email(self, job: Job) -> bool:
        if not self.rate_limiter.can_send():
            return False
        email_data = self.composer.compose_followup_email(job)
        success = self._send_email(
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"],
        )
        if success:
            self.rate_limiter.record_send()
            time.sleep(config.EMAIL_DELAY_SECONDS)
        return success

    def retry_queue(self) -> int:
        if not self.send_queue.pending:
            console.print("[green]No pending emails in queue[/green]")
            return 0
        console.print(f"[yellow]Retrying {len(self.send_queue.pending)} queued emails...[/yellow]")
        sent = 0
        for job_id in list(self.send_queue.pending):
            if not self.rate_limiter.can_send():
                break
            console.print(f"  Skipping queued job {job_id[:8]}... (retry logic not wired to Job objects)")
            self.send_queue.remove(job_id)
        return sent

    def _send_email(self, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            if self.resume_handler.has_resume():
                self.resume_handler.attach_to_email(msg)
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed — check SMTP_USERNAME and SMTP_PASSWORD")
            console.print("[red]❌ SMTP authentication failed. Check your Gmail app password.[/red]")
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.error(f"Recipient refused: {to}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    def _get_approval(self, job: Job, email_data: dict) -> bool:
        console.print(Panel(
            f"[bold cyan]✉️  Send to {job.company}?[/bold cyan]\n\n"
            f"[yellow]To:[/yellow] {email_data['to']}\n"
            f"[yellow]Subject:[/yellow] {email_data['subject']}\n"
            f"[yellow]Score:[/yellow] {job.score}/100\n"
            f"[yellow]Rate Limit:[/yellow] {self.rate_limiter.remaining_hourly}/{config.MAX_EMAILS_PER_HOUR} hr | {self.rate_limiter.remaining_daily}/{config.MAX_EMAILS_PER_DAY} day",
            border_style="cyan",
        ))
        choice = Prompt.ask(
            f"\n[bold yellow]Send to {job.company}?[/bold yellow]",
            choices=["y", "n", "p", "?"],
            default="y",
        )
        if choice == "?":
            console.print(Panel(f"[white]{email_data['body'][:800]}[/white]", title="Email Preview", border_style="blue"))
            choice = Prompt.ask(f"[bold yellow]Send to {job.company}?[/bold yellow]", choices=["y", "n"], default="y")
        if choice == "p":
            console.print("[yellow]⏸️  Pipeline paused. Resume with 'y' next time.[/yellow]")
        return choice == "y"
