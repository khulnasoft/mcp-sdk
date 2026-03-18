"""Custom exceptions for the MCP SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
import traceback


class MCPSDKError(Exception):
    """Base exception for all MCP SDK errors."""

    def __init__(
        self, 
        message: str, 
        code: str = "MCP_ERROR",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.cause = cause
        self.traceback_str = traceback.format_exc() if cause else None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "traceback": self.traceback_str
        }


class MCPProtocolError(MCPSDKError):
    """Raised when MCP protocol violations occur."""

    def __init__(
        self, 
        message: str, 
        protocol_version: Optional[str] = None,
        expected: Optional[str] = None,
        received: Optional[str] = None
    ) -> None:
        details = {}
        if protocol_version:
            details["protocol_version"] = protocol_version
        if expected:
            details["expected"] = expected
        if received:
            details["received"] = received
        
        super().__init__(message, code="PROTOCOL_ERROR", details=details)


class ValidationError(MCPSDKError):
    """Raised when data validation fails."""

    def __init__(
        self, 
        message: str, 
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraint: Optional[str] = None
    ) -> None:
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        if constraint:
            details["constraint"] = constraint
            
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ConfigurationError(MCPSDKError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        config_file: Optional[str] = None
    ) -> None:
        details = {}
        if config_key:
            details["config_key"] = config_key
        if config_file:
            details["config_file"] = config_file
            
        super().__init__(message, code="CONFIG_ERROR", details=details)


class AgentNotFoundError(MCPSDKError):
    """Raised when a referenced agent cannot be found."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(
            f"Agent '{agent_id}' not found", 
            code="AGENT_NOT_FOUND",
            details={"agent_id": agent_id}
        )


