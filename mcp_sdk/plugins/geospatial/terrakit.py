"""
TerraKit Integration
====================
Abstracts coordinate reference system (CRS) complexity and multi-source ingestion.
Part of the TerraStackAI ecosystem.

Features:
- CRS Transformation (EPSG:4326 <-> EPSG:3857 mock)
- Multi-source alignment (Normalizing diverse formats)
- Automated geometry validation
"""

from __future__ import annotations

import math
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CRSTransformer:
    """
    Mock Transformer for Coordinate Reference Systems.
    In production, this would wrap `pyproj`.
    """

    @staticmethod
    def wgs84_to_web_mercator(lat: float, lon: float) -> tuple[float, float]:
        """Convert WGS-84 (EPSG:4326) to Web Mercator (EPSG:3857)."""
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
        y = y * 20037508.34 / 180
        return x, y

    @staticmethod
    def web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
        """Convert Web Mercator (EPSG:3857) to WGS-84 (EPSG:4326)."""
        lon = x * 180 / 20037508.34
        lat = math.atan(math.exp(y * math.pi / 20037508.34)) * 360 / math.pi - 90
        return lat, lon


class TerraKitIngestor:
    """
    Ingests and aligns data from multiple sources.
    Normalizes diversity in schemas.
    """

    def __init__(self) -> None:
        self.transformer = CRSTransformer()

    def align_feature(
        self, raw_data: dict[str, Any], schema_map: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        Aligns a raw record to a standardized feature schema.
        Maps fields like 'latitude' -> 'lat', 'longitude' -> 'lon' if specified in schema_map.
        """
        aligned = {}
        schema_map = schema_map or {
            "latitude": "lat",
            "lat": "lat",
            "LAT": "lat",
            "longitude": "lon",
            "lon": "lon",
            "LONG": "lon",
            "lng": "lon",
        }

        # 1. Coordinate normalization
        lat, lon = None, None
        for k_raw, k_std in schema_map.items():
            if k_raw in raw_data:
                if k_std == "lat":
                    lat = float(raw_data[k_raw])
                if k_std == "lon":
                    lon = float(raw_data[k_raw])

        if lat is not None and lon is not None:
            aligned["location"] = {"lat": lat, "lon": lon}
            aligned["mercator"] = self.transformer.wgs84_to_web_mercator(lat, lon)

        # 2. Attribute normalization
        aligned["properties"] = {k: v for k, v in raw_data.items() if k not in schema_map}

        logger.debug("Feature aligned", input_keys=list(raw_data.keys()))
        return aligned

    def validate_geometry(self, geometry: dict[str, Any]) -> bool:
        """Basic GeoJSON geometry validation."""
        if "type" not in geometry or "coordinates" not in geometry:
            return False

        g_type = geometry["type"]
        coords = geometry["coordinates"]

        if g_type == "Point":
            return isinstance(coords, (list, tuple)) and len(coords) >= 2
        elif g_type in ("LineString", "MultiPoint") or g_type in ("Polygon", "MultiLineString"):
            return isinstance(coords, (list, tuple)) and len(coords) > 0

        return False


class TerraKitPlugin:
    """Agent tool for TerraKit operations."""

    def __init__(self) -> None:
        self.ingestor = TerraKitIngestor()

    def transform_coordinates(
        self, lat: float, lon: float, to_epsg: int = 3857
    ) -> dict[str, float]:
        """Convert lat/lon to other CRS."""
        if to_epsg == 3857:
            x, y = self.ingestor.transformer.wgs84_to_web_mercator(lat, lon)
            return {"x": x, "y": y, "epsg": 3857}
        return {"lat": lat, "lon": lon, "epsg": 4326}

    def align_dataset(
        self, data: list[dict[str, Any]], schema_map: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Batch align a raw dataset."""
        return [self.ingestor.align_feature(row, schema_map) for row in data]
