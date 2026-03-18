"""
Retry Mechanisms for MCP SDK
============================
Provides configurable retry logic with exponential backoff.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

import structlog

from .error_handling import MCPException

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        MCPException,
    )


class RetryError(MCPException):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        total_delay: float,
        last_exception: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            "RETRY_EXHAUSTED",
            {
                "attempts": attempts,
                "total_delay": total_delay,
                "last_exception": str(last_exception) if last_exception else None,
            },
            last_exception,
        )
        self.attempts = attempts
        self.total_delay = total_delay
        self.last_exception = last_exception


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool = True,
) -> float:
    """
    Calculate delay for retry attempt with exponential backoff and optional jitter.
    
    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        
    Returns:
        Calculated delay in seconds
    """
    delay = base_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)

    if jitter:
        # Add up to 25% random jitter
        jitter_amount = delay * 0.25 * random.random()
        delay += jitter_amount

    return delay


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """
    Execute an async function with retry logic.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        config: Retry configuration
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all retry attempts are exhausted
    """
    if config is None:
        config = RetryConfig()

    last_exception = None
    total_delay = 0.0

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # Check if this exception is retryable
            if not isinstance(e, config.retryable_exceptions):
                logger.error(f"Non-retryable exception in {func.__name__}", exc_info=True)
                raise

            if attempt == config.max_attempts - 1:
                # Last attempt, give up
                break

            delay = calculate_delay(
                attempt,
                config.base_delay,
                config.max_delay,
                config.exponential_base,
                config.jitter,
            )
            total_delay += delay

            logger.warning(
                f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s",
                exception=str(e),
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                delay=delay,
            )

            await asyncio.sleep(delay)

    # All attempts exhausted
    raise RetryError(
        f"All {config.max_attempts} retry attempts exhausted for {func.__name__}",
        config.max_attempts,
        total_delay,
        last_exception,
    )


def retry_sync(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """
    Execute a synchronous function with retry logic.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        config: Retry configuration
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all retry attempts are exhausted
    """
    if config is None:
        config = RetryConfig()

    last_exception = None
    total_delay = 0.0

    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # Check if this exception is retryable
            if not isinstance(e, config.retryable_exceptions):
                logger.error(f"Non-retryable exception in {func.__name__}", exc_info=True)
                raise

            if attempt == config.max_attempts - 1:
                # Last attempt, give up
                break

            delay = calculate_delay(
                attempt,
                config.base_delay,
                config.max_delay,
                config.exponential_base,
                config.jitter,
            )
            total_delay += delay

            logger.warning(
                f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s",
                exception=str(e),
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                delay=delay,
            )

            time.sleep(delay)

    # All attempts exhausted
    raise RetryError(
        f"All {config.max_attempts} retry attempts exhausted for {func.__name__}",
        config.max_attempts,
        total_delay,
        last_exception,
    )


def retry(
    config: RetryConfig | None = None,
) -> Callable:
    """
    Decorator for adding retry logic to functions.
    
    Args:
        config: Retry configuration
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await retry_async(func, *args, config=config, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                return retry_sync(func, *args, config=config, **kwargs)
            return sync_wrapper
    return decorator


@asynccontextmanager
async def retry_context(
    operation: str,
    config: RetryConfig | None = None,
):
    """
    Context manager for retryable operations.
    
    Args:
        operation: Description of the operation
        config: Retry configuration
        
    Yields:
        None
        
    Raises:
        RetryError: If all retry attempts are exhausted
    """
    if config is None:
        config = RetryConfig()

    last_exception = None
    total_delay = 0.0

    for attempt in range(config.max_attempts):
        try:
            logger.info(f"Starting operation: {operation} (attempt {attempt + 1}/{config.max_attempts})")
            yield
            logger.info(f"Completed operation: {operation}")
            return
        except Exception as e:
            last_exception = e

            # Check if this exception is retryable
            if not isinstance(e, config.retryable_exceptions):
                logger.error(f"Non-retryable exception in {operation}", exc_info=True)
                raise

            if attempt == config.max_attempts - 1:
                # Last attempt, give up
                break

            delay = calculate_delay(
                attempt,
                config.base_delay,
                config.max_delay,
                config.exponential_base,
                config.jitter,
            )
            total_delay += delay

            logger.warning(
                f"Operation {operation} attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                exception=str(e),
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                delay=delay,
            )

            await asyncio.sleep(delay)

    # All attempts exhausted
    raise RetryError(
        f"All {config.max_attempts} retry attempts exhausted for operation: {operation}",
        config.max_attempts,
        total_delay,
        last_exception,
    )


class CircuitBreaker:
    """
    Circuit breaker pattern for preventing cascading failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half_open

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to apply circuit breaker to a function."""
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await self._call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                return self._call_sync(func, *args, **kwargs)
            return sync_wrapper

    async def _call_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute async function with circuit breaker."""
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker transitioning to half-open")
            else:
                raise MCPException("Circuit breaker is open", "CIRCUIT_BREAKER_OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    def _call_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute sync function with circuit breaker."""
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker transitioning to half-open")
            else:
                raise MCPException("Circuit breaker is open", "CIRCUIT_BREAKER_OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful operation."""
        if self.state == "half_open":
            self.state = "closed"
            logger.info("Circuit breaker transitioning to closed")
        self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker transitioning to open after {self.failure_count} failures"
            )