class AgentAlreadyExistsError(MCPSDKError):
    """Raised when registering a duplicate agent ID."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(
            f"Agent '{agent_id}' already registered", 
            code="AGENT_EXISTS",
            details={"agent_id": agent_id}
        )


class AgentStateError(MCPSDKError):
    """Raised when agent is in invalid state for operation."""

    def __init__(
        self, 
        agent_id: str, 
        current_state: str, 
        required_state: str
    ) -> None:
        super().__init__(
            f"Agent '{agent_id}' is in '{current_state}' state, requires '{required_state}'",
            code="AGENT_STATE_ERROR",
            details={
                "agent_id": agent_id,
                "current_state": current_state,
                "required_state": required_state
            }
        )


class RuleValidationError(ValidationError):
    """Raised when a rule definition is invalid."""

    def __init__(self, message: str, rule_id: Optional[str] = None) -> None:
        details = {"rule_id": rule_id} if rule_id else {}
        super().__init__(message, code="RULE_VALIDATION_ERROR", details=details)


class RuleExecutionError(MCPSDKError):
    """Raised when a rule fails at runtime."""

    def __init__(
        self, 
        rule_id: str, 
        reason: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        details = {"rule_id": rule_id, "reason": reason}
        if context:
            details["context"] = context
            
        super().__init__(
            f"Rule '{rule_id}' execution failed: {reason}", 
            code="RULE_EXEC_ERROR",
            details=details
        )


class ChannelError(MCPSDKError):
    """Raised for inter-agent/business channel errors."""

    def __init__(
        self, 
        channel: str, 
        message: str,
        channel_type: Optional[str] = None
    ) -> None:
        details = {"channel": channel}
        if channel_type:
            details["channel_type"] = channel_type
            
        super().__init__(
            f"Channel '{channel}' error: {message}", 
            code="CHANNEL_ERROR",
            details=details
        )


class AuthenticationError(MCPSDKError):
    """Raised on authentication failures."""

    def __init__(
        self, 
        message: str = "Authentication failed",
        auth_method: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        details = {}
        if auth_method:
            details["auth_method"] = auth_method
        if user_id:
            details["user_id"] = user_id
            
        super().__init__(message, code="AUTH_ERROR", details=details)


class AuthorizationError(MCPSDKError):
    """Raised when the caller lacks permission."""

    def __init__(
        self, 
        resource: str, 
        action: str,
        user_id: Optional[str] = None,
        required_permissions: Optional[list[str]] = None
    ) -> None:
        details = {
            "resource": resource,
            "action": action
        }
        if user_id:
            details["user_id"] = user_id
        if required_permissions:
            details["required_permissions"] = required_permissions
            
        super().__init__(
            f"Not authorized to perform '{action}' on '{resource}'",
            code="AUTHZ_ERROR",
            details=details
        )


class ToolNotFoundError(MCPSDKError):
    """Raised when a tool is not registered."""

    def __init__(self, tool_name: str, available_tools: Optional[list[str]] = None) -> None:
        details = {"tool_name": tool_name}
        if available_tools:
            details["available_tools"] = available_tools
            
        super().__init__(
            f"Tool '{tool_name}' not found", 
            code="TOOL_NOT_FOUND",
            details=details
        )


class ToolExecutionError(MCPSDKError):
    """Raised when tool execution fails."""

    def __init__(
        self, 
        tool_name: str, 
        reason: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        details = {"tool_name": tool_name, "reason": reason}
        if parameters:
            details["parameters"] = parameters
            
        super().__init__(
            f"Tool '{tool_name}' execution failed: {reason}",
            code="TOOL_EXEC_ERROR",
            details=details
        )


class MemoryError(MCPSDKError):
    """Raised on memory store failures."""

    def __init__(
        self, 
        message: str,
        memory_store: Optional[str] = None,
        operation: Optional[str] = None
    ) -> None:
        details = {}
        if memory_store:
            details["memory_store"] = memory_store
        if operation:
            details["operation"] = operation
            
        super().__init__(message, code="MEMORY_ERROR", details=details)


class OrchestratorError(MCPSDKError):
    """Raised on orchestration failures."""

    def __init__(
        self, 
        message: str,
        workflow_id: Optional[str] = None,
        step: Optional[str] = None
    ) -> None:
        details = {}
        if workflow_id:
            details["workflow_id"] = workflow_id
        if step:
            details["step"] = step
            
        super().__init__(message, code="ORCHESTRATOR_ERROR", details=details)


class PluginError(MCPSDKError):
    """Raised when plugin operations fail."""

    def __init__(
        self, 
        message: str,
        plugin_name: Optional[str] = None,
        plugin_version: Optional[str] = None
    ) -> None:
        details = {}
        if plugin_name:
            details["plugin_name"] = plugin_name
        if plugin_version:
            details["plugin_version"] = plugin_version
            
        super().__init__(message, code="PLUGIN_ERROR", details=details)


class NetworkError(MCPSDKError):
    """Raised when network operations fail."""

    def __init__(
        self, 
        message: str,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None
    ) -> None:
        details = {}
        if endpoint:
            details["endpoint"] = endpoint
        if status_code:
            details["status_code"] = status_code
            
        super().__init__(message, code="NETWORK_ERROR", details=details)


class TimeoutError(MCPSDKError):
    """Raised when operations timeout."""

    def __init__(
        self, 
        operation: str,
        timeout_seconds: float,
        elapsed_seconds: Optional[float] = None
    ) -> None:
        details = {
            "operation": operation,
            "timeout_seconds": timeout_seconds
        }
        if elapsed_seconds:
            details["elapsed_seconds"] = elapsed_seconds
            
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s",
            code="TIMEOUT_ERROR",
            details=details
        )


class ResourceExhaustedError(MCPSDKError):
    """Raised when resources are exhausted."""

    def __init__(
        self, 
        resource_type: str,
        current_usage: Optional[str] = None,
        limit: Optional[str] = None
    ) -> None:
        details = {"resource_type": resource_type}
        if current_usage:
            details["current_usage"] = current_usage
        if limit:
            details["limit"] = limit
            
        super().__init__(
            f"Resource '{resource_type}' exhausted",
            code="RESOURCE_EXHAUSTED",
            details=details
        )
