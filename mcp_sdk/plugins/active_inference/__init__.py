"""
Active Inference Plugin for MCP SDK
==================================
Provides predictive reasoning, belief updates, and scaffold integration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.plugins.active_inference.active_inference import (
    ActiveInferenceEngine,
    BeliefState,
    GenerativeModel,
    InferenceResult,
)


class ActiveInferencePlugin(MCPPlugin):
    """
    Plugin for Active Inference.
    Registers predictive reasoning tools.
    """

    def __init__(self, protocol: Any) -> None:
        self._protocol = protocol
        # Default engine; agents can create their own instances
        self.default_engine = ActiveInferenceEngine(state_dim=2, action_space=["none"])

    @property
    def name(self) -> str:
        return "active_inference"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register inference tools."""

        @self.protocol.tool(
            "inference_predict",
            description="Perform active inference prediction based on an observation.",
        )
        async def predict(observation: list[float]) -> dict[str, Any]:
            result = await self.default_engine.infer(observation)
            return {
                "state": result.state.tolist(),
                "action": result.action,
                "surprise": float(result.surprise),
            }

    async def teardown(self) -> None:
        pass


__all__ = [
    "ActiveInferencePlugin",
    "ActiveInferenceEngine",
    "BeliefState",
    "GenerativeModel",
    "InferenceResult",
]
