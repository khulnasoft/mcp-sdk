"""Tests for Auth module."""

import pytest

from mcp_sdk.core.exceptions import AuthenticationError, AuthorizationError
from mcp_sdk.plugins.auth.manager import JWTManager, Permission, RBACManager, Role


class TestJWTManager:
    @pytest.fixture
    def jwt(self):
        return JWTManager(secret_key="test-secret-key")

    def test_create_and_decode_token(self, jwt) -> None:
        token = jwt.create_access_token(user_id="user-1", roles=["admin"])
        payload = jwt.decode_token(token)
        assert payload.sub == "user-1"
        assert "admin" in payload.roles

    def test_invalid_token_raises(self, jwt) -> None:
        with pytest.raises(AuthenticationError):
            jwt.decode_token("invalid.token.here")

    def test_verify_valid_token(self, jwt) -> None:
        token = jwt.create_access_token(user_id="bob")
        assert jwt.verify_token(token) is True

    def test_verify_invalid_token(self, jwt) -> None:
        assert jwt.verify_token("garbage") is False

    def test_tenant_in_payload(self, jwt) -> None:
        token = jwt.create_access_token(user_id="u1", tenant_id="acme")
        payload = jwt.decode_token(token)
        assert payload.tenant_id == "acme"


class TestRBACManager:
    @pytest.fixture
    def rbac(self):
        return RBACManager.with_default_roles()

    def test_default_admin_has_all_perms(self, rbac) -> None:
        rbac.assign_role("user-1", "admin")
        assert rbac.has_permission("user-1", "agents", "delete")
        assert rbac.has_permission("user-1", "any_resource", "any_action")

    def test_viewer_can_read_not_write(self, rbac) -> None:
        rbac.assign_role("user-2", "viewer")
        assert rbac.has_permission("user-2", "agents", "read")
        assert not rbac.has_permission("user-2", "agents", "write")

    def test_check_permission_raises_on_deny(self, rbac) -> None:
        rbac.assign_role("user-3", "viewer")
        with pytest.raises(AuthorizationError):
            rbac.check_permission("user-3", "agents", "delete")

    def test_revoke_role(self, rbac) -> None:
        rbac.assign_role("user-4", "admin")
        rbac.revoke_role("user-4", "admin")
        assert not rbac.has_permission("user-4", "agents", "read")

    def test_custom_role(self, rbac) -> None:
        rbac.define_role(
            Role(
                name="tool_user",
                permissions=[Permission(resource="tools", action="execute")],
            )
        )
        rbac.assign_role("user-5", "tool_user")
        assert rbac.has_permission("user-5", "tools", "execute")
        assert not rbac.has_permission("user-5", "tools", "delete")

    def test_undefined_role_assignment_raises(self, rbac) -> None:
        with pytest.raises(ValueError):
            rbac.assign_role("user-6", "nonexistent-role")
