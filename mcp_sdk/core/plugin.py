"""
Core Plugin Interface for MCP SDK
================================
Defines the base class for all SDK extensions.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_sdk.core.registry import PluginRegistry


class MCPPlugin(abc.ABC):
    """
    Abstract base class for all MCP plugins.

    Plugins extend the SDK with tools, resources, and custom logic.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The unique name of the plugin."""
        pass

    @property
    def version(self) -> str:
        """The version of the plugin."""
        return "0.1.0"

    def on_configure(self, manifest: dict[str, Any], path: Path | None = None) -> None:
        """Called when plugin configuration is loaded."""
        self.manifest = manifest
        self.path = path
        self.config = manifest.get("config", {})

    async def on_activate(self, ctx: Any) -> None:
        """
        Called when the plugin is activated.
        Use this to initialize resources or connections.
        """
        pass

    def register_tools(self, registry: PluginRegistry) -> None:
        """
        Register MCP tools with the registry.
        Recommended naming: 'plugin_name.tool_name'.
        """
        pass

    async def on_context_update(self, context: Any) -> None:
        """Called when MCP context is updated."""
        pass

    async def on_deactivate(self) -> None:
        """Cleanup logic called on shutdown."""
        pass

    def on_error(self, error: Exception) -> None:
        """Handle plugin-specific errors."""
        pass


# Alias for backward compatibility
PluginBase = MCPPlugin
