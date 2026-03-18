"""
Loop Plugin for MCP SDK
======================
Provides the Observation-Action Loop engine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.loop.engine import (
    LoopConfig,
    LoopState,
    ObservationActionLoop,
)


class LoopPlugin(PluginBase):
    """
    Plugin for observation-action loops.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)

    @property
    def name(self) -> str:
        return "loop"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register loop tools."""
        pass

    async def teardown(self) -> None:
        pass


__all__ = [
    "LoopPlugin",
    "ObservationActionLoop",
    "LoopConfig",
    "LoopState",
]
