"""GitHub jobs collector."""
import httpx
import base64
import time
from typing import List
from datetime import datetime

from core.models import Job
from collectors.base import BaseCollector
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class GitHubCollector(BaseCollector):
    API_BASE = "https://api.github.com"

    def __init__(self):
        super().__init__("github")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": config.USER_AGENT,
        }
        if config.GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
            logger.info("GitHub: Using authenticated API (5000 req/hr)")
        else:
            logger.warning("GitHub: No token — 60 req/hr limit. Set GITHUB_TOKEN in .env")

    def _collect_impl(self) -> List[Job]:
        all_jobs: List[Job] = []

        careers_jobs = self._scrape_github_careers()
        all_jobs.extend(careers_jobs)
        logger.info(f"GitHub Careers: {len(careers_jobs)} jobs")

        hiring_jobs = self._search_hiring_repos()
        all_jobs.extend(hiring_jobs)
        logger.info(f"GitHub Hiring Repos: {len(hiring_jobs)} jobs")

        return all_jobs

    def _scrape_github_careers(self) -> List[Job]:
        jobs: List[Job] = []
        try:
            resp = httpx.get(
                "https://github.com/about/careers",
                headers=self.headers,
                timeout=config.REQUEST_TIMEOUT,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return jobs

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            title_elements = soup.find_all(["h2", "h3", "a", "span"])
            seen_urls = set()

            for el in title_elements:
                text = el.get_text(strip=True)
                if not text:
                    continue
                if not any(kw in text.lower() for kw in ["engineer", "developer", "backend", "frontend", "ml", "ai", "software"]):
                    continue
                href = None
                if el.name == "a" and el.get("href"):
                    href = el["href"]
                elif el.parent and el.parent.name == "a" and el.parent.get("href"):
                    href = el.parent["href"]

                if href and ("careers" in href or "jobs" in href):
                    if not href.startswith("http"):
                        href = f"https://github.com{href}"
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    jobs.append(Job(
                        company="GitHub",
                        role=text,
                        job_url=href,
                        source=self.name,
                        location="Remote",
                        posted_date=datetime.utcnow(),
                        description=f"GitHub Careers: {text}",
                    ))
                    if len(jobs) >= 8:
                        break
        except Exception as e:
            logger.error(f"GitHub Careers scrape failed: {e}")
        return jobs

    def _search_hiring_repos(self) -> List[Job]:
        jobs: List[Job] = []
        keywords = [
            "hiring+engineers",
            "we+are+hiring",
            "join+our+team",
            "now+hiring",
            "careers+page",
            "job+opening",
        ]

        for keyword in keywords[:3]:
            try:
                params = {
                    "q": f"{keyword} in:readme",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": 10,
                }
                resp = httpx.get(
                    f"{self.API_BASE}/search/repositories",
                    headers=self.headers,
                    params=params,
                    timeout=30,
                )

                if resp.status_code == 403:
                    logger.warning("GitHub API rate limit hit")
                    break
                if resp.status_code != 200:
                    continue

                items = resp.json().get("items", [])
                for repo in items[:5]:
                    try:
                        company = repo.get("owner", {}).get("login", "Unknown")
                        repo_name = repo.get("name", "")
                        html_url = repo.get("html_url", "")
                        description = repo.get("description", "")
                        updated = repo.get("updated_at", "")

                        readme_url = f"{self.API_BASE}/repos/{company}/{repo_name}/readme"
                        readme_resp = httpx.get(readme_url, headers=self.headers, timeout=15)
                        if readme_resp.status_code != 200:
                            continue

                        readme_json = readme_resp.json()
                        readme_content = base64.b64decode(readme_json.get("content", "")).decode("utf-8", errors="replace")

                        if any(word in readme_content.lower() for word in ["hiring", "careers", "jobs", "join us", "we are looking"]):
                            posted = None
                            if updated:
                                try:
                                    posted = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                                except (ValueError, TypeError):
                                    pass
                            jobs.append(Job(
                                company=company.title(),
                                role=f"Engineering Position — {repo_name}",
                                job_url=html_url,
                                source=self.name,
                                location="Remote",
                                posted_date=posted or datetime.utcnow(),
                                description=f"{description or ''}\n\nRepo: {repo_name}\nHiring info in README",
                            ))
                        time.sleep(0.3)
                    except Exception as e:
                        logger.debug(f"GitHub repo parse error: {e}")
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"GitHub search failed for '{keyword}': {e}")

        return jobs

    def estimate_total_jobs(self) -> int:
        return 30
