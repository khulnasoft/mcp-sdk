"""
Geospatial Plugin for MCP SDK
=============================
Provides spatial intelligence, LGM indexing, and telemetry tools.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.geospatial.chunker import SpatialChunk, SpatialChunker
from mcp_sdk.plugins.geospatial.model import (
    GeoPoint,
    GeoRegion,
    GeoTile,
    H3Index,
    LargeGeospatialModel,
    TelemetryAggregator,
    TelemetryEvent,
    TelemetryStream,
)


class GeospatialPlugin(PluginBase):
    """
    Plugin for geospatial intelligence.
    Registers spatial indexing and query tools.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)
        self.lgm = LargeGeospatialModel()

    @property
    def name(self) -> str:
        return "geospatial"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register geospatial tools."""

        @self.protocol.tool(
            "geo_query_region", description="Query indexed geospatial points within a bounding box."
        )
        async def query_region(
            min_lat: float, max_lat: float, min_lon: float, max_lon: float
        ) -> list[dict[str, Any]]:
            region = GeoRegion(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon)
            return self.lgm.query_region(region)

        @self.protocol.tool(
            "geo_index_point", description="Index a geospatial point with metadata."
        )
        async def index_point(
            lat: float, lon: float, properties: dict[str, Any] | None = None
        ) -> str:
            point = GeoPoint(lat=lat, lon=lon)
            return self.lgm.index_point(point, properties)

        @self.protocol.resource("geo://stats")
        async def get_stats(uri: str) -> dict[str, Any]:
            return self.lgm.stats

    async def teardown(self) -> None:
        """Cleanup logic."""
        pass


__all__ = [
    "GeospatialPlugin",
    "GeoPoint",
    "GeoRegion",
    "GeoTile",
    "H3Index",
    "LargeGeospatialModel",
    "TelemetryEvent",
    "TelemetryStream",
    "TelemetryAggregator",
    "SpatialChunker",
    "SpatialChunk",
]
