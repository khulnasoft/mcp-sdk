from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_sdk.core.plugin import MCPPlugin

if TYPE_CHECKING:
    from mcp_sdk.core.registry import PluginRegistry


class Plugin(MCPPlugin):
    """
    Knowledge Plugin for self-discovery and context management.
    """

    @property
    def name(self) -> str:
        return "knowledge"

    def register_tools(self, registry: PluginRegistry) -> None:
        """Expose knowledge tools."""
        from mcp_sdk.plugins.knowledge.tools.context import summarize_context
        from mcp_sdk.plugins.knowledge.tools.discovery import list_capabilities, recommend_tools

        # Use the registry itself for discovery tools
        registry.register_tool(
            f"{self.name}.recommend_tools",
            recommend_tools(registry),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "recommend_tools"),
        )
        registry.register_tool(
            f"{self.name}.list_capabilities",
            list_capabilities(registry),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "list_capabilities"),
        )
        registry.register_tool(
            f"{self.name}.summarize_context",
            summarize_context(),
            metadata=next(t for t in self.manifest["tools"] if t["name"] == "summarize_context"),
        )
