"""Wellfound (AngelList Talent) jobs collector."""
import httpx
from bs4 import BeautifulSoup
from typing import List

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class WellfoundCollector(BaseCollector):
    """
    Collect jobs from Wellfound (formerly AngelList Talent).
    
    URL: https://wellfound.com/jobs
    
    Strategy:
    - Use public job search
    - Filter by role and location
    - Extract startup metadata
    """
    
    def __init__(self):
        super().__init__("wellfound")
        self.base_url = "https://wellfound.com"
    
    def _collect_impl(self) -> List[Job]:
        """Scrape Wellfound jobs."""
        jobs = []
        
        # Wellfound has a GraphQL API - we can try that
        # Or parse the HTML search results
        
        # Try GraphQL API first
        api_jobs = self._try_graphql_api()
        if api_jobs:
            return api_jobs
        
        # Fallback to HTML scraping
        search_url = f"{self.base_url}/role/r/software-engineer"
        
        with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
            response = client.get(
                search_url,
                headers={"User-Agent": config.USER_AGENT},
                follow_redirects=True
            )
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Parse job listings (adjust selectors based on actual HTML)
        job_cards = soup.find_all('div', class_='startup-job-listing')
        
        for card in job_cards[:40]:
            try:
                job = self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Failed to parse job: {e}")
                continue
        
        return jobs
    
    def _try_graphql_api(self) -> List[Job]:
        """
        Try Wellfound's GraphQL API.
        
        Wellfound uses GraphQL - inspect network requests to find the query.
        """
        # Example GraphQL query (adjust based on actual API)
        query = """
        query JobSearch($slug: String!) {
          startupJobs(slug: $slug) {
            id
            title
            locationNames
            startup {
              name
              companySize
              slug
            }
          }
        }
        """
        
        try:
            with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                response = client.post(
                    f"{self.base_url}/graphql",
                    json={
                        "query": query,
                        "variables": {"slug": "software-engineer"}
                    },
                    headers={
                        "User-Agent": config.USER_AGENT,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_graphql_response(data)
        except:
            pass
        
        return []
    
    def _parse_graphql_response(self, data: dict) -> List[Job]:
        """Parse GraphQL response."""
        jobs = []
        
        # Adjust based on actual response structure
        job_data = data.get('data', {}).get('startupJobs', [])
        
        for item in job_data:
            startup = item.get('startup', {})
            
            job = Job(
                company=startup.get('name', ''),
                role=item.get('title', ''),
                source=self.name,
                job_url=f"{self.base_url}/jobs/{item.get('id')}",
                location=", ".join(item.get('locationNames', [])),
                company_size=startup.get('companySize', ''),
                company_stage="startup",
            )
            jobs.append(job)
        
        return jobs
    
    def _parse_job_card(self, card) -> Job:
        """Parse HTML job card."""
        title = card.find('h2')
        company = card.find('div', class_='company-name')
        location = card.find('span', class_='location')
        link = card.find('a', href=True)
        
        if not (title and company and link):
            return None
        
        return Job(
            company=company.text.strip(),
            role=title.text.strip(),
            source=self.name,
            job_url=self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
            location=location.text.strip() if location else "",
            company_stage="startup",
        )
