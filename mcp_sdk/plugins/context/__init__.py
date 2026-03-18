"""
Context Plugin for MCP SDK
=========================
Provides token-budget-aware context management.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.context.manager import (
    ContextItem,
    TokenBudgetManager,
)


class ContextPlugin(PluginBase):
    """
    Plugin for context management.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)
        self.manager = TokenBudgetManager()

    @property
    def name(self) -> str:
        return "context"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register context tools."""

        @self.protocol.tool("context_add", description="Add an item to the agent's context window.")
        async def add_item(content: str, priority: float = 0.5) -> str:
            self.manager.add(ContextItem(content=content, priority=priority))
            return "Item added to context"

    async def teardown(self) -> None:
        pass


__all__ = [
    "ContextPlugin",
    "ContextManager",
    "ContextItem",
    "TokenBudgetManager",
]
