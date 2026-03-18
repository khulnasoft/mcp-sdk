"""
Auth Module — JWT + RBAC
=========================
Provides JWT-based authentication and Role-Based Access Control (RBAC)
for securing agent interactions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel

from mcp_sdk.core.exceptions import AuthenticationError, AuthorizationError

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #


class Permission(BaseModel):
    resource: str
    action: str  # read, write, execute, admin


class Role(BaseModel):
    name: str
    permissions: list[Permission] = []

    def has_permission(self, resource: str, action: str) -> bool:
        for perm in self.permissions:
            r_match = perm.resource in ("*", resource)
            a_match = perm.action in ("*", action, "admin")
            if r_match and a_match:
                return True
        return False


class TokenPayload(BaseModel):
    sub: str  # subject (user_id)
    exp: datetime
    roles: list[str] = []
    tenant_id: str | None = None
    metadata: dict[str, Any] = {}


# ------------------------------------------------------------------ #
#  JWT Manager                                                         #
# ------------------------------------------------------------------ #


class JWTManager:
    """Issue and validate JWT tokens for agent auth."""

    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        self._secret = secret_key
        self._algorithm = algorithm

    def create_access_token(
        self,
        user_id: str,
        roles: list[str] | None = None,
        tenant_id: str | None = None,
        expires_minutes: int = 30,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        from jose import jwt  # type: ignore

        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "exp": now + timedelta(minutes=expires_minutes),
            "iat": now,
            "roles": roles or [],
            "tenant_id": tenant_id,
            "metadata": metadata or {},
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        from jose import JWTError, jwt  # type: ignore

        try:
            raw = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            return TokenPayload(**raw)
        except JWTError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

    def verify_token(self, token: str) -> bool:
        try:
            self.decode_token(token)
            return True
        except AuthenticationError:
            return False


# ------------------------------------------------------------------ #
#  RBAC Manager                                                        #
# ------------------------------------------------------------------ #


class RBACManager:
    """Role-Based Access Control manager."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {}
        self._user_roles: dict[str, list[str]] = {}

    def define_role(self, role: Role) -> None:
        self._roles[role.name] = role
        logger.debug("Role defined", role=role.name)

    def assign_role(self, user_id: str, role_name: str) -> None:
        if role_name not in self._roles:
            raise ValueError(f"Role '{role_name}' not defined")
        self._user_roles.setdefault(user_id, [])
        if role_name not in self._user_roles[user_id]:
            self._user_roles[user_id].append(role_name)

    def revoke_role(self, user_id: str, role_name: str) -> None:
        if user_id in self._user_roles:
            self._user_roles[user_id] = [r for r in self._user_roles[user_id] if r != role_name]

    def check_permission(self, user_id: str, resource: str, action: str) -> None:
        """Raise AuthorizationError if user lacks permission."""
        roles = self._user_roles.get(user_id, [])
        for role_name in roles:
            role = self._roles.get(role_name)
            if role and role.has_permission(resource, action):
                return
        raise AuthorizationError(resource, action)

    def has_permission(self, user_id: str, resource: str, action: str) -> bool:
        try:
            self.check_permission(user_id, resource, action)
            return True
        except AuthorizationError:
            return False

    @classmethod
    def with_default_roles(cls) -> RBACManager:
        """Create a manager with sensible default roles."""
        manager = cls()
        manager.define_role(Role(name="admin", permissions=[Permission(resource="*", action="*")]))
        manager.define_role(
            Role(
                name="agent_operator",
                permissions=[
                    Permission(resource="agents", action="read"),
                    Permission(resource="agents", action="execute"),
                    Permission(resource="workflows", action="execute"),
                ],
            )
        )
        manager.define_role(
            Role(
                name="viewer",
                permissions=[
                    Permission(resource="agents", action="read"),
                    Permission(resource="workflows", action="read"),
                ],
            )
        )
        return manager
