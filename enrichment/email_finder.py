"""Email finder - discover contact emails for companies."""
import httpx
import re
import urllib.parse
from typing import Optional, Dict, Any

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailFinder:
    """
    Find hiring contact emails for companies.
    
    Strategies (in order):
    1. Extract domain from job URL (most reliable)
    2. Try common patterns with domain verification
    3. Search company website for contact emails
    4. Scrape job page for emails
    5. LLM-powered domain discovery (fallback)
    """
    
    KNOWN_DOMAINS = {
        "notion": "notion.so",
        "stripe": "stripe.com",
        "figma": "figma.com",
        "linear": "linear.app",
        "vercel": "vercel.com",
        "anthropic": "anthropic.com",
        "openai": "openai.com",
        "google": "google.com",
        "meta": "meta.com",
        "apple": "apple.com",
        "microsoft": "microsoft.com",
        "amazon": "amazon.com",
        "netflix": "netflix.com",
        "spotify": "spotify.com",
        "slack": "slack.com",
        "airbnb": "airbnb.com",
        "uber": "uber.com",
        "lyft": "lyft.com",
        "doordash": "doordash.com",
        "instacart": "instacart.com",
        "datadog": "datadoghq.com",
        "hashicorp": "hashicorp.com",
        "elastic": "elastic.co",
        "mongodb": "mongodb.com",
        "snowflake": "snowflake.com",
        "cloudflare": "cloudflare.com",
        "github": "github.com",
        "gitlab": "gitlab.com",
        "docker": "docker.com",
        "kubernetes": "kubernetes.io",
        "sentry": "sentry.io",
        "vercel": "vercel.com",
        "netlify": "netlify.com",
        "railway": "railway.app",
        "render": "render.com",
        "fly": "fly.io",
        "replit": "replit.com",
        "cursor": "cursor.com",
        "warp": "warp.dev",
        "perplexity": "perplexity.ai",
        "midjourney": "midjourney.com",
        "character.ai": "character.ai",
    }
    
    CAREER_PAGE_COMPANIES = {
        "notion": "https://www.notion.so/careers",
        "stripe": "https://stripe.com/jobs",
        "figma": "https://www.figma.com/careers",
        "linear": "https://linear.app/careers",
        "vercel": "https://vercel.com/careers",
        "anthropic": "https://www.anthropic.com/careers",
    }
    
    def __init__(self):
        self.client = httpx.Client(timeout=15.0)
    
    def find_email(self, job: Job) -> Optional[Dict[str, Any]]:
        company_key = job.company.lower().strip()
        if company_key in self.CAREER_PAGE_COMPANIES:
            logger.info(f"{job.company} uses career page applications only: {self.CAREER_PAGE_COMPANIES[company_key]}")
            return None
        
        domain = self._discover_domain(job)
        if not domain:
            logger.warning(f"No email found for {job.company}")
            return None
        
        email = self._try_common_patterns(domain)
        if email:
            return {"email": email, "confidence": 0.7, "name": "Hiring Team"}
        
        email = self._scrape_company_website(domain)
        if email:
            return {"email": email, "confidence": 0.8, "name": ""}
        
        email = self._extract_from_job_page(job)
        if email:
            return {"email": email, "confidence": 0.6, "name": ""}
        
        logger.warning(f"No email found for {job.company} (domain: {domain})")
        return None
    
    def _discover_domain(self, job: Job) -> Optional[str]:
        """Discover company domain from job URL first, then company name."""
        domain = self._extract_domain_from_url(job.job_url)
        if domain:
            return domain
        
        company_key = job.company.lower().strip()
        if company_key in self.KNOWN_DOMAINS:
            return self.KNOWN_DOMAINS[company_key]
        
        return self._extract_domain_from_name(job.company)
    
    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """Extract company domain from job URL (e.g., careers.sievecorp.com/jobs/...)."""
        try:
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname or ""
            parts = hostname.split(".")
            if len(parts) >= 2:
                return hostname
        except Exception:
            pass
        return None
    
    def _extract_domain_from_name(self, company: str) -> str:
        """Convert company name to a plausible domain."""
        name = company.lower().strip()
        name = re.sub(r'\s+(inc|corp|llc|ltd|co|technologies|tech|labs|studio|ai)\.?$', '', name)
        name = re.sub(r'[^a-z0-9.-]', '', name.replace(' ', ''))
        if not name:
            name = company.lower().strip()
            name = re.sub(r'[^a-z0-9]', '', name)
        for tld in ['.com', '.io', '.ai', '.co', '.dev', '.app']:
            candidate = f"{name}{tld}"
            if self._domain_resolves(candidate):
                return candidate
        return f"{name}.com"
    
    def _domain_resolves(self, domain: str) -> bool:
        """Check if domain has DNS records."""
        try:
            import socket
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except Exception:
            return False
    
    def _try_common_patterns(self, domain: str) -> Optional[str]:
        patterns = [
            f"jobs@{domain}",
            f"hiring@{domain}",
            f"careers@{domain}",
            f"talent@{domain}",
            f"recruiting@{domain}",
        ]
        return patterns[0]
    
    def _scrape_company_website(self, domain: str) -> Optional[str]:
        try:
            urls = [
                f"https://{domain}/careers",
                f"https://{domain}/jobs",
                f"https://{domain}/contact",
                f"https://{domain}/about",
            ]
            for url in urls:
                email = self._find_email_in_page(url)
                if email:
                    return email
        except Exception as e:
            logger.debug(f"Failed to scrape {domain}: {e}")
        return None
    
    def _find_email_in_page(self, url: str) -> Optional[str]:
        try:
            response = self.client.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True,
                timeout=10.0
            )
            if response.status_code != 200:
                return None
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
            excluded = ['support@', 'sales@', 'info@', 'press@', 'privacy@', 'noreply@', 'no-reply@']
            for email in emails:
                if not any(email.startswith(e) for e in excluded):
                    return email
        except Exception:
            pass
        return None
    
    def _extract_from_job_page(self, job: Job) -> Optional[str]:
        try:
            response = self.client.get(
                job.job_url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True,
                timeout=10.0
            )
            if response.status_code == 200:
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
                for email in emails:
                    if any(keyword in email.lower() for keyword in ['job', 'career', 'hiring', 'recruit', 'talent', 'apply']):
                        return email
                if emails:
                    return emails[0]
        except Exception as e:
            logger.debug(f"Failed to extract email from {job.job_url}: {e}")
        return None
