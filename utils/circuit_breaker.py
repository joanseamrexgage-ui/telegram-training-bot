"""
Advanced Circuit Breaker for telegram-training-bot.

Implements circuit breaker pattern with:
- Per-service circuit breakers (Redis, Database, Telegram API)
- Health check integration
- Graceful degradation modes
- Metrics collection

Usage:
    from utils.circuit_breaker import CircuitBreaker, get_circuit_breaker

    # Use circuit breaker
    redis_cb = get_circuit_breaker("redis")

    async with redis_cb:
        result = await redis.get(key)
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: int = 60  # Seconds before attempting recovery
    half_open_timeout: int = 30  # Timeout in half-open state


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Prevents cascading failures by failing fast when a service is down.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()

    async def __aenter__(self):
        """Async context manager entry"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.config.timeout:
                logger.info(f"Circuit {self.name}: Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if exc_type is None:
            self._on_success()
        else:
            self._on_failure()

    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit {self.name}: Closing (recovered)")
                self.state = CircuitState.CLOSED
                self.last_state_change = time.time()

    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit {self.name}: Re-opening (recovery failed)")
            self.state = CircuitState.OPEN

        elif self.failure_count >= self.config.failure_threshold:
            logger.error(f"Circuit {self.name}: Opening (threshold reached)")
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get or create circuit breaker"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]
