from __future__ import annotations

from collections.abc import Callable


def check_permission(rbac_manager) -> Callable:
    def _check_permission(user_id: str, resource: str, action: str) -> bool:
        """Check if a user has permission for a resource/action."""
        return rbac_manager.has_permission(user_id, resource, action)

    return _check_permission


def assign_role(rbac_manager) -> Callable:
    def _assign_role(user_id: str, role_name: str) -> bool:
        """Assign a role to a user."""
        try:
            rbac_manager.assign_role(user_id, role_name)
            return True
        except Exception:
            return False

    return _assign_role
