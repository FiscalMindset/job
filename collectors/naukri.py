"""Naukri.com job collector for Indian job market."""
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


class NaukriCollector(BaseCollector):
    """
    Collect jobs from Naukri.com (India's largest job portal).
    
    Strategy:
    - Scrape public job search pages
    - Parse job listings
    - Filter by target roles and experience
    """
    
    def __init__(self):
        super().__init__("naukri")
        self.base_url = "https://www.naukri.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
    
    def _collect_impl(self) -> List[Job]:
        """Scrape Naukri.com jobs."""
        all_jobs = []
        
        # Build search queries for different roles
        role_keywords = [
            "software engineer",
            "backend engineer", 
            "full stack developer",
            "ai engineer",
            "ml engineer"
        ]
        
        for keyword in role_keywords[:2]:  # Limit to 2 roles to avoid too many requests
            # Scrape multiple pages per keyword
            for page in range(1, 4):  # Pages 1-3
                search_url = self._build_search_url(keyword, page)
                
                console.print(Panel(
                    f"[cyan]🔍 Scraping Naukri.com[/cyan]\n\n"
                    f"[yellow]Keyword:[/yellow] {keyword}\n"
                    f"[yellow]Page:[/yellow] {page}/3\n"
                    f"[yellow]Experience:[/yellow] {config.MIN_EXPERIENCE_YEARS}-{config.MAX_EXPERIENCE_YEARS} years\n"
                    f"[yellow]URL:[/yellow] [link={search_url}]{search_url[:80]}...[/link]",
                    title=f"[bold cyan]Naukri Collector[/bold cyan]",
                    border_style="cyan"
                ))
                
                # Fetch with retries
                html = self._fetch_with_retry(search_url)
                if not html:
                    logger.warning(f"Failed to fetch Naukri page {page} for '{keyword}'")
                    continue
                
                # Parse jobs
                soup = BeautifulSoup(html, 'lxml')
                
                # Naukri job cards - common class patterns
                job_cards = soup.find_all('article', class_=lambda x: x and 'jobTuple' in str(x))
                
                if not job_cards:
                    # Try alternative selectors
                    job_cards = soup.find_all('div', class_=lambda x: x and 'srp-jobtuple' in str(x))
                
                console.print(f"[green]✓[/green] Found {len(job_cards)} jobs on page {page}\n")
                
                if len(job_cards) == 0:
                    logger.warning(f"No jobs found on page {page} for '{keyword}', stopping pagination")
                    break
                
                for card in job_cards:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        logger.debug(f"Failed to parse job card: {e}")
                        continue
                
                # Add delay between pages
                time.sleep(2)
            
            # Delay between keywords
            time.sleep(3)
        
        logger.info(f"Naukri: Total jobs collected: {len(all_jobs)}")
        return all_jobs
    
    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build Naukri.com job search URL."""
        params = {
            'k': keyword.replace(' ', '%20'),
            'experience': f"{config.MIN_EXPERIENCE_YEARS}",  # Min experience
            'x-axis': config.MAX_EXPERIENCE_YEARS,  # Max experience
            'sort': '1',  # Sort by relevance
            'page': str(page)
        }
        
        # Add location if specified
        if config.PREFERRED_LOCATIONS:
            location = config.PREFERRED_LOCATIONS[0]
            if location.lower() not in ['remote', 'united states']:
                params['l'] = location.replace(' ', '%20')
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.base_url}/jobs-in-india?{query_string}"
    
    def _parse_job_card(self, card) -> Job:
        """Parse a Naukri job card into Job model."""
        try:
            # Title and company
            title_elem = card.find('a', class_=lambda x: x and 'title' in str(x)) or card.find('h2')
            company_elem = card.find('a', class_=lambda x: x and 'comp' in str(x)) or card.find('div', class_=lambda x: x and 'comp' in str(x))
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            job_url = title_elem.get('href', '')
            
            # Make URL absolute
            if job_url and not job_url.startswith('http'):
                job_url = f"{self.base_url}{job_url}"
            
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location
            location_elem = card.find('li', class_=lambda x: x and 'loc' in str(x)) or card.find('span', class_=lambda x: x and 'loc' in str(x))
            location = location_elem.get_text(strip=True) if location_elem else "India"
            
            # Experience
            exp_elem = card.find('li', class_=lambda x: x and 'exp' in str(x)) or card.find('span', class_=lambda x: x and 'exp' in str(x))
            experience = exp_elem.get_text(strip=True) if exp_elem else ""
            
            # Salary
            salary_elem = card.find('li', class_=lambda x: x and 'sal' in str(x)) or card.find('span', class_=lambda x: x and 'sal' in str(x))
            salary = salary_elem.get_text(strip=True) if salary_elem else ""
            
            # Description
            desc_elem = card.find('div', class_=lambda x: x and 'desc' in str(x)) or card.find('p')
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Posted date
            date_elem = card.find('span', class_=lambda x: x and 'date' in str(x))
            posted_date = self._parse_naukri_date(date_elem.get_text(strip=True) if date_elem else "")
            
            # Skills
            skills_elem = card.find('ul', class_=lambda x: x and 'tag' in str(x))
            skills = []
            if skills_elem:
                skill_items = skills_elem.find_all('li')
                skills = [s.get_text(strip=True) for s in skill_items]
            
            # Build full description
            full_description = f"{description}\n\n"
            if experience:
                full_description += f"Experience: {experience}\n"
            if salary:
                full_description += f"Salary: {salary}\n"
            if skills:
                full_description += f"Skills: {', '.join(skills)}\n"
            
            job = Job(
                job_id=self._generate_job_id(self.name, company, title),
                company=company,
                role=title,
                url=job_url,
                source=self.name,
                location=location,
                posted_date=posted_date,
                description=full_description.strip()
            )
            
            return job
            
        except Exception as e:
            logger.debug(f"Failed to parse Naukri job card: {e}")
            return None
    
    def _parse_naukri_date(self, date_str: str) -> datetime:
        """Parse Naukri date strings like '2 Days ago', 'Today', 'Just now'."""
        date_str = date_str.lower().strip()
        now = datetime.utcnow()
        
        if 'just now' in date_str or 'today' in date_str:
            return now
        elif 'yesterday' in date_str:
            return now - timedelta(days=1)
        elif 'days ago' in date_str or 'day ago' in date_str:
            try:
                days = int(''.join(filter(str.isdigit, date_str)))
                return now - timedelta(days=days)
            except:
                return now
        elif 'week ago' in date_str or 'weeks ago' in date_str:
            try:
                weeks = int(''.join(filter(str.isdigit, date_str)))
                return now - timedelta(weeks=weeks)
            except:
                return now - timedelta(weeks=1)
        elif 'month ago' in date_str or 'months ago' in date_str:
            try:
                months = int(''.join(filter(str.isdigit, date_str)))
                return now - timedelta(days=months * 30)
            except:
                return now - timedelta(days=30)
        else:
            return now
    
    def _fetch_with_retry(self, url: str, retries: int = 3) -> str:
        """Fetch URL with retries."""
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=30, follow_redirects=True) as client:
                    resp = client.get(url, headers=self.headers)
                    if resp.status_code == 200:
                        return resp.text
                    else:
                        logger.warning(f"HTTP {resp.status_code} for {url}")
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to fetch {url}: {e}")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return ""
