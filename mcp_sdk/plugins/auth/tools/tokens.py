from __future__ import annotations

from collections.abc import Callable
from typing import Any


def create_token(jwt_manager: Any) -> Callable[[str, list[str] | None], str]:
    def _create_token(user_id: str, roles: list[str] = None) -> str:
        """Create a new access token for a user."""
        return jwt_manager.create_access_token(user_id=user_id, roles=roles)

    return _create_token


def verify_token(jwt_manager: Any) -> Callable[[str], bool]:
    def _verify_token(token: str) -> bool:
        """Verify the validity of a token."""
        return jwt_manager.verify_token(token)

    return _verify_token
