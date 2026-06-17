"""Naukri.com job collector for Indian job market."""
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime, timedelta
import time
import re

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class NaukriCollector(BaseCollector):
    BASE = "https://www.naukri.com"

    def __init__(self):
        super().__init__("naukri")

    def _collect_impl(self) -> List[Job]:
        all_jobs: List[Job] = []
        keywords = ["software engineer", "backend engineer", "ai engineer", "ml engineer", "full stack developer"]

        for keyword in keywords[:3]:
            for page in range(1, 4):
                self._throttle()
                url = self._build_url(keyword, page)
                html = self._fetch_with_retry(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")
                cards = soup.find_all("article", class_=lambda x: x and "jobTuple" in str(x))
                if not cards:
                    cards = soup.find_all("div", class_=lambda x: x and "srp-jobtuple" in str(x))
                if not cards:
                    logger.warning(f"Naukri: No cards on page {page} for '{keyword}'")
                    break

                for card in cards:
                    try:
                        job = self._parse_card(card)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        logger.debug(f"Naukri parse error: {e}")

                time.sleep(1.5)
            time.sleep(2)

        logger.info(f"Naukri: Collected {len(all_jobs)} jobs")
        return all_jobs

    def _build_url(self, keyword: str, page: int = 1) -> str:
        params = {
            "k": keyword.replace(" ", "%20"),
            "experience": str(config.MIN_EXPERIENCE_YEARS),
            "x-axis": str(config.MAX_EXPERIENCE_YEARS),
            "sort": "1",
            "page": str(page),
        }
        if config.PREFERRED_LOCATIONS and config.PREFERRED_LOCATIONS[0].lower() not in ["remote", "united states"]:
            params["l"] = config.PREFERRED_LOCATIONS[0].replace(" ", "%20")
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE}/jobs-in-india?{qs}"

    def _parse_card(self, card) -> Optional[Job]:
        title_el = card.find("a", class_=lambda x: x and "title" in str(x)) or card.find("h2")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        if url and not url.startswith("http"):
            url = f"{self.BASE}{url}"

        company_el = card.find("a", class_=lambda x: x and "comp" in str(x)) or card.find("div", class_=lambda x: x and "comp" in str(x))
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        loc_el = card.find("li", class_=lambda x: x and "loc" in str(x)) or card.find("span", class_=lambda x: x and "loc" in str(x))
        location = loc_el.get_text(strip=True) if loc_el else "India"

        exp_el = card.find("li", class_=lambda x: x and "exp" in str(x))
        experience = exp_el.get_text(strip=True) if exp_el else ""

        sal_el = card.find("li", class_=lambda x: x and "sal" in str(x)) or card.find("span", class_=lambda x: x and "sal" in str(x))
        salary = sal_el.get_text(strip=True) if sal_el else ""

        desc_el = card.find("div", class_=lambda x: x and "desc" in str(x)) or card.find("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        date_el = card.find("span", class_=lambda x: x and "date" in str(x))
        posted_date = self._parse_naukri_date(date_el.get_text(strip=True)) if date_el else None

        skills_el = card.find("ul", class_=lambda x: x and "tag" in str(x))
        skills = []
        if skills_el:
            skills = [s.get_text(strip=True) for s in skills_el.find_all("li")]

        full_desc = description
        if experience:
            full_desc += f"\nExperience: {experience}"
        if salary:
            full_desc += f"\nSalary: {salary}"
        if skills:
            full_desc += f"\nSkills: {', '.join(skills)}"

        return Job(
            company=company,
            role=title,
            source=self.name,
            job_url=url,
            location=location,
            posted_date=posted_date,
            description=full_desc.strip(),
            tags=skills,
        )

    def _parse_naukri_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.lower().strip()
        now = datetime.utcnow()
        if "just now" in date_str or "today" in date_str:
            return now
        if "yesterday" in date_str:
            return now - timedelta(days=1)
        m = re.search(r"(\d+)\s*day", date_str)
        if m:
            return now - timedelta(days=int(m.group(1)))
        m = re.search(r"(\d+)\s*week", date_str)
        if m:
            return now - timedelta(weeks=int(m.group(1)))
        m = re.search(r"(\d+)\s*month", date_str)
        if m:
            return now - timedelta(days=int(m.group(1)) * 30)
        return now

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        for attempt in range(config.MAX_RETRIES):
            try:
                with httpx.Client(timeout=config.REQUEST_TIMEOUT, follow_redirects=True) as client:
                    resp = client.get(url, headers=self._build_headers(self.BASE))
                    if resp.status_code == 200:
                        return resp.text
                    logger.warning(f"Naukri HTTP {resp.status_code}")
            except httpx.TimeoutException:
                logger.warning(f"Naukri timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.warning(f"Naukri error: {e}")
            self._exponential_backoff(attempt)
        return None

    def estimate_total_jobs(self) -> int:
        return 150
