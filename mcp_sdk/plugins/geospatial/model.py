"""
Large Geospatial Model
========================
Handles massive spatial payloads and live map SDK telemetry without
overloading the model's context window.

Components:
- GeoPoint / GeoRegion / GeoTile — Geometry primitives (no GDAL needed)
- H3Index — Pure-Python H3 hexagonal grid (wraps h3 library if available)
- LargeGeospatialModel — Spatial index for fast region queries + tile materialisation
- TelemetryStream / TelemetryEvent — Async live telemetry ingestion
- TelemetryAggregator — Batches events into H3 cells, debounces, notifies handlers
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Geometry primitives
# ─────────────────────────────────────────────────────────────────────────────


class GeoPoint(BaseModel):
    """A WGS-84 geographic point."""

    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    alt: float = 0.0  # metres MSL

    def distance_m(self, other: GeoPoint) -> float:
        """Haversine distance in metres."""
        R = 6_371_000.0
        φ1, φ2 = math.radians(self.lat), math.radians(other.lat)
        Δφ = math.radians(other.lat - self.lat)
        Δλ = math.radians(other.lon - self.lon)
        a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def to_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lon)


class GeoRegion(BaseModel):
    """Axis-aligned bounding box."""

    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, point: GeoPoint) -> bool:
        return (
            self.min_lat <= point.lat <= self.max_lat and self.min_lon <= point.lon <= self.max_lon
        )

    @property
    def centre(self) -> GeoPoint:
        return GeoPoint(
            lat=(self.min_lat + self.max_lat) / 2, lon=(self.min_lon + self.max_lon) / 2
        )

    @property
    def area_km2(self) -> float:
        lat_km = (self.max_lat - self.min_lat) * 111.0
        lon_km = (self.max_lon - self.min_lon) * 111.0 * math.cos(math.radians(self.centre.lat))
        return lat_km * lon_km


class GeoTile(BaseModel):
    """A bounded geographic tile with vector payload data."""

    tile_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    region: GeoRegion
    resolution: int = 9  # H3 resolution (0=coarse, 15=fine)
    data: dict[str, Any] = Field(default_factory=dict)
    cell_ids: list[str] = Field(default_factory=list)
    loaded_at: float = Field(default_factory=time.time)
    token_estimate: int = 0

    def model_post_init(self, __context: Any) -> None:
        if self.token_estimate == 0:
            self.token_estimate = max(1, len(str(self.data)) // 4)


# ─────────────────────────────────────────────────────────────────────────────
# H3 Index — pure-Python fallback + h3 library integration
# ─────────────────────────────────────────────────────────────────────────────


class H3Index:
    """
    Hexagonal hierarchical spatial index.

    Uses the `h3` library if installed, otherwise falls back to
    a grid-cell approximation using lat/lon bucketing.

    H3 resolutions: 0 (≈1107km avg edge) → 15 (≈0.5m avg edge)
    Typical for city-level: resolution 8-10.
    """

    def __init__(self, resolution: int = 9) -> None:
        self.resolution = resolution
        self._h3_available = self._check_h3()

    @staticmethod
    def _check_h3() -> bool:
        try:
            import h3  # type: ignore[import]

            return True
        except ImportError:
            return False

    def point_to_cell(self, point: GeoPoint) -> str:
        """Convert a lat/lon point to an H3 cell ID string."""
        if self._h3_available:
            import h3

            return h3.latlng_to_cell(point.lat, point.lon, self.resolution)
        # Fallback: quantise to grid cell
        grid_size = 0.1 / (2 ** (self.resolution - 5))  # Approximate
        lat_q = round(point.lat / grid_size) * grid_size
        lon_q = round(point.lon / grid_size) * grid_size
        cell_key = f"grid_{lat_q:.6f}_{lon_q:.6f}_r{self.resolution}"
        return hashlib.sha1(cell_key.encode()).hexdigest()[:15]

    def cell_to_latlng(self, cell_id: str) -> tuple[float, float]:
        """Get the centre lat/lon of an H3 cell."""
        if self._h3_available:
            import h3

            return h3.cell_to_latlng(cell_id)
        return (0.0, 0.0)  # Fallback: origin

    def get_neighbors(self, cell_id: str, k: int = 1) -> list[str]:
        """Return all cells within k rings of cell_id."""
        if self._h3_available:
            import h3

            return list(h3.grid_disk(cell_id, k))
        return [cell_id]  # Fallback: only self

    def polyfill(self, region: GeoRegion) -> list[str]:
        """Return all H3 cells covering a GeoRegion."""
        if self._h3_available:
            import h3

            polygon = h3.LatLngPoly(
                [
                    (region.min_lat, region.min_lon),
                    (region.min_lat, region.max_lon),
                    (region.max_lat, region.max_lon),
                    (region.max_lat, region.min_lon),
                    (region.min_lat, region.min_lon),
                ]
            )
            return list(h3.polygon_to_cells(polygon, self.resolution))
        # Fallback: sample grid
        cells: list[str] = []
        step = 0.1
        lat = region.min_lat
        while lat <= region.max_lat:
            lon = region.min_lon
            while lon <= region.max_lon:
                cells.append(self.point_to_cell(GeoPoint(lat=lat, lon=lon)))
                lon += step
            lat += step
        return list(set(cells))

    def compact(self, cell_ids: list[str]) -> list[str]:
        """Compact a set of cells to fewer parent cells (reduces token count)."""
        if self._h3_available:
            import h3

            return list(h3.compact_cells(set(cell_ids)))
        return cell_ids


# ─────────────────────────────────────────────────────────────────────────────
# Large Geospatial Model
# ─────────────────────────────────────────────────────────────────────────────


class LargeGeospatialModel:
    """
    Spatial index and tile manager for large geospatial datasets.

    Supports fast region queries and incremental tile loading without
    materialising the entire map into memory (or tokens).

    Example::

        lgm = LargeGeospatialModel(resolution=9)
        tile = lgm.load_tile(region, data={"roads": [...], "pois": [...]})

        # Query
        nearby = lgm.query_region(GeoRegion(min_lat=48.8, max_lat=48.9,
                                            min_lon=2.3, max_lon=2.4))
        for point_data in nearby:
            print(point_data)
    """

    def __init__(self, resolution: int = 9) -> None:
        self.resolution = resolution
        self.h3 = H3Index(resolution=resolution)
        self._index: dict[str, list[dict[str, Any]]] = {}  # cell_id → [feature_dicts]
        self._tiles: dict[str, GeoTile] = {}
        self._point_count = 0

    def index_point(self, point: GeoPoint, properties: dict[str, Any] | None = None) -> str:
        """Index a point with properties. Returns the H3 cell ID."""
        cell_id = self.h3.point_to_cell(point)
        record = {"lat": point.lat, "lon": point.lon, **(properties or {})}
        self._index.setdefault(cell_id, []).append(record)
        self._point_count += 1
        return cell_id

    def query_radius(self, centre: GeoPoint, radius_km: float) -> list[dict[str, Any]]:
        """Query all indexed points within radius_km of centre."""
        cell = self.h3.point_to_cell(centre)
        k = max(1, int(radius_km / 0.5))  # Approximate ring size
        neighbor_cells = self.h3.get_neighbors(cell, k)
        results: list[dict[str, Any]] = []
        for c in neighbor_cells:
            for record in self._index.get(c, []):
                p = GeoPoint(lat=record["lat"], lon=record["lon"])
                if p.distance_m(centre) <= radius_km * 1000:
                    results.append(record)
        return results

    def query_region(self, region: GeoRegion) -> list[dict[str, Any]]:
        """Query all indexed points within a bounding box."""
        cells = self.h3.polyfill(region)
        results: list[dict[str, Any]] = []
        for cell in cells:
            for record in self._index.get(cell, []):
                p = GeoPoint(lat=record["lat"], lon=record["lon"])
                if region.contains(p):
                    results.append(record)
        return results

    def load_tile(self, region: GeoRegion, data: dict[str, Any]) -> GeoTile:
        """Load a data tile for a region and index its features."""
        cells = self.h3.polyfill(region)
        tile = GeoTile(region=region, resolution=self.resolution, data=data, cell_ids=cells)
        self._tiles[tile.tile_id] = tile

        # Index any point features in the data
        features = data.get("features", [])
        for feat in features:
            coords = feat.get("coordinates") or feat.get("location")
            if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                p = GeoPoint(lat=float(coords[0]), lon=float(coords[1]))
                self.index_point(p, feat)

        logger.debug("Tile loaded", tile_id=tile.tile_id, cells=len(cells), features=len(features))
        return tile

    def get_tile(self, tile_id: str) -> GeoTile | None:
        return self._tiles.get(tile_id)

    def compact_region(self, region: GeoRegion) -> list[str]:
        """Return a compacted (fewer cells) representation of a region."""
        cells = self.h3.polyfill(region)
        return self.h3.compact(cells)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "indexed_points": self._point_count,
            "cells_used": len(self._index),
            "tiles_loaded": len(self._tiles),
            "resolution": self.resolution,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Live Telemetry
# ─────────────────────────────────────────────────────────────────────────────


class TelemetryEvent(BaseModel):
    """A single geospatial telemetry observation."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    source: str = ""
    location: GeoPoint
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    quality: float = Field(default=1.0, ge=0.0, le=1.0)


