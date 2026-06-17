"""Email finder - discover contact emails for companies using multiple strategies."""
import httpx
import re
import urllib.parse
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailFinder:
    KNOWN_DOMAINS = {
        "notion": "notion.so", "stripe": "stripe.com", "figma": "figma.com",
        "linear": "linear.app", "vercel": "vercel.com",
        "anthropic": "anthropic.com", "openai": "openai.com",
        "google": "google.com", "meta": "meta.com", "apple": "apple.com",
        "microsoft": "microsoft.com", "amazon": "amazon.com",
        "netflix": "netflix.com", "spotify": "spotify.com",
        "slack": "slack.com", "airbnb": "airbnb.com",
        "uber": "uber.com", "doordash": "doordash.com",
        "datadog": "datadoghq.com", "hashicorp": "hashicorp.com",
        "elastic": "elastic.co", "mongodb": "mongodb.com",
        "snowflake": "snowflake.com", "cloudflare": "cloudflare.com",
        "github": "github.com", "gitlab": "gitlab.com",
        "docker": "docker.com", "kubernetes": "kubernetes.io",
        "sentry": "sentry.io", "netlify": "netlify.com",
        "railway": "railway.app", "render": "render.com",
        "fly": "fly.io", "replit": "replit.com",
        "cursor": "cursor.com", "warp": "warp.dev",
        "perplexity": "perplexity.ai", "midjourney": "midjourney.com",
        "character.ai": "character.ai", "sievecorp": "sievecorp.com",
        "pinecone": "pinecone.io", "weaviate": "weaviate.io",
        "chroma": "chroma.com", "cohere": "cohere.com",
        "huggingface": "huggingface.co", "replicate": "replicate.com",
    }

    CAREER_PAGE_COMPANIES = {
        "notion": "https://www.notion.so/careers",
        "stripe": "https://stripe.com/jobs",
        "figma": "https://www.figma.com/careers",
        "linear": "https://linear.app/careers",
        "vercel": "https://vercel.com/careers",
    }

    EXCLUDED_EMAIL_PREFIXES = [
        "support", "sales", "info", "press", "privacy",
        "noreply", "no-reply", "donotreply", "admin",
        "webmaster", "postmaster", "abuse", "spam",
    ]

    EMAIL_PATTERNS = [
        "jobs@{domain}", "hiring@{domain}", "careers@{domain}",
        "talent@{domain}", "recruiting@{domain}", "hr@{domain}",
        "apply@{domain}", "join@{domain}", "team@{domain}",
        "people@{domain}",
    ]

    def __init__(self):
        self.client = httpx.Client(timeout=15.0, follow_redirects=True)

    def find_email(self, job: Job) -> Optional[Dict[str, Any]]:
        company_key = job.company.lower().strip()
        if company_key in self.CAREER_PAGE_COMPANIES:
            logger.info(f"{job.company} uses career portal only: {self.CAREER_PAGE_COMPANIES[company_key]}")
            return None

        domain = self._discover_domain(job)
        if not domain:
            logger.warning(f"No domain for {job.company}")
            return None

        result = self._search_email_in_parallel(domain, job)
        if result:
            return result

        logger.warning(f"No email found for {job.company} (domain: {domain})")
        return None

    def _discover_domain(self, job: Job) -> Optional[str]:
        domain = self._extract_domain_from_url(job.job_url)
        if domain:
            return domain
        company_key = job.company.lower().strip()
        if company_key in self.KNOWN_DOMAINS:
            return self.KNOWN_DOMAINS[company_key]
        return self._extract_domain_from_name(job.company)

    def _extract_domain_from_url(self, url: str) -> Optional[str]:
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
        name = company.lower().strip()
        name = re.sub(r'\s+(inc|corp|llc|ltd|co|technologies|tech|labs|studio|ai)\.?$', '', name)
        name = re.sub(r'[^a-z0-9.-]', '', name.replace(' ', ''))
        if not name:
            name = re.sub(r'[^a-z0-9]', '', company.lower().strip())
        for tld in ['.com', '.io', '.ai', '.co', '.dev', '.app', '.org']:
            candidate = f"{name}{tld}"
            if self._domain_resolves(candidate):
                return candidate
        return f"{name}.com"

    def _domain_resolves(self, domain: str) -> bool:
        try:
            import socket
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except Exception:
            return False

    def _search_email_in_parallel(self, domain: str, job: Job) -> Optional[Dict[str, Any]]:
        strategies = [
            ("common_patterns", lambda: self._try_common_patterns_parallel(domain)),
            ("website_scrape", lambda: self._scrape_company_website(domain)),
            ("job_page_scrape", lambda: self._extract_from_job_page(job)),
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_map = {pool.submit(fn): name for name, fn in strategies}
            for future in as_completed(fut_map):
                name = fut_map[future]
                try:
                    email = future.result(timeout=12)
                    if email:
                        logger.info(f"Found email via {name}: {email}")
                        confidence = {"common_patterns": 0.7, "website_scrape": 0.8, "job_page_scrape": 0.6}.get(name, 0.6)
                        return {"email": email, "confidence": confidence, "name": "Hiring Team"}
                except Exception:
                    pass
        return None

    def _try_common_patterns_parallel(self, domain: str) -> Optional[str]:
        def _try(pattern: str) -> Optional[str]:
            email = pattern
            if self._email_resolves_dns(email):
                return email
            return None

        candidates = [p.format(domain=domain) for p in self.EMAIL_PATTERNS]
        with ThreadPoolExecutor(max_workers=min(len(candidates), 5)) as pool:
            for future in as_completed([pool.submit(_try, c) for c in candidates]):
                try:
                    result = future.result(timeout=5)
                    if result:
                        return result
                except Exception:
                    continue
        return candidates[0]

    def _email_resolves_dns(self, email: str) -> bool:
        try:
            import socket
            domain = email.split("@")[1]
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except Exception:
            return False

    def _scrape_company_website(self, domain: str) -> Optional[str]:
        urls = [
            f"https://{domain}/careers",
            f"https://{domain}/jobs",
            f"https://{domain}/contact",
            f"https://{domain}/about",
        ]
        for url in urls:
            try:
                email = self._find_email_in_page(url)
                if email:
                    return email
            except Exception:
                continue
        return None

    def _find_email_in_page(self, url: str) -> Optional[str]:
        try:
            resp = self.client.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=10)
            if resp.status_code != 200:
                return None
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resp.text)
            for email in emails:
                prefix = email.split("@")[0].lower()
                if not any(prefix.startswith(ex) for ex in self.EXCLUDED_EMAIL_PREFIXES):
                    return email
        except Exception:
            pass
        return None

    def _extract_from_job_page(self, job: Job) -> Optional[str]:
        try:
            resp = self.client.get(job.job_url, headers={"User-Agent": config.USER_AGENT}, timeout=10)
            if resp.status_code != 200:
                return None
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resp.text)
            for email in emails:
                if any(kw in email.lower() for kw in ["job", "career", "hiring", "recruit", "talent", "apply"]):
                    return email
            if emails:
                prefix = emails[0].split("@")[0].lower()
                if not any(prefix.startswith(ex) for ex in self.EXCLUDED_EMAIL_PREFIXES):
                    return emails[0]
        except Exception as e:
            logger.debug(f"Failed to extract from job page {job.job_url}: {e}")
        return None
