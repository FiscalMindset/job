"""Wellfound (AngelList Talent) jobs collector."""
import httpx
from typing import List

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class WellfoundCollector(BaseCollector):
    API_BASE = "https://wellfound.com"
    GRAPHQL_URL = f"{API_BASE}/graphql"

    def __init__(self):
        super().__init__("wellfound")

    def _collect_impl(self) -> List[Job]:
        jobs = self._try_graphql_api()
        if jobs:
            return jobs
        logger.warning("Wellfound: GraphQL API failed, trying HTML scrape")
        return self._try_html_scrape()

    def _try_graphql_api(self) -> List[Job]:
        query = """
        query jobSearch($filter: JobFilters!) {
          jobs(filter: $filter) {
            id
            title
            locations
            startup {
              name
              size
              stage
              slug
            }
            url
          }
        }
        """
        roles = ["software-engineer", "backend-engineer", "full-stack-engineer", "ai-engineer", "ml-engineer"]
        all_jobs: List[Job] = []

        for role in roles[:2]:
            try:
                with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                    resp = client.post(
                        self.GRAPHQL_URL,
                        json={
                            "query": query,
                            "variables": {"filter": {"slug": role, "page": 1}},
                        },
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": config.USER_AGENT,
                            "Accept": "application/json",
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    jobs_data = data.get("data", {}).get("jobs", [])
                    for item in jobs_data:
                        startup = item.get("startup", {}) or {}
                        job = Job(
                            company=startup.get("name", "Unknown Startup"),
                            role=item.get("title", ""),
                            source=self.name,
                            job_url=item.get("url", ""),
                            location=", ".join(item.get("locations", [])) if item.get("locations") else "",
                            company_size=startup.get("size", ""),
                            company_stage=startup.get("stage", "startup"),
                        )
                        all_jobs.append(job)
                    self._throttle()
            except Exception as e:
                logger.debug(f"Wellfound GraphQL failed for role '{role}': {e}")

        return all_jobs

    def _try_html_scrape(self) -> List[Job]:
        from bs4 import BeautifulSoup
        jobs: List[Job] = []
        try:
            with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                resp = client.get(
                    f"{self.API_BASE}/jobs",
                    headers=self._build_headers(),
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return jobs
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.find_all("div", class_="startup-job-listing")
                for card in cards[:30]:
                    try:
                        title = card.find("h2")
                        company = card.find("div", class_="company-name")
                        link = card.find("a", href=True)
                        if not (title and company and link):
                            continue
                        href = link["href"]
                        if not href.startswith("http"):
                            href = f"{self.API_BASE}{href}"
                        jobs.append(Job(
                            company=company.text.strip(),
                            role=title.text.strip(),
                            source=self.name,
                            job_url=href,
                            company_stage="startup",
                        ))
                    except Exception as e:
                        logger.debug(f"Wellfound HTML parse error: {e}")
        except Exception as e:
            logger.error(f"Wellfound HTML scrape failed: {e}")
        return jobs

    def estimate_total_jobs(self) -> int:
        return 60
