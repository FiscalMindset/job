"""Email composition and personalization."""
from typing import Optional
from datetime import datetime

from core.models import Job
from intelligence.llm import OllamaClient
from enrichment.profile_analyzer import ProfileAnalyzer
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailComposer:
    """
    Compose personalized job application emails.
    
    Philosophy:
    - Be specific to company and role
    - Avoid AI-sounding phrases
    - Keep it professional but human
    - Reference real achievements
    - Never spam
    """
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.profile_analyzer = ProfileAnalyzer()
        
        # Analyze GitHub profile on init
        github_username = config.YOUR_GITHUB.split('/')[-1] if config.YOUR_GITHUB else None
        if github_username:
            self.profile_analyzer.analyze_github(github_username)
        
        if use_llm:
            try:
                self.llm = OllamaClient()
            except:
                logger.warning("LLM unavailable for email personalization")
                self.use_llm = False
    
    def compose_initial_email(self, job: Job) -> dict:
        """
        Compose initial application email.
        
        Returns:
            Dict with keys: subject, body, to
        """
        # Get base template
        template = self._get_template("initial")
        
        # Always use template personalization (LLM can be added later)
        body = self._personalize_template(template, job)
        
        # Create subject
        subject = f"Application: {job.role} at {job.company}"
        
        return {
            "to": job.email,
            "subject": subject,
            "body": body
        }
    
    def compose_followup_email(self, job: Job) -> dict:
        """Compose follow-up email."""
        template = self._get_template("followup")
        
        if self.use_llm:
            body = self.llm.personalize_email(
                job=job,
                template=template,
                hiring_manager=job.hiring_manager
            )
        else:
            body = self._personalize_template(template, job)
        
        subject = f"Following up: {job.role} at {job.company}"
        
        return {
            "to": job.email,
            "subject": subject,
            "body": body
        }
    
    def _get_template(self, template_type: str) -> str:
        """Get email template."""
        if template_type == "initial":
            return self._initial_template()
        elif template_type == "followup":
            return self._followup_template()
        else:
            raise ValueError(f"Unknown template type: {template_type}")
    
    def _initial_template(self) -> str:
        """Initial application email template."""
        portfolio_section = f"\n• Portfolio: {config.YOUR_PORTFOLIO}" if config.YOUR_PORTFOLIO and config.YOUR_PORTFOLIO != config.YOUR_GITHUB else ""
        
        return f"""Hi,

I'm {config.YOUR_NAME}, a {config.YOUR_TITLE} with {config.YOUR_EXPERIENCE_YEARS} years of experience in AI/ML and Full-Stack Engineering.

I came across the {{{{role}}}} position at {{{{company}}}} and wanted to reach out directly.

{{{{relevant_projects}}}}

My technical background:
• Backend: Python, FastAPI, PostgreSQL, REST APIs, WebSockets
• AI/ML: PyTorch, TensorFlow, LangChain, RAG, LLMs, Fine-tuning
• Full-Stack: React, JavaScript, TypeScript, Docker, CI/CD

{{{{past_experience}}}}

You can view my work:
• GitHub: {config.YOUR_GITHUB} ({{{{github_stats}}}})
• LinkedIn: {config.YOUR_LINKEDIN}{portfolio_section}

I'd love to discuss how I can contribute to {{{{company}}}}.

Best,
{config.YOUR_NAME}"""
    
    def _followup_template(self) -> str:
        """Follow-up email template."""
        return f"""Hi,

I wanted to follow up on my application for the {{role}} position at {{company}}.

I remain very interested in this opportunity and would appreciate any update on the hiring process.

{{additional_context}}

Thank you for your time.

Best,
{config.YOUR_NAME}"""
    
    def _personalize_template(self, template: str, job: Job) -> str:
        """Simple template personalization without LLM."""
        # Replace placeholders
        body = template.replace("{{role}}", job.role)
        body = body.replace("{{company}}", job.company)
        
        # Get relevant projects
        relevant_projects = self.profile_analyzer.get_relevant_projects(
            job.role, 
            job.description, 
            max_projects=2
        )
        
        # Format projects
        if relevant_projects:
            project_text = "Some relevant projects:\n"
            for project in relevant_projects:
                tech = ", ".join(project.get('tech_stack', [])[:3])
                project_text += f"• {project['name']}: {project['description'][:70]}... (Tech: {tech})\n"
            body = body.replace("{{relevant_projects}}", project_text)
        else:
            body = body.replace("{{relevant_projects}}", "")
        
        # GitHub stats
        github_stats = ""
        if self.profile_analyzer.github_data:
            github_stats = f"{self.profile_analyzer.github_data['public_repos']} repos, {self.profile_analyzer.github_data['total_stars']} stars"
        body = body.replace("{{github_stats}}", github_stats)
        
        # Past experience
        past_exp = self._extract_past_experience()
        body = body.replace("{{past_experience}}", past_exp)
        
        # Additional context for follow-up
        body = body.replace(
            "{{additional_context}}",
            "I believe my background aligns well with the role requirements."
        )
        
        return body
    
    def _extract_past_experience(self) -> str:
        """Extract past work experience if available."""
        # This could extract from resume PDF in future
        # For now, return empty or add to config
        if config.YOUR_EXPERIENCE_YEARS > 0:
            return f"I have {config.YOUR_EXPERIENCE_YEARS} years of professional experience in software engineering.\n"
        return ""
