"""Circuit breaker pattern for fault tolerance with event hooks."""
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Callable

from observability.logger import get_logger


logger = get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 300,
        on_state_change: Optional[Callable[[str, CircuitState, CircuitState], None]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.on_state_change = on_state_change
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.success_count = 0
        self.total_calls = 0
        self.total_failures = 0

    def can_execute(self) -> bool:
        self.total_calls += 1
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._set_state(CircuitState.HALF_OPEN)
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._set_state(CircuitState.CLOSED)
            logger.info(f"{self.name}: Service recovered")
        self.failure_count = 0
        self.success_count += 1

    def record_failure(self) -> None:
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.utcnow()
        if self.state == CircuitState.HALF_OPEN:
            self._set_state(CircuitState.OPEN)
            logger.warning(f"{self.name}: Test failed, back to OPEN")
        elif self.failure_count >= self.failure_threshold:
            self._set_state(CircuitState.OPEN)
            logger.error(f"{self.name}: OPEN ({self.failure_count} failures)")

    def _set_state(self, new_state: CircuitState) -> None:
        old = self.state
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(self.name, old, new_state)

    def _should_attempt_reset(self) -> bool:
        if not self.last_failure_time:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout

    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "failure_rate": round((self.total_failures / max(self.total_calls, 1)) * 100, 1),
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        logger.info(f"{self.name}: Manual reset to CLOSED")
