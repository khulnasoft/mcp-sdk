"""
Plugin Registry for MCP SDK
===========================
Maintains a central record of loaded plugins, tools, and resources.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from mcp_sdk.core.plugin import MCPPlugin


class PluginRegistry:
    """
    Tracks all extension points exposed by plugins.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, MCPPlugin] = {}
        self._tools: dict[str, Callable] = {}
        self._resources: dict[str, Any] = {}

    def register_plugin(self, plugin: MCPPlugin) -> None:
        """Register a plugin instance."""
        self._plugins[plugin.name] = plugin

    def unregister_plugin(self, name: str) -> None:
        """Unregister a plugin and its associated tools."""
        if name in self._plugins:
            del self._plugins[name]
            # Remove tools associated with this namespace
            self._tools = {k: v for k, v in self._tools.items() if not k.startswith(f"{name}.")}
            logger.info("Plugin unregistered", name=name)

    def register_tool(
        self, name: str, func: Callable, metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Register an MCP tool with optional metadata.
        'name' should ideally be namespaced, e.g. 'github.create_issue'.
        """
        self._tools[name] = {"func": func, "metadata": metadata or {}}
        logger.debug("Tool registered", name=name, tags=(metadata or {}).get("tags"))

    def register_resource(self, name: str, resource: Any) -> None:
        """Register an MCP resource."""
        self._resources[name] = resource

    def get_tool(self, name: str) -> Callable | None:
        """Retrieve a tool by name."""
        entry = self._tools.get(name)
        return entry["func"] if entry else None

    def get_tool_metadata(self, name: str) -> dict[str, Any] | None:
        """Retrieve metadata for a specific tool."""
        entry = self._tools.get(name)
        return entry["metadata"] if entry else None

    def discover_tools(self, query: str) -> list[tuple[str, float]]:
        """
        Retrieves tools that match the query semantically.
        Scores tools based on metadata, tags, and keywords.
        """
        results = []
        query_lower = query.lower()

        STOP_WORDS = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "is",
            "of",
            "i",
            "need",
        }
        query_words = {w for w in query_lower.split() if w not in STOP_WORDS and len(w) > 2}

        for tool_name, tool_entry in self._tools.items():
            score = 0.0
            tool_meta = tool_entry.get("metadata", {})

            # 1. Name overlap
            name_lower = tool_name.lower()
            if any(word in name_lower for word in query_words):
                score += 5.0  # Increased weight for keyword in name
            if name_lower in query_lower:
                score += 10.0  # High weight for exact tool name mention

            # 2. Tag match
            tags = tool_meta.get("tags", [])
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in query_lower or any(word in tag_lower for word in query_words):
                    score += 4.0

            # 3. Description overlap
            desc_lower = tool_meta.get("description", "").lower()
            if any(word in desc_lower for word in query_words):
                score += 2.0

            # 4. Keyword freq
            keywords = tool_meta.get("keywords", [])
            for kw in keywords:
                if kw and kw.lower() in query_lower:
                    score += 3.0

            if score > 0:
                logger.debug(
                    "Tool discovery score",
                    tool=tool_name,
                    score=score,
                    query_words=list(query_words),
                )
                results.append((tool_name, score))

        # Sort by score descending
        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_plugin(self, name: str) -> MCPPlugin | None:
        """Retrieve a plugin by name."""
        return self._plugins.get(name)

    def clear_plugins(self) -> None:
        """Clear all registered plugins and tools."""
        self._plugins.clear()
        self._tools.clear()


_GLOBAL_REGISTRY: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Return the global registry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = PluginRegistry()
    return _GLOBAL_REGISTRY
