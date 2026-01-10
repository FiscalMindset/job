"""GitHub jobs collector - scrapes GitHub careers page and user repos with hiring tags."""
import httpx
from bs4 import BeautifulSoup
from typing import List
import time
from datetime import datetime

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
from rich.console import Console
from rich.panel import Panel
import config


logger = get_logger(__name__)
console = Console()


class GitHubCollector(BaseCollector):
    """
    Collect jobs from multiple GitHub sources:
    
    1. GitHub Careers Page (https://github.com/about/careers)
    2. GitHub Search for repos/issues with hiring keywords
    3. Public repos tagged with 'hiring', 'job', 'careers'
    
    This captures both official GitHub postings AND companies hiring on GitHub.
    """
    
    def __init__(self):
        super().__init__("github")
        self.base_url = "https://github.com"
        self.api_url = "https://api.github.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/vnd.github.v3+json"
        }
        if config.GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
    
    def _collect_impl(self) -> List[Job]:
        """Collect jobs from all GitHub sources."""
        all_jobs = []
        
        # Source 1: GitHub Careers Page
        console.print(Panel(
            "[cyan]🔍 Scraping GitHub Careers Page[/cyan]\n\n"
            "[yellow]URL:[/yellow] https://github.com/about/careers",
            title="[bold cyan]GitHub Collector - Official Careers[/bold cyan]",
            border_style="cyan"
        ))
        
        careers_jobs = self._scrape_github_careers()
        all_jobs.extend(careers_jobs)
        console.print(f"[green]✓[/green] Found {len(careers_jobs)} jobs from GitHub Careers\n")
        
        # Source 2: GitHub Search for repos with hiring
        console.print(Panel(
            "[cyan]🔍 Searching GitHub Repos for Hiring[/cyan]\n\n"
            "[yellow]Topics:[/yellow] hiring, job, careers, jobs, recruiting\n"
            "[yellow]Keywords:[/yellow] We're hiring, Join our team, Now hiring",
            title="[bold cyan]GitHub Collector - Community Hiring[/bold cyan]",
            border_style="cyan"
        ))
        
        hiring_jobs = self._search_github_hiring()
        all_jobs.extend(hiring_jobs)
        console.print(f"[green]✓[/green] Found {len(hiring_jobs)} jobs from GitHub hiring posts\n")
        
        # Source 3: GitHub Issues with "hiring" label
        console.print(Panel(
            "[cyan]🔍 Searching GitHub Issues for Hiring[/cyan]\n\n"
            "[yellow]Labels:[/yellow] hiring, jobs, recruitment\n"
            "[yellow]State:[/yellow] open",
            title="[bold cyan]GitHub Collector - Issue Postings[/bold cyan]",
            border_style="cyan"
        ))
        
        issue_jobs = self._search_github_issues()
        all_jobs.extend(issue_jobs)
        console.print(f"[green]✓[/green] Found {len(issue_jobs)} jobs from GitHub issues\n")
        
        logger.info(f"GitHub: Total jobs collected: {len(all_jobs)}")
        return all_jobs
    
    def _scrape_github_careers(self) -> List[Job]:
        """Scrape official GitHub careers page."""
        jobs = []
        try:
            # Try the careers page
            url = "https://github.com/about/careers"
            resp = httpx.get(url, headers=self.headers, timeout=30, follow_redirects=True)
            
            if resp.status_code != 200:
                logger.warning(f"GitHub careers returned {resp.status_code}")
                return jobs
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # GitHub career page structure (may vary)
            # Look for job listings - common patterns
            job_links = soup.find_all('a', href=True)
            
            for link in job_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Check if link looks like a job posting
                if any(keyword in text.lower() for keyword in ['engineer', 'developer', 'backend', 'frontend', 'ml', 'ai', 'software']):
                    if 'careers' in href or 'jobs' in href or href.startswith('/about/careers'):
                        full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        
                        job = Job(
                            job_id=self._generate_job_id("github", text, full_url),
                            company="GitHub",
                            role=text,
                            job_url=full_url,
                            source=self.name,
                            location="Remote",  # GitHub is remote-friendly
                            posted_date=datetime.utcnow(),
                            description=f"GitHub official career posting: {text}"
                        )
                        jobs.append(job)
                        
                        if len(jobs) >= 10:  # Limit to avoid duplicates
                            break
        
        except Exception as e:
            logger.error(f"Failed to scrape GitHub careers: {e}")
        
        return jobs
    
    def _search_github_hiring(self) -> List[Job]:
        """Search for GitHub repos with hiring-related topics and README."""
        jobs = []
        
        hiring_keywords = [
            "hiring+engineers",
            "we+are+hiring",
            "join+our+team",
            "now+hiring",
            "careers+page"
        ]
        
        for keyword in hiring_keywords[:2]:  # Limit searches to avoid rate limits
            try:
                # Search repos via API
                search_url = f"{self.api_url}/search/repositories"
                params = {
                    "q": f"{keyword} in:readme",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": 10
                }
                
                resp = httpx.get(search_url, headers=self.headers, params=params, timeout=30)
                
                if resp.status_code == 403:
                    logger.warning("GitHub API rate limit hit, skipping repo search")
                    break
                
                if resp.status_code != 200:
                    logger.warning(f"GitHub search returned {resp.status_code}")
                    continue
                
                data = resp.json()
                items = data.get('items', [])
                
                for repo in items[:5]:  # Top 5 per keyword
                    try:
                        # Extract company from repo owner
                        company = repo.get('owner', {}).get('login', 'Unknown')
                        repo_name = repo.get('name', '')
                        description = repo.get('description', '')
                        html_url = repo.get('html_url', '')
                        
                        # Check README for hiring info
                        readme_url = f"{self.api_url}/repos/{company}/{repo_name}/readme"
                        readme_resp = httpx.get(readme_url, headers=self.headers, timeout=15)
                        
                        if readme_resp.status_code == 200:
                            readme_data = readme_resp.json()
                            # README content is base64 encoded
                            import base64
                            readme_content = base64.b64decode(readme_data.get('content', '')).decode('utf-8')
                            
                            # Look for job-related URLs in README
                            if any(word in readme_content.lower() for word in ['hiring', 'careers', 'jobs', 'join us', 'we are looking']):
                                job = Job(
                                    job_id=self._generate_job_id("github", company, html_url),
                                    company=company.title(),
                                    role=f"Engineering Position (from README)",
                                    job_url=html_url,
                                    source=self.name,
                                    location="Unknown",
                                    posted_date=datetime.fromisoformat(repo.get('updated_at', '').replace('Z', '+00:00')) if repo.get('updated_at') else datetime.utcnow(),
                                    description=f"{description}\n\nFound hiring info in repo README: {repo_name}"
                                )
                                jobs.append(job)
                        
                        time.sleep(0.5)  # Rate limit protection
                        
                    except Exception as e:
                        logger.debug(f"Failed to parse repo: {e}")
                        continue
                
                time.sleep(1)  # Delay between keyword searches
                
            except Exception as e:
                logger.error(f"GitHub repo search failed for '{keyword}': {e}")
                continue
        
        return jobs
    
    def _search_github_issues(self) -> List[Job]:
        """Search for GitHub issues with hiring-related labels."""
        jobs = []
        
        try:
            # Search issues via API
            search_url = f"{self.api_url}/search/issues"
            params = {
                "q": "label:hiring OR label:jobs OR label:recruitment is:open is:issue",
                "sort": "updated",
                "order": "desc",
                "per_page": 20
            }
            
            resp = httpx.get(search_url, headers=self.headers, params=params, timeout=30)
            
            if resp.status_code == 403:
                logger.warning("GitHub API rate limit hit, skipping issue search")
                return jobs
            
            if resp.status_code != 200:
                logger.warning(f"GitHub issue search returned {resp.status_code}")
                return jobs
            
            data = resp.json()
            items = data.get('items', [])
            
            for issue in items[:15]:  # Top 15 issues
                try:
                    title = issue.get('title', '')
                    body = issue.get('body', '')
                    html_url = issue.get('html_url', '')
                    repo_url = issue.get('repository_url', '')
                    
                    # Extract company from repo URL
                    company = "Unknown"
                    if repo_url:
                        parts = repo_url.split('/')
                        if len(parts) >= 5:
                            company = parts[-2]  # Owner name
                    
                    # Check if it's actually a job posting
                    job_keywords = ['engineer', 'developer', 'position', 'role', 'hiring', 'join', 'opening']
                    if any(keyword in title.lower() or keyword in (body or '').lower() for keyword in job_keywords):
                        job = Job(
                            job_id=self._generate_job_id("github-issue", company, html_url),
                            company=company.title(),
                            role=title,
                            job_url=html_url,
                            source=self.name,
                            location="Remote",  # Assume remote for GitHub postings
                            posted_date=datetime.fromisoformat(issue.get('created_at', '').replace('Z', '+00:00')) if issue.get('created_at') else datetime.utcnow(),
                            description=f"GitHub Issue Posting:\n\n{body[:500] if body else 'No description'}"
                        )
                        jobs.append(job)
                
                except Exception as e:
                    logger.debug(f"Failed to parse issue: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"GitHub issue search failed: {e}")
        
        return jobs
    
    def _fetch_with_retry(self, url: str, retries: int = 3) -> str:
        """Fetch URL with retries."""
        for attempt in range(retries):
            try:
                resp = httpx.get(url, headers=self.headers, timeout=30, follow_redirects=True)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 403:
                    logger.warning("GitHub rate limit hit")
                    return ""
                else:
                    logger.warning(f"HTTP {resp.status_code} for {url}")
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to fetch {url}: {e}")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return ""
