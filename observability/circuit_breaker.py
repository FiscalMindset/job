"""Circuit breaker pattern for fault tolerance."""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict

from observability.logger import get_logger


logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, reject all requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject all requests
    - HALF_OPEN: After timeout, try one request to test recovery
    
    Example:
        If LinkedIn scraper fails 5 times in a row, stop trying
        for 5 minutes, then test again.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 300  # seconds
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0
    
    def can_execute(self) -> bool:
        """Check if request can proceed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._should_attempt_reset():
                logger.info(f"{self.name}: Circuit breaker moving to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                return True
            else:
                return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow one test request
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"{self.name}: Circuit breaker CLOSED (service recovered)")
            self.state = CircuitState.CLOSED
        
        self.failure_count = 0
        self.success_count += 1
    
    def record_failure(self) -> None:
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            # Test failed, go back to OPEN
            logger.warning(f"{self.name}: Circuit breaker OPEN (test failed)")
            self.state = CircuitState.OPEN
        
        elif self.failure_count >= self.failure_threshold:
            # Too many failures, open circuit
            logger.error(
                f"{self.name}: Circuit breaker OPEN "
                f"({self.failure_count} failures >= {self.failure_threshold})"
            )
            self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout
    
    def get_status(self) -> Dict[str, any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }
