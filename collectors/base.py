"""Base collector interface for job scrapers."""
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from core.models import Job
from observability.logger import get_logger
from observability.circuit_breaker import CircuitBreaker
import config


logger = get_logger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for job collectors.
    
    Design principles:
    - Each source = one collector
    - Collectors are stateless
    - Collectors never crash the pipeline
    - Circuit breakers prevent cascading failures
    """
    
    def __init__(self, name: str):
        self.name = name
        self.circuit_breaker = CircuitBreaker(
            name=name,
            failure_threshold=config.CIRCUIT_BREAKER_THRESHOLD,
            timeout=config.CIRCUIT_BREAKER_TIMEOUT
        )
    
    def collect(self) -> List[Job]:
        """
        Collect jobs from this source.
        
        Returns:
            List of Job objects (may be empty if source fails)
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.warning(f"{self.name}: Circuit breaker is OPEN, skipping")
            return []
        
        try:
            logger.info(f"{self.name}: Starting collection...")
            jobs = self._collect_impl()
            
            # Success - reset circuit breaker
            self.circuit_breaker.record_success()
            
            logger.info(f"{self.name}: Collected {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            # Failure - record in circuit breaker
            self.circuit_breaker.record_failure()
            
            logger.error(f"{self.name}: Collection failed: {e}", exc_info=True)
            return []
    
    @abstractmethod
    def _collect_impl(self) -> List[Job]:
        """
        Actual collection implementation.
        
        Must be implemented by subclasses.
        Should raise exception on failure.
        """
        pass
    
    def _parse_posted_date(self, date_str: str) -> datetime:
        """
        Parse various date formats to datetime.
        
        Common formats:
        - "2 days ago"
        - "1 week ago"
        - "2024-01-15"
        """
        import re
        from datetime import timedelta
        
        date_str = date_str.lower().strip()
        now = datetime.utcnow()
        
        # "X days ago"
        match = re.search(r'(\d+)\s*days?\s*ago', date_str)
        if match:
            days = int(match.group(1))
            return now - timedelta(days=days)
        
        # "X weeks ago"
        match = re.search(r'(\d+)\s*weeks?\s*ago', date_str)
        if match:
            weeks = int(match.group(1))
            return now - timedelta(weeks=weeks)
        
        # "X months ago"
        match = re.search(r'(\d+)\s*months?\s*ago', date_str)
        if match:
            months = int(match.group(1))
            return now - timedelta(days=months * 30)
        
        # ISO format
        try:
            return datetime.fromisoformat(date_str)
        except:
            pass
        
        # Default to now
        return now
