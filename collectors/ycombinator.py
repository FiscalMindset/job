"""Y Combinator jobs collector."""
import httpx
from typing import List, Any

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class YCombinatorCollector(BaseCollector):
    API_URL = "https://www.workatastartup.com/jobs"
    API_SEARCH = "https://www.workatastartup.com/api/jobs"
    GRAPHQL_URL = "https://www.workatastartup.com/graphql"

    def __init__(self):
        super().__init__("ycombinator")

    def _collect_impl(self) -> List[Job]:
        jobs = self._try_graphql_api()
        if jobs:
            return jobs
        jobs = self._try_rest_api()
        if jobs:
            return jobs
        logger.warning("Y Combinator: All API methods failed")
        return []

    def _try_graphql_api(self) -> List[Job]:
        query = """
        query JobSearch($limit: Int!, $offset: Int!) {
          jobs(limit: $limit, offset: $offset) {
            id
            title
            company {
              name
              slug
              size
              stage
              location
            }
            locationNames
            description
            url
          }
        }
        """
        all_jobs: List[Job] = []
        limit = 50

        for offset in range(0, 200, limit):
            try:
                with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                    resp = client.post(
                        self.GRAPHQL_URL,
                        json={"query": query, "variables": {"limit": limit, "offset": offset}},
                        headers={"Content-Type": "application/json", "User-Agent": config.USER_AGENT},
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    jobs_data = data.get("data", {}).get("jobs", [])
                    if not jobs_data:
                        break
                    for item in jobs_data:
                        company = item.get("company", {}) or {}
                        job = Job(
                            company=company.get("name", "Unknown YC Startup"),
                            role=item.get("title", ""),
                            source=self.name,
                            job_url=item.get("url", f"https://www.workatastartup.com/jobs/{item.get('id')}"),
                            description=item.get("description", ""),
                            location=", ".join(item.get("locationNames", [])) if item.get("locationNames") else (company.get("location", "") or ""),
                            company_size=company.get("size", ""),
                            company_stage=company.get("stage", "seed"),
                        )
                        all_jobs.append(job)
                    self._throttle()
            except Exception as e:
                logger.debug(f"YC GraphQL failed at offset {offset}: {e}")
                break

        return all_jobs

    def _try_rest_api(self) -> List[Job]:
        try:
            with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
                resp = client.get(
                    self.API_SEARCH,
                    params={"limit": 50, "sort": "newest"},
                    headers={"User-Agent": config.USER_AGENT},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return self._parse_api_response(data)
        except Exception as e:
            logger.debug(f"YC REST API failed: {e}")
            return []

    def _parse_api_response(self, data: Any) -> List[Job]:
        jobs: List[Job] = []
        items = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
        for item in items:
            company_data = item.get("company", {}) if isinstance(item, dict) else {}
            job = Job(
                company=company_data.get("name", item.get("company", "Unknown")),
                role=item.get("title", item.get("role", "")),
                source=self.name,
                job_url=item.get("url", item.get("jobUrl", "")),
                description=item.get("description", ""),
                location=item.get("location", company_data.get("location", "")),
                company_size=str(company_data.get("size", item.get("company_size", ""))),
                company_stage=item.get("stage", company_data.get("stage", "seed")),
                posted_date=self._parse_posted_date(item.get("createdAt", "")),
            )
            jobs.append(job)
        return jobs

    def estimate_total_jobs(self) -> int:
        return 100
