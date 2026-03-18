"""
Anomaly Plugin for MCP SDK
==========================
Provides real-time anomaly detection and registry.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.anomaly.detector import (
    AnomalyDetector,
    AnomalyDetectorConfig,
    AnomalyRegistry,
)


class AnomalyPlugin(PluginBase):
    """
    Plugin for anomaly detection.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)
        self.detector = AnomalyDetector(agent_id=f"{protocol.name}-anomaly")

    @property
    def name(self) -> str:
        return "anomaly"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register anomaly tools."""

        @self.protocol.tool(
            "anomaly_check", description="Run a value through the anomaly detector."
        )
        async def check_anomaly(value: float, context: str = "default") -> dict[str, Any]:
            is_anomaly, score = self.detector.check(value, context)
            return {"is_anomaly": is_anomaly, "score": score}

    async def teardown(self) -> None:
        pass


__all__ = [
    "AnomalyPlugin",
    "AnomalyDetector",
    "AnomalyDetectorConfig",
    "AnomalyRegistry",
]
