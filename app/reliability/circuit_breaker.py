import time
from enum import Enum
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable[[], T]) -> T:
        now = time.time()
        if self.state == CircuitState.OPEN and now - self.last_failure_time < self.recovery_time:
            raise CircuitOpenError("circuit open")
        if self.state == CircuitState.OPEN:
            self.state = CircuitState.HALF_OPEN

        try:
            result = func()
        except Exception as exc:  # pragma: no cover - generic catch for breaker
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise exc

        # success path
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        return result


class CircuitOpenError(Exception):
    pass