class TelemetryStream:
    """
    Async-iterable telemetry source. Wraps any async generator of raw events.

    Example::

        async def gps_source():
            while True:
                event = await read_gps_sensor()
                yield event
                await asyncio.sleep(0.1)

        stream = TelemetryStream(source=gps_source())
        async for event in stream:
            lgm.index_point(event.location, event.payload)
    """

    def __init__(
        self,
        source: AsyncGenerator[TelemetryEvent, None] | None = None,
        filter_fn: Callable[[TelemetryEvent], bool] | None = None,
    ) -> None:
        self._source = source
        self._filter = filter_fn
        self._emitted = 0

    def __aiter__(self) -> TelemetryStream:
        return self

    async def __anext__(self) -> TelemetryEvent:
        if self._source is None:
            raise StopAsyncIteration
        async for event in self._source:
            if self._filter is None or self._filter(event):
                self._emitted += 1
                return event
        raise StopAsyncIteration

    @classmethod
    def from_list(cls, events: list[TelemetryEvent]) -> TelemetryStream:
        """Create a stream from a static list (useful for testing)."""

        async def _gen() -> AsyncGenerator[TelemetryEvent, None]:
            for e in events:
                yield e

        return cls(source=_gen())

    @property
    def emitted_count(self) -> int:
        return self._emitted


