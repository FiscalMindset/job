"""Email notifications for pipeline completion and errors."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from core.models import PipelineResult, Decision
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailNotifier:
    """Send email notifications about pipeline execution."""
    
    def __init__(self):
        self.enabled = config.SEND_COMPLETION_EMAIL
    
    def send_completion_notification(self, result: PipelineResult) -> None:
        """Send email notification when pipeline completes."""
        if not self.enabled:
            return
        
        try:
            subject = f"✅ Job Intelligence OS - {result.emails_sent} Applications Sent ({result.jobs_collected} Jobs Found)"
            body = self._format_completion_email(result)
            
            self._send_email(
                to=config.SMTP_USERNAME,
                subject=subject,
                body=body,
                is_html=True
            )
            
            logger.info("Completion notification sent")
            
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")
    
    def send_error_notification(self, error: str) -> None:
        """Send email notification when pipeline fails."""
        if not config.NOTIFY_ON_ERRORS:
            return
        
        try:
            subject = "Job Intelligence OS - Error Alert"
            body = f"""Job Intelligence OS encountered an error:

Error: {error}

Time: {datetime.utcnow().isoformat()}

Please check the logs at: {config.LOG_FILE}
"""
            
            self._send_email(
                to=config.SMTP_USERNAME,
                subject=subject,
                body=body
            )
            
            logger.info("Error notification sent")
            
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    def _format_completion_email(self, result: PipelineResult) -> str:
        """Format completion email body with HTML styling."""
        # Calculate success rate
        total_decisions = sum(result.decisions_made.values())
        apply_count = result.decisions_made.get(Decision.APPLY, 0) + result.decisions_made.get(Decision.APPLY_LATER, 0)
        success_rate = (apply_count / total_decisions * 100) if total_decisions > 0 else 0
        
        # Format job details with URLs and reasons
        jobs_html = self._format_detailed_jobs_html(result.all_jobs) if result.all_jobs else "<p style='color: #6c757d; text-align: center;'>No jobs collected this run</p>"
        
        # Build HTML email
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; }}
        .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; }}
        .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #6c757d; font-size: 14px; margin-top: 5px; }}
        .decision-box {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ffc107; }}
        .decision-item {{ padding: 8px 0; display: flex; justify-content: space-between; border-bottom: 1px solid #eee; }}
        .decision-item:last-child {{ border-bottom: none; }}
        .sources {{ background: #d1ecf1; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #17a2b8; }}
        .footer {{ text-align: center; padding: 20px; color: #6c757d; font-size: 12px; }}
        .success-rate {{ font-size: 48px; font-weight: bold; color: #28a745; text-align: center; margin: 20px 0; }}
        .job-card {{ background: #f8f9fa; border-left: 4px solid #667eea; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .job-card.apply {{ border-left-color: #28a745; background: #d4edda; }}
        .job-card.skip {{ border-left-color: #dc3545; background: #f8d7da; }}
        .job-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; }}
        .job-company {{ font-size: 16px; color: #667eea; margin-bottom: 10px; }}
        .job-meta {{ font-size: 13px; color: #6c757d; margin-bottom: 10px; }}
        .job-reason {{ background: white; padding: 10px; border-radius: 4px; margin-top: 10px; font-size: 13px; line-height: 1.5; }}
        .job-link {{ display: inline-block; background: #667eea; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-top: 10px; font-size: 13px; }}
        .job-link:hover {{ background: #5568d3; }}
        .score-badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
        .score-high {{ background: #28a745; color: white; }}
        .score-medium {{ background: #ffc107; color: #333; }}
        .score-low {{ background: #dc3545; color: white; }}
        .section-title {{ font-size: 20px; font-weight: bold; color: #333; margin-top: 30px; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Job Intelligence OS - Complete!</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Pipeline execution finished successfully</p>
        </div>
        
        <div class="content">
            <div class="success-rate">{success_rate:.1f}%</div>
            <p style="text-align: center; color: #6c757d; margin-top: -10px;">Application Success Rate</p>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{result.jobs_collected}</div>
                    <div class="stat-label">Jobs Found</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{result.emails_sent}</div>
                    <div class="stat-label">Emails Sent</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{result.jobs_deduplicated}</div>
                    <div class="stat-label">New Jobs</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{result.duration_seconds:.1f}s</div>
                    <div class="stat-label">Execution Time</div>
                </div>
            </div>
            
            <div class="decision-box">
                <h3 style="margin-top: 0; color: #856404;">📋 Decisions Made</h3>
                {self._format_decisions_html(result.decisions_made)}
            </div>
            
            <div class="sources">
                <h3 style="margin-top: 0; color: #0c5460;">📍 Sources</h3>
                {self._format_sources_html(result.source_stats)}
            </div>
            
            <div class="section-title">📋 All Jobs Found ({len(result.all_jobs)})</div>
            {jobs_html}
            
            <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #6c757d;">
                <strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
                <strong>Errors:</strong> {result.errors}
            </p>
        </div>
        
        <div class="footer">
            Job Intelligence Operating System v1.0<br>
            Autonomous Job Application Platform
        </div>
    </div>
</body>
</html>
        """
        
        return html
    
    def _format_detailed_jobs_html(self, jobs: list) -> str:
        """Format all jobs with URLs and reasons why to apply."""
        if not jobs:
            return "<p>No jobs found</p>"
        
        html = ""
        
        # Group jobs by decision
        apply_jobs = [j for j in jobs if j.decision == Decision.APPLY]
        other_jobs = [j for j in jobs if j.decision != Decision.APPLY]
        
        # Show APPLY jobs first
        if apply_jobs:
            html += "<h3 style='color: #28a745; margin-top: 20px;'>✅ RECOMMENDED TO APPLY ({} jobs)</h3>".format(len(apply_jobs))
            for job in apply_jobs[:30]:  # Limit to 30 to avoid huge emails
                score_class = "score-high" if job.score >= 75 else "score-medium" if job.score >= 50 else "score-low"
                
                # Truncate reason if too long
                reason = job.reason[:300] if job.reason else "Good match based on your skills and experience"
                if len(job.reason or "") > 300:
                    reason += "..."
                
                html += f"""
                <div class="job-card apply">
                    <div class="job-title">{job.role}</div>
                    <div class="job-company">🏢 {job.company}</div>
                    <div class="job-meta">
                        📍 {job.location} | 
                        <span class="score-badge {score_class}">Match: {job.score}%</span>
                    </div>
                    <div class="job-reason">
                        <strong>💡 Why you should apply:</strong><br>
                        {reason}
                    </div>
                    <a href="{job.job_url}" class="job-link" target="_blank">🔗 View Job & Apply</a>
                </div>
                """
            
            if len(apply_jobs) > 30:
                html += f"<p style='color: #6c757d; text-align: center; margin: 20px 0;'><em>... and {len(apply_jobs) - 30} more APPLY jobs (check CSV for full list)</em></p>"
        
        # Show other jobs (SKIP, WATCH, etc.) - condensed
        if other_jobs and len(other_jobs) <= 20:
            html += "<h3 style='color: #6c757d; margin-top: 30px;'>📌 Other Jobs Found ({} jobs)</h3>".format(len(other_jobs))
            for job in other_jobs[:20]:
                decision_emoji = {"APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(job.decision.value, "")
                score_class = "score-high" if job.score >= 75 else "score-medium" if job.score >= 50 else "score-low"
                
                reason = job.reason[:200] if job.reason else "Review manually"
                if len(job.reason or "") > 200:
                    reason += "..."
                
                html += f"""
                <div class="job-card skip">
                    <div class="job-title">{job.role} {decision_emoji}</div>
                    <div class="job-company">🏢 {job.company}</div>
                    <div class="job-meta">
                        📍 {job.location} | 
                        <span class="score-badge {score_class}">{job.score}%</span> |
                        Decision: {job.decision.value}
                    </div>
                    <div class="job-reason" style="background: #fff; font-size: 12px;">
                        {reason}
                    </div>
                    <a href="{job.job_url}" class="job-link" style="background: #6c757d;" target="_blank">View Job</a>
                </div>
                """
        elif other_jobs:
            html += f"<p style='color: #6c757d; text-align: center; margin: 20px 0;'><em>Plus {len(other_jobs)} other jobs (SKIP/WATCH) - see CSV for details</em></p>"
        
        return html
    
    def _format_decisions_html(self, decisions: dict) -> str:
        """Format decisions as HTML."""
        emojis = {
            "APPLY": "✅",
            "APPLY_LATER": "⏰",
            "WATCH": "👀",
            "SKIP": "⏭️"
        }
        
        html = ""
        for decision, count in decisions.items():
            emoji = emojis.get(decision.value, "")
            html += f'<div class="decision-item"><span>{emoji} {decision.value}</span><strong>{count}</strong></div>'
        
        return html
    
    def _format_sources_html(self, sources: dict) -> str:
        """Format sources as HTML."""
        html = ""
        for source, count in sources.items():
            html += f'<div class="decision-item"><span>{source}</span><strong>{count} jobs</strong></div>'
        
        return html
    
    def _send_email(self, to: str, subject: str, body: str, is_html: bool = False) -> None:
        """Send email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        
        if is_html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
