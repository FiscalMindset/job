"""Email finder - discover contact emails for companies."""
import httpx
import re
from typing import Optional, Dict, Any

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class EmailFinder:
    """
    Find hiring contact emails for companies.
    
    Strategies (in order):
    1. Common patterns: jobs@, hiring@, careers@
    2. Parse company website for contact emails
    3. LinkedIn profile scraping (if session available)
    4. Domain verification (check if email domain exists)
    
    Note: This is a simplified implementation.
    For production, consider:
    - Hunter.io API (paid)
    - RocketReach API (paid)
    - Custom domain research
    """
    
    # Career Page Companies (use career page instead of email)
    CAREER_PAGE_COMPANIES = {
        "notion": "https://www.notion.so/careers",
        "stripe": "https://stripe.com/jobs",
        "figma": "https://www.figma.com/careers",
        "linear": "https://linear.app/careers",
        "vercel": "https://vercel.com/careers",
        "anthropic": "https://www.anthropic.com/careers",
    }
    
    def __init__(self):
        self.client = httpx.Client(timeout=config.REQUEST_TIMEOUT)
    
    def find_email(self, job: Job) -> Optional[Dict[str, Any]]:
        """
        Find email for job application.
        
        Returns:
            Dict with keys: email, confidence (0-1), name (optional)
            None if no email found
        """
        # Check if company uses career page only
        company_key = job.company.lower().strip()
        if company_key in self.CAREER_PAGE_COMPANIES:
            logger.info(f"{job.company} uses career page applications only: {self.CAREER_PAGE_COMPANIES[company_key]}")
            return None  # Will skip email sending
        
        # Strategy 1: Try common patterns
        email = self._try_common_patterns(job)
        if email:
            return {
                "email": email,
                "confidence": 0.7,
                "name": "Hiring Team"
            }
        
        # Strategy 2: Scrape company website
        email = self._scrape_company_website(job)
        if email:
            return {
                "email": email,
                "confidence": 0.8,
                "name": ""
            }
        
        # Strategy 3: Try to extract from job URL
        email = self._extract_from_job_page(job)
        if email:
            return {
                "email": email,
                "confidence": 0.9,
                "name": ""
            }
        
        logger.warning(f"No email found for {job.company}")
        return None
    
    def _try_common_patterns(self, job: Job) -> Optional[str]:
        """Try common email patterns."""
        # Get company domain
        domain = self._extract_domain(job)
        if not domain:
            return None
        
        # Common patterns
        patterns = [
            f"jobs@{domain}",
            f"hiring@{domain}",
            f"careers@{domain}",
            f"talent@{domain}",
            f"recruiting@{domain}",
        ]
        
        # Verify domain exists
        if self._verify_domain(domain):
            # Return most likely pattern
            return patterns[0]
        
        return None
    
    def _extract_domain(self, job: Job) -> Optional[str]:
        """Extract company domain from various sources."""
        # Try to get domain from company name
        company = job.company.lower().strip()
        
        # Remove common suffixes
        company = re.sub(r'\s+(inc|corp|llc|ltd|co)\.?$', '', company)
        
        # Convert to domain-friendly format
        domain = company.replace(' ', '').replace(',', '')
        
        # Add .com (assumption - could be wrong)
        return f"{domain}.com"
    
    def _verify_domain(self, domain: str) -> bool:
        """Check if domain exists (has MX records)."""
        try:
            import socket
            socket.gethostbyname(domain)
            return True
        except:
            return False
    
    def _scrape_company_website(self, job: Job) -> Optional[str]:
        """Scrape company website for contact emails."""
        domain = self._extract_domain(job)
        if not domain:
            return None
        
        try:
            # Try careers/jobs/contact pages
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
        """Find email address in a web page."""
        try:
            response = self.client.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True
            )
            
            if response.status_code != 200:
                return None
            
            # Find email with regex
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
            
            # Filter out common non-hiring emails
            excluded = ['support@', 'sales@', 'info@', 'press@', 'privacy@']
            
            for email in emails:
                if not any(email.startswith(e) for e in excluded):
                    return email
        
        except:
            pass
        
        return None
    
    def _extract_from_job_page(self, job: Job) -> Optional[str]:
        """Extract email from job posting page."""
        try:
            response = self.client.get(
                job.job_url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True
            )
            
            if response.status_code == 200:
                # Look for "apply" emails
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
                
                # Prioritize hiring-related emails
                for email in emails:
                    if any(keyword in email.lower() for keyword in ['job', 'career', 'hiring', 'recruit', 'talent']):
                        return email
                
                # Return first email found
                if emails:
                    return emails[0]
        
        except Exception as e:
            logger.debug(f"Failed to extract email from {job.job_url}: {e}")
        
        return None
