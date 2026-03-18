"""
Security Middleware for MCP SDK
===============================
Provides authentication and authorization middleware for HTTP and WebSocket connections.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPBearer

from .auth import AuthenticationError, SecurityManager, get_security_manager

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


class AuthenticationMiddleware:
    """Middleware for HTTP authentication."""

    def __init__(self, security_manager: SecurityManager | None = None) -> None:
        self.security_manager = security_manager or get_security_manager()

    async def authenticate_request(self, request: Request) -> dict[str, Any]:
        """Authenticate HTTP request and return user info."""
        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split(" ")[1]

        try:
            user = await self.security_manager.auth_manager.validate_token(token)
            return {
                "user_id": user.user_id,
                "username": user.username,
                "roles": user.roles,
                "authenticated": True,
            }
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )


class AuthorizationMiddleware:
    """Middleware for HTTP authorization."""

    def __init__(self, security_manager: SecurityManager | None = None) -> None:
        self.security_manager = security_manager or get_security_manager()

    async def authorize_request(
        self,
        request: Request,
        required_permission: str,
        resource: str | None = None,
    ) -> dict[str, Any]:
        """Authorize HTTP request for specific permission."""
        # First authenticate
        auth_middleware = AuthenticationMiddleware(self.security_manager)
        auth_info = await auth_middleware.authenticate_request(request)

        # Get user from auth info
        user = self.security_manager.auth_manager._users.get(auth_info["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Check permission
        has_permission = await self.security_manager.authz_manager.check_permission(
            user, required_permission, resource
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_permission}",
            )

        auth_info["authorized"] = True
        return auth_info


class SecurityHeadersMiddleware:
    """Middleware for adding security headers to HTTP responses."""

    def __init__(self) -> None:
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

    async def add_security_headers(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        for header, value in self.security_headers.items():
            response.headers[header] = value

        return response


class RateLimitMiddleware:
    """Middleware for rate limiting requests."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self._client_requests: dict[str, list[float]] = {}

    async def rate_limit_request(self, request: Request) -> None:
        """Check if request should be rate limited."""
        client_ip = self._get_client_ip(request)
        current_time = asyncio.get_event_loop().time()

        # Clean old requests
        self._cleanup_old_requests(client_ip, current_time)

        # Get recent requests
        recent_requests = self._client_requests.get(client_ip, [])

        # Check minute limit
        minute_ago = current_time - 60
        minute_requests = [r for r in recent_requests if r > minute_ago]

        if len(minute_requests) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded (per minute)",
                headers={"Retry-After": "60"},
            )

        # Check hour limit
        hour_ago = current_time - 3600
        hour_requests = [r for r in recent_requests if r > hour_ago]

        if len(hour_requests) >= self.requests_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded (per hour)",
                headers={"Retry-After": "3600"},
            )

        # Add current request
        recent_requests.append(current_time)
        self._client_requests[client_ip] = recent_requests

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client IP
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, client_ip: str, current_time: float) -> None:
        """Clean up old request records."""
        if client_ip not in self._client_requests:
            return

        hour_ago = current_time - 3600
        requests = self._client_requests[client_ip]
        self._client_requests[client_ip] = [r for r in requests if r > hour_ago]


class AuditMiddleware:
    """Middleware for auditing security events."""

    def __init__(self) -> None:
        self._audit_log = []

    async def log_security_event(
        self,
        event_type: str,
        request: Request,
        user: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event."""
        event = {
            "timestamp": asyncio.get_event_loop().time(),
            "event_type": event_type,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent"),
            "path": request.url.path,
            "method": request.method,
            "user": user,
            "details": details or {},
        }

        self._audit_log.append(event)

        # Keep only last 10000 events
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-10000:]

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


class WebSocketSecurityMiddleware:
    """Security middleware for WebSocket connections."""

    def __init__(self, security_manager: SecurityManager | None = None) -> None:
        self.security_manager = security_manager or get_security_manager()

    async def authenticate_websocket(self, websocket, token: str) -> dict[str, Any]:
        """Authenticate WebSocket connection."""
        try:
            user = await self.security_manager.auth_manager.validate_token(token)
            return {
                "user_id": user.user_id,
                "username": user.username,
                "roles": user.roles,
                "authenticated": True,
            }
        except AuthenticationError as e:
            await websocket.close(code=4001, reason=str(e))
            raise

    async def authorize_websocket(
        self,
        websocket,
        auth_info: dict[str, Any],
        required_permission: str,
        resource: str | None = None,
    ) -> bool:
        """Authorize WebSocket connection for specific permission."""
        user = self.security_manager.auth_manager._users.get(auth_info["user_id"])
        if not user:
            await websocket.close(code=4003, reason="User not found")
            return False

        has_permission = await self.security_manager.authz_manager.check_permission(
            user, required_permission, resource
        )

        if not has_permission:
            await websocket.close(code=4003, reason="Insufficient permissions")
            return False

        return True


# Decorator for requiring authentication
def require_auth(func):
    """Decorator to require authentication for a function."""
    async def wrapper(request: Request, *args, **kwargs):
        auth_middleware = AuthenticationMiddleware()
        auth_info = await auth_middleware.authenticate_request(request)
        kwargs["auth_info"] = auth_info
        return await func(request, *args, **kwargs)
    return wrapper


# Decorator for requiring specific permission
def require_permission(permission: str, resource: str | None = None):
    """Decorator to require specific permission for a function."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            authz_middleware = AuthorizationMiddleware()
            auth_info = await authz_middleware.authorize_request(
                request, permission, resource
            )
            kwargs["auth_info"] = auth_info
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# Decorator for rate limiting
def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 1000):
    """Decorator to apply rate limiting to a function."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            rate_limit_middleware = RateLimitMiddleware(
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour
            )
            await rate_limit_middleware.rate_limit_request(request)
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
