"""
Authentication and Authorization for MCP SDK
============================================
Provides JWT-based authentication and RBAC authorization.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from pydantic import BaseModel, Field

from ..core.error_handling import MCPException, handle_errors

logger = __import__("structlog").get_logger(__name__)


class AuthenticationError(MCPException):
    """Raised when authentication fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(MCPException):
    """Raised when authorization fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "AUTHORIZATION_ERROR")


class User(BaseModel):
    """User model for authentication."""

    id: str
    username: str
    email: str
    password_hash: str
    roles: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenInfo(BaseModel):
    """JWT token information."""

    user_id: str
    username: str
    roles: list[str]
    permissions: list[str]
    issued_at: datetime
    expires_at: datetime
    token_type: str = "access"


class Permission(BaseModel):
    """Permission model."""

    name: str
    description: str = ""
    resource: str = "*"
    action: str = "*"


class Role(BaseModel):
    """Role model for RBAC."""

    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    is_system_role: bool = False


class AuthenticationManager:
    """Manages user authentication and token generation."""

    def __init__(
        self,
        secret_key: str | None = None,
        token_expiry_hours: int = 24,
        password_min_length: int = 8,
    ) -> None:
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.token_expiry_hours = token_expiry_hours
        self.password_min_length = password_min_length
        self._users: dict[str, User] = {}
        self._refresh_tokens: dict[str, str] = {}  # refresh_token -> user_id

    @handle_errors("USER_CREATION_ERROR")
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """Create a new user."""
        if len(password) < self.password_min_length:
            raise AuthenticationError(
                f"Password must be at least {self.password_min_length} characters"
            )

        # Check if user already exists
        for user in self._users.values():
            if user.username == username or user.email == email:
                raise AuthenticationError("User with this username or email already exists")

        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        user = User(
            id=secrets.token_urlsafe(16),
            username=username,
            email=email,
            password_hash=password_hash,
            roles=roles or [],
        )

        self._users[user.id] = user
        logger.info("User created", user_id=user.id, username=username)

        return user

    @handle_errors("AUTHENTICATION_ERROR")
    async def authenticate(self, username: str, password: str) -> tuple[User, str]:
        """Authenticate user and return access token."""
        user = None
        for u in self._users.values():
            if u.username == username:
                user = u
                break

        if not user or not user.is_active:
            raise AuthenticationError("Invalid username or password")

        if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            raise AuthenticationError("Invalid username or password")

        # Update last login
        user.last_login = datetime.now(UTC)

        # Generate tokens
        access_token = await self._generate_access_token(user)
        refresh_token = secrets.token_urlsafe(32)
        self._refresh_tokens[refresh_token] = user.id

        logger.info("User authenticated", user_id=user.id, username=username)

        return user, access_token

    async def _generate_access_token(self, user: User) -> str:
        """Generate JWT access token."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=self.token_expiry_hours)

        payload = {
            "user_id": user.id,
            "username": user.username,
            "roles": user.roles,
            "exp": expires_at,
            "iat": now,
            "type": "access"
        }

        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    @handle_errors("TOKEN_VALIDATION_ERROR")
    async def validate_token(self, token: str) -> TokenInfo:
        """Validate JWT token and return token info."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # Check token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            # Check expiration
            exp = datetime.fromtimestamp(payload["exp"], UTC)
            if exp < datetime.now(UTC):
                raise AuthenticationError("Token has expired")

            # Get user
            user = self._users.get(payload["user_id"])
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            return TokenInfo(
                user_id=user.id,
                username=user.username,
                roles=user.roles,
                permissions=[],  # Will be filled by authorization manager
                issued_at=datetime.fromtimestamp(payload["iat"], UTC),
                expires_at=exp,
            )

        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    async def refresh_token(self, refresh_token: str) -> str:
        """Refresh access token using refresh token."""
        user_id = self._refresh_tokens.get(refresh_token)
        if not user_id:
            raise AuthenticationError("Invalid refresh token")

        user = self._users.get(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Generate new access token
        return await self._generate_access_token(user)

    async def revoke_token(self, refresh_token: str) -> None:
        """Revoke refresh token."""
        if refresh_token in self._refresh_tokens:
            del self._refresh_tokens[refresh_token]


class AuthorizationManager:
    """Manages role-based access control (RBAC)."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {}
        self._permissions: dict[str, Permission] = {}
        self._role_permissions: dict[str, set[str]] = {}

        # Initialize default roles and permissions
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default system roles and permissions."""
        # Default permissions
        permissions = [
            Permission(name="read", description="Read access", resource="*", action="read"),
            Permission(name="write", description="Write access", resource="*", action="write"),
            Permission(name="execute", description="Execute access", resource="*", action="execute"),
            Permission(name="admin", description="Administrative access", resource="*", action="*"),
        ]

        for perm in permissions:
            self._permissions[perm.name] = perm

        # Default roles
        roles = [
            Role(name="admin", description="System administrator", permissions=["admin"], is_system_role=True),
            Role(name="user", description="Regular user", permissions=["read", "write"], is_system_role=True),
            Role(name="guest", description="Guest user", permissions=["read"], is_system_role=True),
        ]

        for role in roles:
            self._roles[role.name] = role
            self._role_permissions[role.name] = set(role.permissions)

    @handle_errors("ROLE_CREATION_ERROR")
    async def create_role(self, name: str, description: str, permissions: list[str]) -> Role:
        """Create a new role."""
        if name in self._roles:
            raise MCPException("Role already exists", "ROLE_EXISTS")

        # Validate permissions
        for perm_name in permissions:
            if perm_name not in self._permissions:
                raise MCPException(f"Permission '{perm_name}' not found", "PERMISSION_NOT_FOUND")

        role = Role(name=name, description=description, permissions=permissions)
        self._roles[name] = role
        self._role_permissions[name] = set(permissions)

        logger.info("Role created", role=name, permissions=permissions)

        return role

    @handle_errors("PERMISSION_CREATION_ERROR")
    async def create_permission(self, name: str, description: str, resource: str, action: str) -> Permission:
        """Create a new permission."""
        if name in self._permissions:
            raise MCPException("Permission already exists", "PERMISSION_EXISTS")

        permission = Permission(name=name, description=description, resource=resource, action=action)
        self._permissions[name] = permission

        logger.info("Permission created", permission=name, resource=resource, action=action)

        return permission

    async def assign_role_to_user(self, user: User, role_name: str) -> None:
        """Assign a role to a user."""
        if role_name not in self._roles:
            raise MCPException(f"Role '{role_name}' not found", "ROLE_NOT_FOUND")

        if role_name not in user.roles:
            user.roles.append(role_name)
            logger.info("Role assigned to user", user_id=user.id, role=role_name)

    async def remove_role_from_user(self, user: User, role_name: str) -> None:
        """Remove a role from a user."""
        if role_name in user.roles:
            user.roles.remove(role_name)
            logger.info("Role removed from user", user_id=user.id, role=role_name)

    async def check_permission(
        self,
        user: User,
        permission: str,
        resource: str | None = None,
        action: str | None = None,
    ) -> bool:
        """Check if user has a specific permission."""
        # Get all user permissions from roles
        user_permissions = set()
        for role_name in user.roles:
            role_perms = self._role_permissions.get(role_name, set())
            user_permissions.update(role_perms)

        # Check for admin permission (grants all access)
        if "admin" in user_permissions:
            return True

        # Check specific permission
        if permission in user_permissions:
            return True

        # Check resource/action specific permissions
        if resource and action:
            resource_action_perm = f"{resource}:{action}"
            if resource_action_perm in user_permissions:
                return True

        return False

    async def get_user_permissions(self, user: User) -> list[str]:
        """Get all permissions for a user."""
        user_permissions = set()
        for role_name in user.roles:
            role_perms = self._role_permissions.get(role_name, set())
            user_permissions.update(role_perms)

        return list(user_permissions)


class SecurityManager:
    """Main security manager combining authentication and authorization."""

    def __init__(
        self,
        secret_key: str | None = None,
        token_expiry_hours: int = 24,
        password_min_length: int = 8,
    ) -> None:
        self.auth_manager = AuthenticationManager(
            secret_key, token_expiry_hours, password_min_length
        )
        self.authz_manager = AuthorizationManager()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """Create a new user with optional roles."""
        user = await self.auth_manager.create_user(username, email, password, roles)

        # Assign default role if none provided
        if not roles:
            await self.authz_manager.assign_role_to_user(user, "user")

        return user

    async def authenticate(self, username: str, password: str) -> tuple[User, str]:
        """Authenticate user and return user with access token."""
        user, token = await self.auth_manager.authenticate(username, password)

        # Add permissions to token info
        permissions = await self.authz_manager.get_user_permissions(user)

        return user, token

    async def authorize(self, token: str, permission: str, resource: str | None = None) -> User:
        """Authorize user based on token and permission."""
        token_info = await self.auth_manager.validate_token(token)

        user = self.auth_manager._users.get(token_info.user_id)
        if not user:
            raise AuthenticationError("User not found")

        has_permission = await self.authz_manager.check_permission(
            user, permission, resource
        )

        if not has_permission:
            raise AuthorizationError(
                f"User '{user.username}' does not have permission '{permission}'"
            )

        return user

    @handle_errors("SECURITY_CHECK_ERROR")
    async def check_access(
        self,
        token: str | None,
        required_permission: str,
        resource: str | None = None,
        action: str | None = None,
    ) -> User | None:
        """Check if token provides required access."""
        if not token:
            raise AuthenticationError("No authentication token provided")

        return await self.authorize(token, required_permission, resource)


# Security context manager for operations
class SecurityContext:
    """Security context for authenticated operations."""

    def __init__(self, security_manager: SecurityManager, token: str) -> None:
        self.security_manager = security_manager
        self.token = token
        self.user: User | None = None

    async def __aenter__(self) -> User:
        """Enter security context and validate token."""
        self.user = await self.security_manager.auth_manager.validate_token(self.token)
        return self.user

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit security context."""
        pass


# Global security manager instance
_security_manager: SecurityManager | None = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


async def require_permission(permission: str, resource: str | None = None):
    """Decorator to require specific permission for a function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract token from kwargs or context
            token = kwargs.get("token") or kwargs.get("auth_token")
            if not token:
                raise AuthenticationError("No authentication token provided")

            security = get_security_manager()
            user = await security.authorize(token, permission, resource)

            # Add user to kwargs for the function
            kwargs["current_user"] = user

            return await func(*args, **kwargs)
        return wrapper
    return decorator
