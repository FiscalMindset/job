"""Y Combinator jobs collector."""
import httpx
from bs4 import BeautifulSoup
from typing import List

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class YCombinatorCollector(BaseCollector):
    """
    Collect jobs from Y Combinator Work at a Startup.
    
    URL: https://www.ycombinator.com/jobs
    
    Strategy:
    - Parse the public jobs page
    - Filter by role keywords
    - Extract company info from YC database
    """
    
    def __init__(self):
        super().__init__("ycombinator")
        self.base_url = "https://www.ycombinator.com"
        self.jobs_url = f"{self.base_url}/jobs"
    
    def _collect_impl(self) -> List[Job]:
        """Scrape YC jobs."""
        jobs = []
        
        # Fetch jobs page
        with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
            response = client.get(
                self.jobs_url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True
            )
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # YC uses different layouts, this is a simplified parser
        # In production, you'd need to reverse-engineer their actual structure
        job_listings = soup.find_all('div', class_='job-listing')  # Example selector
        
        if not job_listings:
            # Fallback: try API endpoint (if available)
            jobs = self._try_api_endpoint()
            return jobs
        
        for listing in job_listings[:50]:  # Limit to 50 jobs per run
            try:
                job = self._parse_job_listing(listing)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Failed to parse job listing: {e}")
                continue
        
        return jobs
    
    def _try_api_endpoint(self) -> List[Job]:
        """
        Try YC's API endpoint (if available).
        
        YC may have a JSON API for jobs - check network tab.
        """
        # Example - adjust based on actual API
        try:
            with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                response = client.get(
                    "https://www.ycombinator.com/api/jobs",  # Example URL
                    headers={"User-Agent": config.USER_AGENT}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_api_response(data)
        except:
            pass
        
        return []
    
    def _parse_job_listing(self, listing) -> Job:
        """Parse a single job listing from HTML."""
        # This is a template - adjust selectors based on actual HTML
        title = listing.find('h3')
        company = listing.find('span', class_='company-name')
        location = listing.find('span', class_='location')
        link = listing.find('a', href=True)
        
        if not (title and company and link):
            return None
        
        return Job(
            company=company.text.strip(),
            role=title.text.strip(),
            source=self.name,
            job_url=self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
            location=location.text.strip() if location else "",
            company_stage="seed",  # YC companies are typically early stage
        )
    
    def _parse_api_response(self, data: dict) -> List[Job]:
        """Parse jobs from API response."""
        jobs = []
        
        # Adjust based on actual API structure
        for item in data.get('jobs', []):
            job = Job(
                company=item.get('company', ''),
                role=item.get('title', ''),
                source=self.name,
                job_url=item.get('url', ''),
                description=item.get('description', ''),
                location=item.get('location', ''),
                company_size=item.get('size', ''),
                company_stage=item.get('stage', 'seed'),
            )
            jobs.append(job)
        
        return jobs