class TelemetryAggregator:
    """
    Batches raw telemetry events into H3 cells and calls
    registered handlers when a batch is ready.

    Handles the token-bloat problem by NOT passing raw event lists
    to the agent; instead it summarises them into cell-level statistics.

    Example::

        agg = TelemetryAggregator(resolution=8, batch_size=50)

        @agg.on_batch
        async def handle(cell_id, events):
            summary = agg.summarise_cell(cell_id)
            context_mgr.add(ContextItem(content=str(summary), priority=0.6))

        await agg.ingest(stream)
    """

    def __init__(
        self,
        resolution: int = 8,
        batch_size: int = 50,
        debounce_seconds: float = 1.0,
    ) -> None:
        self.resolution = resolution
        self.batch_size = batch_size
        self.debounce_seconds = debounce_seconds
        self.h3 = H3Index(resolution=resolution)
        self._cells: dict[str, list[TelemetryEvent]] = {}
        self._handlers: list[Callable[[str, list[TelemetryEvent]], Any]] = []
        self._total_ingested = 0

    def on_batch(self, fn: Callable[[str, list[TelemetryEvent]], Any]) -> Callable:
        """Decorator to register a batch handler."""
        self._handlers.append(fn)
        return fn

    async def ingest(self, stream: TelemetryStream, max_events: int = 0) -> int:
        """Ingest from a TelemetryStream, dispatching batches as they fill."""
        count = 0
        async for event in stream:
            cell_id = self.h3.point_to_cell(event.location)
            self._cells.setdefault(cell_id, []).append(event)
            self._total_ingested += 1
            count += 1

            if len(self._cells[cell_id]) >= self.batch_size:
                await self._dispatch(cell_id)

            if max_events and count >= max_events:
                break

        # Flush remaining cells
        for cell_id in list(self._cells.keys()):
            if self._cells[cell_id]:
                await self._dispatch(cell_id)

        return count

    async def _dispatch(self, cell_id: str) -> None:
        events = self._cells.pop(cell_id, [])
        for handler in self._handlers:
            try:
                coro = handler(cell_id, events)
                if asyncio.iscoroutine(coro):
                    await coro
            except Exception as exc:
                logger.error("Telemetry handler failed", cell=cell_id, error=str(exc))

    def summarise_cell(self, cell_id: str) -> dict[str, Any]:
        """Return a compact statistical summary of events in a cell (token-friendly)."""
        events = self._cells.get(cell_id, [])
        if not events:
            return {"cell": cell_id, "count": 0}
        lats = [e.location.lat for e in events]
        lons = [e.location.lon for e in events]
        return {
            "cell_id": cell_id,
            "resolution": self.resolution,
            "count": len(events),
            "lat_range": [min(lats), max(lats)],
            "lon_range": [min(lons), max(lons)],
            "time_range": [min(e.timestamp for e in events), max(e.timestamp for e in events)],
            "avg_quality": sum(e.quality for e in events) / len(events),
        }

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_ingested": self._total_ingested,
            "active_cells": len(self._cells),
            "pending_events": sum(len(v) for v in self._cells.values()),
        }
