"""Base collector interface for job scrapers."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import re
import time

from core.models import Job
from observability.logger import get_logger
from observability.circuit_breaker import CircuitBreaker
import config


logger = get_logger(__name__)


class CollectorError(Exception):
    def __init__(self, message: str, source: str, status_code: Optional[int] = None, recoverable: bool = True):
        self.message = message
        self.source = source
        self.status_code = status_code
        self.recoverable = recoverable
        super().__init__(f"[{source}] {message}")


class RateLimitError(CollectorError):
    def __init__(self, source: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__("Rate limited", source, status_code=429)


class BaseCollector(ABC):
    def __init__(self, name: str):
        self.name = name
        self._last_request_time: float = 0.0
        self.circuit_breaker = CircuitBreaker(
            name=name,
            failure_threshold=config.CIRCUIT_BREAKER_THRESHOLD,
            timeout=config.CIRCUIT_BREAKER_TIMEOUT,
        )
        self.base_delay = 1.0
        self._request_count = 0

    def collect(self) -> List[Job]:
        if not self.circuit_breaker.can_execute():
            logger.warning(f"{self.name}: Circuit breaker is OPEN, skipping")
            return []
        try:
            logger.info(f"{self.name}: Starting collection...")
            self._request_count = 0
            jobs = self._collect_impl()
            self.circuit_breaker.record_success()
            logger.info(f"{self.name}: Collected {len(jobs)} jobs")
            return jobs
        except CollectorError as e:
            self.circuit_breaker.record_failure()
            if e.recoverable:
                logger.warning(f"{self.name}: Recoverable error: {e.message}")
            else:
                logger.error(f"{self.name}: Unrecoverable error: {e.message}")
            return []
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"{self.name}: Collection failed: {e}", exc_info=True)
            return []

    @abstractmethod
    def _collect_impl(self) -> List[Job]:
        pass

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.base_delay:
            time.sleep(self.base_delay - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _exponential_backoff(self, attempt: int, base: float = 2.0) -> None:
        delay = min(base ** attempt, 30.0)
        logger.debug(f"{self.name}: Backing off {delay:.1f}s (attempt {attempt})")
        time.sleep(delay)

    def _parse_posted_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.lower().strip()
        now = datetime.utcnow()
        patterns = [
            (r'(\d+)\s*days?\s*ago', lambda m: now - timedelta(days=int(m.group(1)))),
            (r'(\d+)\s*weeks?\s*ago', lambda m: now - timedelta(weeks=int(m.group(1)))),
            (r'(\d+)\s*months?\s*ago', lambda m: now - timedelta(days=int(m.group(1)) * 30)),
            (r'(\d+)\s*years?\s*ago', lambda m: now - timedelta(days=int(m.group(1)) * 365)),
            (r'just\s+now', lambda m: now),
            (r'today', lambda m: now),
            (r'yesterday', lambda m: now - timedelta(days=1)),
            (r'(\d{4}-\d{2}-\d{2})', lambda m: datetime.fromisoformat(m.group(1))),
            (r'(\d{2}/\d{2}/\d{4})', lambda m: datetime.strptime(m.group(1), "%m/%d/%Y")),
        ]
        for pattern, handler in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return handler(match)
                except (ValueError, TypeError):
                    continue
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass
        return now

    def _build_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def estimate_total_jobs(self) -> int:
        return 0
