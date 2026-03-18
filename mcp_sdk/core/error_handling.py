"""
Centralized Error Handling for MCP SDK
======================================
Provides consistent error handling patterns across the SDK.
"""

from __future__ import annotations

import asyncio
import functools
import traceback
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class MCPError(BaseModel):
    """Standardized error structure for MCP operations."""

    code: str = Field(description="Error code for programmatic handling")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error context")
    traceback: str | None = Field(default=None, description="Stack trace for debugging")
    timestamp: str = Field(default_factory=lambda: structlog.get_logger().bind().info("timestamp"))


class MCPException(Exception):
    """Base exception for MCP SDK errors."""

    def __init__(
        self,
        message: str,
        code: str = "MCP_ERROR",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause

    def to_error(self) -> MCPError:
        """Convert to MCPError model."""
        return MCPError(
            code=self.code,
            message=self.message,
            details=self.details,
            traceback=traceback.format_exc() if self.cause else None,
        )


class ConfigurationError(MCPException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "CONFIG_ERROR", details)


class ValidationError(MCPException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None) -> None:
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, "VALIDATION_ERROR", details)


class PluginError(MCPException):
    """Raised when plugin operations fail."""

    def __init__(self, message: str, plugin_name: str | None = None, details: dict[str, Any] | None = None) -> None:
        details = details or {}
        if plugin_name:
            details["plugin_name"] = plugin_name
        super().__init__(message, "PLUGIN_ERROR", details)


class ProtocolError(MCPException):
    """Raised when MCP protocol operations fail."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "PROTOCOL_ERROR", details)


class AgentError(MCPException):
    """Raised when agent operations fail."""

    def __init__(self, message: str, agent_id: str | None = None, details: dict[str, Any] | None = None) -> None:
        details = details or {}
        if agent_id:
            details["agent_id"] = agent_id
        super().__init__(message, "AGENT_ERROR", details)


def handle_errors(
    error_code: str = "UNKNOWN_ERROR",
    reraise: bool = True,
    log_level: str = "error",
    return_on_error: Any = None,
) -> Callable:
    """
    Decorator for standardized error handling.
    
    Args:
        error_code: Error code to use for caught exceptions
        reraise: Whether to reraise the exception after logging
        log_level: Logging level for the error
        return_on_error: Value to return if reraise=False and an error occurs
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {str(e)}"
                getattr(logger, log_level)(error_msg, exc_info=True)

                if reraise:
                    if isinstance(e, MCPException):
                        raise
                    else:
                        raise MCPException(error_msg, error_code, {"original_error": str(e)}, e) from e
                else:
                    return return_on_error

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {str(e)}"
                getattr(logger, log_level)(error_msg, exc_info=True)

                if reraise:
                    if isinstance(e, MCPException):
                        raise
                    else:
                        raise MCPException(error_msg, error_code, {"original_error": str(e)}, e) from e
                else:
                    return return_on_error

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


@asynccontextmanager
async def error_context(
    operation: str,
    error_code: str = "UNKNOWN_ERROR",
    details: dict[str, Any] | None = None,
):
    """
    Context manager for error handling in async operations.
    
    Args:
        operation: Description of the operation being performed
        error_code: Error code to use if an exception occurs
        details: Additional context to include in error details
    """
    try:
        logger.info(f"Starting operation: {operation}")
        yield
        logger.info(f"Completed operation: {operation}")
    except Exception as e:
        error_details = details or {}
        error_details["operation"] = operation

        logger.error(f"Operation failed: {operation}", exc_info=True)

        if isinstance(e, MCPException):
            raise
        else:
            raise MCPException(
                f"Operation '{operation}' failed: {str(e)}",
                error_code,
                error_details,
                e,
            ) from e


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    default: T | None = None,
    error_code: str = "EXECUTION_ERROR",
    **kwargs: Any,
) -> T | None:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        default: Default value to return on error
        error_code: Error code for error reporting
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Safe execution failed for {func.__name__}", exc_info=True)
        if default is not None:
            return default
        raise MCPException(
            f"Safe execution failed: {str(e)}",
            error_code,
            {"function": func.__name__, "args": args, "kwargs": kwargs},
            e,
        ) from e


async def safe_execute_async(
    func: Callable[..., T],
    *args: Any,
    default: T | None = None,
    error_code: str = "ASYNC_EXECUTION_ERROR",
    **kwargs: Any,
) -> T | None:
    """
    Safely execute an async function with error handling.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        default: Default value to return on error
        error_code: Error code for error reporting
        **kwargs: Keyword arguments for the function
        
    Returns:
        Function result or default value on error
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Safe async execution failed for {func.__name__}", exc_info=True)
        if default is not None:
            return default
        raise MCPException(
            f"Safe async execution failed: {str(e)}",
            error_code,
            {"function": func.__name__, "args": args, "kwargs": kwargs},
            e,
        ) from e


class ErrorCollector:
    """Collects and manages multiple errors during batch operations."""

    def __init__(self) -> None:
        self.errors: list[MCPError] = []

    def add_error(
        self,
        message: str,
        code: str = "COLLECTED_ERROR",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Add an error to the collection."""
        error = MCPError(
            code=code,
            message=message,
            details=details or {},
            traceback=traceback.format_exc() if cause else None,
        )
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Check if any errors have been collected."""
        return len(self.errors) > 0

    def get_errors(self) -> list[MCPError]:
        """Get all collected errors."""
        return self.errors.copy()

    def clear(self) -> None:
        """Clear all collected errors."""
        self.errors.clear()

    def raise_if_has_errors(self, aggregate_message: str = "Multiple errors occurred") -> None:
        """Raise an exception if errors have been collected."""
        if self.has_errors():
            raise MCPException(
                aggregate_message,
                "MULTIPLE_ERRORS",
                {"error_count": len(self.errors), "errors": [e.dict() for e in self.errors]},
            )
