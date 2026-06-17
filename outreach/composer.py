"""Email composition with template engine and profile-driven personalization."""
from typing import Optional
import re

from core.models import Job
from intelligence.llm import OllamaClient
from enrichment.profile_analyzer import ProfileAnalyzer
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailComposer:
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.profile_analyzer = ProfileAnalyzer()
        github_username = config.YOUR_GITHUB.split("/")[-1] if config.YOUR_GITHUB else None
        if github_username:
            self.profile_analyzer.analyze_github(github_username)
        self.llm: Optional[OllamaClient] = None
        if use_llm:
            try:
                self.llm = OllamaClient()
                if not self.llm.is_available:
                    self.use_llm = False
            except Exception:
                self.use_llm = False

    def compose_initial_email(self, job: Job) -> dict:
        body = self._personalize(self._initial_template(), job)
        return {"to": job.email, "subject": f"Application: {job.role} at {job.company}", "body": body}

    def compose_followup_email(self, job: Job) -> dict:
        template = self._followup_template()
        if self.use_llm and self.llm:
            body = self.llm.personalize_email(job, template, job.hiring_manager)
        else:
            body = self._personalize(template, job)
        return {"to": job.email, "subject": f"Following up: {job.role} at {job.company}", "body": body}

    def _personalize(self, template: str, job: Job) -> str:
        body = template.replace("{role}", job.role)
        body = body.replace("{company}", job.company)
        body = body.replace("{name}", config.YOUR_NAME)
        body = body.replace("{title}", config.YOUR_TITLE)
        body = body.replace("{experience_years}", str(config.YOUR_EXPERIENCE_YEARS))
        body = body.replace("{skills}", ", ".join(config.YOUR_SKILLS[:8]))

        projects = self.profile_analyzer.get_relevant_projects(job.role, job.description, max_projects=2)
        if projects:
            lines = ["Some relevant projects:"]
            for p in projects:
                tech = ", ".join(p.get("tech_stack", [])[:3])
                lines.append(f"• {p['name']}: {p['description'][:70]}... (Tech: {tech})")
            body = body.replace("{relevant_projects}", "\n".join(lines))
        else:
            body = body.replace("{relevant_projects}", "")

        repo_skills = self.profile_analyzer.generate_skill_section(job.role, job.description, max_examples=2)
        body = body.replace("{repo_categories}", repo_skills)

        github_stats = ""
        if self.profile_analyzer.github_data:
            gd = self.profile_analyzer.github_data
            github_stats = f"{gd['public_repos']} repos, {gd['total_stars']} stars"
        body = body.replace("{github_stats}", github_stats)

        portfolio_section = ""
        if config.YOUR_PORTFOLIO and config.YOUR_PORTFOLIO != config.YOUR_GITHUB:
            portfolio_section = f"\n• Portfolio: {config.YOUR_PORTFOLIO}"
        body = body.replace("{portfolio}", portfolio_section)

        past_exp = f"I have {config.YOUR_EXPERIENCE_YEARS} years of professional experience in software engineering." if config.YOUR_EXPERIENCE_YEARS > 0 else ""
        body = body.replace("{past_experience}", past_exp)

        body = body.replace("{additional_context}", "I believe my background aligns well with the role requirements.")
        body = body.replace("{linkedin}", config.YOUR_LINKEDIN)
        body = body.replace("{github}", config.YOUR_GITHUB)

        body = re.sub(r'\n{3,}', '\n\n', body).strip()
        return body

    def _initial_template(self) -> str:
        return """Hi,

I'm {name}, a {title} with {experience_years} years of experience in AI/ML and Full-Stack Engineering.

I came across the {role} position at {company} and wanted to reach out directly.

{relevant_projects}

My GitHub profile shows I've built:
{repo_categories}

My technical background:
• Backend: Python, FastAPI, PostgreSQL, REST APIs, WebSockets
• AI/ML: PyTorch, TensorFlow, LangChain, RAG, LLMs, Fine-tuning
• Full-Stack: React, JavaScript, TypeScript, Docker, CI/CD

{past_experience}

You can view my work:
• GitHub: {github} ({github_stats})
• LinkedIn: {linkedin}{portfolio}

I'd love to discuss how I can contribute to {company}.

Best,
{name}"""

    def _followup_template(self) -> str:
        return """Hi,

I wanted to follow up on my application for the {role} position at {company}.

I remain very interested in this opportunity and would appreciate any update on the hiring process.

{additional_context}

Thank you for your time.

Best,
{name}"""

    def estimate_tokens(self, template: str) -> int:
        return len(template.split())
