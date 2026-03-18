"""
Thinking Plugin for MCP SDK
==========================
Provides sequential thinking and reasoning capabilities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.thinking.engine import (
    SequentialThinkingEngine,
    ThinkingConfig,
)


class ThinkingPlugin(PluginBase):
    """
    Plugin for sequential thinking.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)
        self.engine = SequentialThinkingEngine()

    @property
    def name(self) -> str:
        return "thinking"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register thinking tools."""

        @self.protocol.tool(
            "thinking_step", description="Perform a single step of sequential thinking."
        )
        async def think(thought: str) -> str:
            return await self.engine.step(thought)

    async def teardown(self) -> None:
        pass


__all__ = [
    "ThinkingPlugin",
    "SequentialThinkingEngine",
    "ThinkingConfig",
]
