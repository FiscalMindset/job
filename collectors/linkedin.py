"""LinkedIn jobs collector."""
import httpx
from bs4 import BeautifulSoup
from typing import List
import urllib.parse
import time
from datetime import datetime, timedelta

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
from rich.console import Console
from rich.panel import Panel
import config


logger = get_logger(__name__)
console = Console()


class LinkedInCollector(BaseCollector):
    """
    Collect jobs from LinkedIn.
    
    Strategy:
    - Use public job search URLs (no auth required)
    - Parse job listings
    - Limited to ~25 jobs per search without login
    
    Note: LinkedIn actively blocks scrapers. Consider:
    - Rotating user agents
    - Adding delays between requests
    - Using Playwright for JS rendering
    - Using LinkedIn session cookie (if available)
    """
    
    def __init__(self):
        super().__init__("linkedin")
        self.base_url = "https://www.linkedin.com"
    
    def _collect_impl(self) -> List[Job]:
        """Scrape LinkedIn jobs."""
        all_jobs = []
        
        # Build search query
        keywords = " OR ".join(config.TARGET_ROLES)
        location = config.PREFERRED_LOCATIONS[0] if config.PREFERRED_LOCATIONS else "United States"
        
        # Scrape multiple pages
        for page in range(config.LINKEDIN_MAX_PAGES):
            # LinkedIn job search URL with pagination
            search_url = self._build_search_url(keywords, location, page)
            
            # Show beautiful progress panel
            console.print(Panel(
                f"[cyan]🔍 Scraping LinkedIn[/cyan]\n\n"
                f"[yellow]Page:[/yellow] {page + 1}/{config.LINKEDIN_MAX_PAGES}\n"
                f"[yellow]Keywords:[/yellow] {keywords}\n"
                f"[yellow]Location:[/yellow] {location}\n"
                f"[yellow]URL:[/yellow] [link={search_url}]{search_url[:80]}...[/link]",
                title=f"[bold cyan]LinkedIn Collector[/bold cyan]",
                border_style="cyan"
            ))
            
            # Fetch with retries
            html = self._fetch_with_retry(search_url)
            if not html:
                logger.warning(f"Failed to fetch LinkedIn page {page + 1}")
                continue
            
            # Parse jobs
            soup = BeautifulSoup(html, 'lxml')
            job_cards = soup.find_all('div', class_='base-card')
            
            console.print(f"[green]✓[/green] Found {len(job_cards)} jobs on page {page + 1}\n")
            
            if len(job_cards) == 0:
                logger.warning(f"No jobs found on page {page + 1}, stopping pagination")
                break
            
            for card in job_cards:
                try:
                    job = self._parse_job_card(card)
                    if job:
                        all_jobs.append(job)
                except Exception as e:
                    logger.debug(f"Failed to parse job card: {e}")
                    continue
            
            # Add delay between pages to be respectful
            import time
            time.sleep(2)
        
        logger.info(f"LinkedIn: Total jobs collected: {len(all_jobs)}")
        return all_jobs
    
    def _build_search_url(self, keywords: str, location: str, page: int = 0) -> str:
        """Build LinkedIn job search URL."""
        params = {
            'keywords': keywords,
            'location': location,
            'f_TPR': 'r86400',  # Last 24 hours
            'f_E': '1,2',  # Entry level & Associate
            'position': '1',
            'pageNum': str(page),
            'start': str(page * 25),  # LinkedIn shows 25 jobs per page
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/jobs/search?{query_string}"
    
    def _fetch_with_retry(self, url: str) -> str:
        """Fetch URL with retries."""
        headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Add session cookie if available
        cookies = {}
        if config.LINKEDIN_SESSION_COOKIE:
            cookies['li_at'] = config.LINKEDIN_SESSION_COOKIE
        
        with httpx.Client(timeout=config.REQUEST_TIMEOUT, cookies=cookies) as client:
            for attempt in range(config.MAX_RETRIES):
                try:
                    response = client.get(url, headers=headers, follow_redirects=True)
                    
                    if response.status_code == 200:
                        return response.text
                    
                    logger.warning(f"LinkedIn returned {response.status_code}, attempt {attempt + 1}")
                    
                except Exception as e:
                    logger.warning(f"Request failed, attempt {attempt + 1}: {e}")
                
                # Wait before retry
                import time
                time.sleep(config.RETRY_DELAY)
        
        return None
    
    def _parse_job_card(self, card) -> Job:
        """Parse a LinkedIn job card."""
        # Extract elements
        title_elem = card.find('h3', class_='base-search-card__title')
        company_elem = card.find('h4', class_='base-search-card__subtitle')
        location_elem = card.find('span', class_='job-search-card__location')
        link_elem = card.find('a', class_='base-card__full-link')
        date_elem = card.find('time')
        
        if not (title_elem and company_elem and link_elem):
            return None
        
        # Extract text
        title = title_elem.text.strip()
        company = company_elem.text.strip()
        location = location_elem.text.strip() if location_elem else ""
        job_url = link_elem['href']
        
        # Parse date
        posted_date = None
        if date_elem and date_elem.get('datetime'):
            posted_date = self._parse_posted_date(date_elem['datetime'])
        
        return Job(
            company=company,
            role=title,
            source=self.name,
            job_url=job_url,
            location=location,
            posted_date=posted_date,
        )
