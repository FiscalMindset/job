"""LinkedIn jobs collector."""
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
import urllib.parse
import time
import re

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class LinkedInCollector(BaseCollector):
    SEARCH_BASE = "https://www.linkedin.com/jobs/search"
    JOB_BASE = "https://www.linkedin.com/jobs/view"

    def __init__(self):
        super().__init__("linkedin")
        self.session_cookie = config.LINKEDIN_SESSION_COOKIE

    def _collect_impl(self) -> List[Job]:
        all_jobs: List[Job] = []
        keywords = " OR ".join(config.TARGET_ROLES) if config.TARGET_ROLES else "software engineer"
        location = config.PREFERRED_LOCATIONS[0] if config.PREFERRED_LOCATIONS else "United States"

        for page in range(config.LINKEDIN_MAX_PAGES):
            self._throttle()
            search_url = self._build_search_url(keywords, location, page)
            html = self._fetch_with_retry(search_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            job_cards = soup.find_all("div", class_="base-card")
            if not job_cards:
                job_cards = soup.find_all("li", class_=re.compile(r"jobs-search-results__list-item"))
            if not job_cards:
                logger.warning(f"LinkedIn: No jobs found on page {page + 1}, stopping")
                break

            for card in job_cards:
                try:
                    job = self._parse_job_card(card)
                    if job:
                        all_jobs.append(job)
                except Exception as e:
                    logger.debug(f"LinkedIn: Failed to parse card: {e}")

            time.sleep(1.5)

        logger.info(f"LinkedIn: Collected {len(all_jobs)} jobs")
        return all_jobs

    def _build_search_url(self, keywords: str, location: str, page: int = 0) -> str:
        params = {
            "keywords": keywords,
            "location": location,
            "f_TPR": "r86400",
            "f_E": "1,2",
            "position": "1",
            "pageNum": str(page),
            "start": str(page * 25),
        }
        return f"{self.SEARCH_BASE}?{urllib.parse.urlencode(params)}"

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        cookies = {}
        if self.session_cookie:
            cookies["li_at"] = self.session_cookie

        with httpx.Client(timeout=config.REQUEST_TIMEOUT, cookies=cookies) as client:
            for attempt in range(config.MAX_RETRIES):
                try:
                    resp = client.get(url, headers=self._build_headers(), follow_redirects=True)
                    if resp.status_code == 200:
                        return resp.text
                    if resp.status_code == 429:
                        logger.warning(f"LinkedIn rate limited (attempt {attempt + 1})")
                        self._exponential_backoff(attempt)
                        continue
                    logger.warning(f"LinkedIn returned {resp.status_code}")
                except httpx.TimeoutException:
                    logger.warning(f"LinkedIn timeout (attempt {attempt + 1})")
                    self._exponential_backoff(attempt)
                except Exception as e:
                    logger.warning(f"LinkedIn request failed: {e}")
                    self._exponential_backoff(attempt)
        return None

    def _parse_job_card(self, card) -> Optional[Job]:
        title_elem = card.find("h3", class_="base-search-card__title")
        company_elem = card.find("h4", class_="base-search-card__subtitle")
        location_elem = card.find("span", class_="job-search-card__location")
        link_elem = card.find("a", class_="base-card__full-link")
        date_elem = card.find("time")

        if not title_elem or not company_elem:
            return None

        title = title_elem.text.strip()
        company = company_elem.text.strip()
        location = location_elem.text.strip() if location_elem else ""
        job_url = link_elem["href"] if link_elem else ""
        if job_url and not job_url.startswith("http"):
            job_url = f"https://www.linkedin.com{job_url}"

        posted_date = None
        if date_elem and date_elem.get("datetime"):
            posted_date = self._parse_posted_date(date_elem["datetime"])

        return Job(
            company=company,
            role=title,
            source=self.name,
            job_url=job_url,
            location=location,
            posted_date=posted_date,
        )

    def estimate_total_jobs(self) -> int:
        return config.LINKEDIN_MAX_PAGES * 25
