from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.plugins.auth.manager import JWTManager, RBACManager

if TYPE_CHECKING:
    from mcp_sdk.core.registry import PluginRegistry


class Plugin(MCPPlugin):
    """
    Auth Plugin integrating JWTManager and RBACManager.
    """

    @property
    def name(self) -> str:
        return "auth"

    def on_configure(self, manifest: dict[str, Any], path: Path | None = None) -> None:
        super().on_configure(manifest, path)
        # Initialize managers with default or config values
        self.jwt = JWTManager(secret_key=self.config.get("secret_key", "default-secret"))
        self.rbac = RBACManager.with_default_roles()

    def register_tools(self, registry: PluginRegistry) -> None:
        """Expose auth tools."""
        from mcp_sdk.plugins.auth.tools.rbac import assign_role, check_permission
        from mcp_sdk.plugins.auth.tools.tokens import create_token, verify_token

        # Store managers on the tool modules or pass them via closures
        # For this implementation, we'll use a closure-based approach in the tools dir.

        registry.register_tool(
            f"{self.name}.create_token",
            create_token(self.jwt),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "create_token"),
        )
        registry.register_tool(
            f"{self.name}.verify_token",
            verify_token(self.jwt),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "verify_token"),
        )
        registry.register_tool(
            f"{self.name}.check_permission",
            check_permission(self.rbac),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "check_permission"),
        )
        registry.register_tool(
            f"{self.name}.assign_role",
            assign_role(self.rbac),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "assign_role"),
        )
