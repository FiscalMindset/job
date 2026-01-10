"""Email sender with SMTP and rate limiting."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional
import time

from core.models import Job, EmailStatus
from outreach.composer import EmailComposer
from outreach.resume_handler import ResumeHandler
from outreach.email_validator import EmailValidator
from observability.logger import get_logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text
from rich import box
import config


logger = get_logger(__name__)
console = Console()


class RateLimiter:
    """Simple rate limiter for email sending."""
    
    def __init__(self, max_per_hour: int, max_per_day: int):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.hourly_sends = []
        self.daily_sends = []
    
    def can_send(self) -> bool:
        """Check if we can send an email now."""
        now = datetime.utcnow()
        
        # Clean up old records
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        self.hourly_sends = [t for t in self.hourly_sends if t > hour_ago]
        self.daily_sends = [t for t in self.daily_sends if t > day_ago]
        
        # Check limits
        if len(self.hourly_sends) >= self.max_per_hour:
            logger.warning(f"Hourly limit reached ({self.max_per_hour})")
            return False
        
        if len(self.daily_sends) >= self.max_per_day:
            logger.warning(f"Daily limit reached ({self.max_per_day})")
            return False
        
        return True
    
    def record_send(self) -> None:
        """Record a successful send."""
        now = datetime.utcnow()
        self.hourly_sends.append(now)
        self.daily_sends.append(now)


class EmailSender:
    """
    Send emails via SMTP with rate limiting.
    
    Features:
    - Gmail SMTP support
    - Rate limiting (hourly + daily)
    - Retry logic
    - Send delay to appear human
    """
    
    def __init__(self):
        self.composer = EmailComposer()
        self.resume_handler = ResumeHandler()
        self.rate_limiter = RateLimiter(
            max_per_hour=config.MAX_EMAILS_PER_HOUR,
            max_per_day=config.MAX_EMAILS_PER_DAY
        )
    
    def send_application_email(self, job: Job) -> bool:
        """
        Send initial application email.
        
        Returns:
            True if sent successfully, False otherwise
        """
        # Check if already sent
        if job.email_status == EmailStatus.SENT:
            logger.info(f"Email already sent to {job.company} - {job.role} (skipping duplicate)")
            console.print(f"[yellow]⚠️  Already sent to {job.company} - {job.role}[/yellow]")
            return False
        
        # Validate email address
        is_valid, reason = EmailValidator.is_valid(job.email)
        if not is_valid:
            logger.warning(f"Invalid email {job.email}: {reason}")
            console.print(f"[red]❌ Invalid email for {job.company}: {reason}[/red]")
            job.email_status = EmailStatus.FAILED
            job.error_log = f"Email validation failed: {reason}"
            return False
        
        # Check rate limits
        if not self.rate_limiter.can_send():
            logger.warning(f"Rate limit exceeded, skipping {job.company}")
            return False
        
        # Compose email
        email_data = self.composer.compose_initial_email(job)
        
        # Show email preview and ask for approval
        if not self._get_approval(job, email_data):
            logger.info(f"Email to {job.company} rejected by user")
            job.email_status = EmailStatus.NOT_SENT
            return False
        
        # Send
        success = self._send_email(
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"]
        )
        
        if success:
            self.rate_limiter.record_send()
            job.email_status = EmailStatus.SENT
            
            # Human-like delay
            time.sleep(config.EMAIL_DELAY_SECONDS)
        else:
            job.email_status = EmailStatus.FAILED
        
        return success
    
    def send_followup_email(self, job: Job) -> bool:
        """Send follow-up email."""
        if not self.rate_limiter.can_send():
            return False
        
        email_data = self.composer.compose_followup_email(job)
        
        success = self._send_email(
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"]
        )
        
        if success:
            self.rate_limiter.record_send()
            time.sleep(config.EMAIL_DELAY_SECONDS)
        
        return success
    
    def _send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
            msg["To"] = to
            msg["Subject"] = subject
            
            # Add body (plain text)
            msg.attach(MIMEText(body, "plain"))
            
            # Attach resume if available
            if self.resume_handler.has_resume():
                self.resume_handler.attach_to_email(msg)
                logger.info(f"Resume attached to email for {to}")
            
            # Connect to SMTP server
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
    
    def _get_approval(self, job: Job, email_data: dict) -> bool:
        """Show email preview and ask for user approval."""
        console.print("\n" + "━"*80)
        console.print("\n[bold cyan]    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        console.print("[bold white on blue]         📧 EMAIL APPROVAL REQUIRED         [/bold white on blue]")
        console.print("[bold cyan]    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n")
        
        # Job Details Table
        job_table = Table(
            show_header=False,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1)
        )
        job_table.add_column("Field", style="bold yellow", width=20)
        job_table.add_column("Value", style="white", width=55)
        
        score_color = 'green' if job.score >= 75 else 'yellow' if job.score >= 50 else 'red'
        job_table.add_row("🏢 Company", job.company)
        job_table.add_row("💼 Role", job.role)
        job_table.add_row("📍 Location", job.location)
        job_table.add_row("📊 Match Score", f"{job.score}/100")
        job_table.add_row("🔗 Job URL", job.job_url[:60] + "..." if len(job.job_url) > 60 else job.job_url)
        
        job_panel = Panel(
            job_table,
            title="[bold magenta]🎯 Job Details[/bold magenta]",
            border_style="magenta",
            box=box.DOUBLE
        )
        console.print(job_panel)
        console.print()
        
        # Email Metadata Table
        email_table = Table(
            show_header=False,
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 1)
        )
        email_table.add_column("Field", style="bold yellow", width=20)
        email_table.add_column("Value", style="white", width=55)
        
        email_table.add_row("📨 To", email_data['to'])
        email_table.add_row("📝 Subject", email_data['subject'])
        resume_status = f"✅ Resume attached ({config.YOUR_RESUME.split('/')[-1]})" if self.resume_handler.has_resume() else "❌ No resume"
        email_table.add_row("📎 Attachments", resume_status)
        
        email_panel = Panel(
            email_table,
            title="[bold green]📧 Email Metadata[/bold green]",
            border_style="green",
            box=box.DOUBLE
        )
        console.print(email_panel)
        console.print()
        
        # Email Body Preview
        body_preview = email_data['body']
        if len(body_preview) > 600:
            body_preview = body_preview[:600] + "\n\n[dim]... (email continues)[/dim]"
        
        body_panel = Panel(
            f"[white]{body_preview}[/white]",
            title="[bold blue]📄 Email Body Preview[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        console.print(body_panel)
        console.print()
        
        # Footer
        footer_text = Text()
        footer_text.append("━" * 80 + "\n", style="bold cyan")
        console.print(footer_text)
        
        return Confirm.ask(
            f"\n[bold yellow]✉️  Send this email to {job.company}?[/bold yellow]",
            default=True
        )

