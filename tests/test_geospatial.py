"""Tests for Large Geospatial Model and related components."""

import pytest

from mcp_sdk.plugins.geospatial.chunker import SpatialChunker
from mcp_sdk.plugins.geospatial.model import (
    GeoPoint,
    GeoRegion,
    H3Index,
    LargeGeospatialModel,
    TelemetryAggregator,
    TelemetryEvent,
    TelemetryStream,
)


class TestGeoPoint:
    def test_distance_same_point(self) -> None:
        p = GeoPoint(lat=48.8566, lon=2.3522)
        assert p.distance_m(p) == pytest.approx(0.0, abs=1e-3)

    def test_distance_paris_london(self) -> None:
        paris = GeoPoint(lat=48.8566, lon=2.3522)
        london = GeoPoint(lat=51.5074, lon=-0.1278)
        d = paris.distance_m(london)
        # ~340 km
        assert 330_000 < d < 350_000

    def test_to_tuple(self) -> None:
        p = GeoPoint(lat=10.0, lon=20.0)
        assert p.to_tuple() == (10.0, 20.0)

    def test_invalid_lat_raises(self) -> None:
        with pytest.raises(Exception):
            GeoPoint(lat=91.0, lon=0.0)


class TestGeoRegion:
    @pytest.fixture
    def paris_bbox(self):
        return GeoRegion(min_lat=48.81, max_lat=48.90, min_lon=2.28, max_lon=2.42)

    def test_contains_point_inside(self, paris_bbox) -> None:
        p = GeoPoint(lat=48.85, lon=2.35)
        assert paris_bbox.contains(p) is True

    def test_not_contains_outside(self, paris_bbox) -> None:
        p = GeoPoint(lat=51.5, lon=-0.1)  # London
        assert paris_bbox.contains(p) is False

    def test_centre(self, paris_bbox) -> None:
        c = paris_bbox.centre
        assert 48.8 < c.lat < 48.9
        assert 2.3 < c.lon < 2.4

    def test_area_positive(self, paris_bbox) -> None:
        assert paris_bbox.area_km2 > 0


class TestH3Index:
    @pytest.fixture
    def h3(self):
        return H3Index(resolution=8)

    def test_point_to_cell_returns_string(self, h3) -> None:
        p = GeoPoint(lat=48.8566, lon=2.3522)
        cell = h3.point_to_cell(p)
        assert isinstance(cell, str)
        assert len(cell) > 0

    def test_same_point_same_cell(self, h3) -> None:
        p = GeoPoint(lat=48.8566, lon=2.3522)
        assert h3.point_to_cell(p) == h3.point_to_cell(p)

    def test_different_points_may_differ(self, h3) -> None:
        p1 = GeoPoint(lat=0.0, lon=0.0)
        p2 = GeoPoint(lat=10.0, lon=10.0)
        # They should map to different cells at most resolutions
        # (not guaranteed for very coarse res, but res=8 should distinguish these)
        c1 = h3.point_to_cell(p1)
        c2 = h3.point_to_cell(p2)
        assert c1 != c2

    def test_polyfill_returns_cells(self, h3) -> None:
        region = GeoRegion(min_lat=48.85, max_lat=48.86, min_lon=2.35, max_lon=2.36)
        cells = h3.polyfill(region)
        assert isinstance(cells, list)
        assert len(cells) > 0

    def test_get_neighbors_includes_origin(self, h3) -> None:
        p = GeoPoint(lat=48.8566, lon=2.3522)
        cell = h3.point_to_cell(p)
        neighbors = h3.get_neighbors(cell, k=1)
        assert cell in neighbors


class TestLargeGeospatialModel:
    @pytest.fixture
    def lgm(self):
        return LargeGeospatialModel(resolution=8)

    @pytest.fixture
    def paris_region(self):
        return GeoRegion(min_lat=48.81, max_lat=48.90, min_lon=2.28, max_lon=2.42)

    def test_index_and_query_point(self, lgm) -> None:
        p = GeoPoint(lat=48.8566, lon=2.3522)
        lgm.index_point(p, {"name": "Eiffel Tower"})
        results = lgm.query_radius(p, radius_km=1.0)
        assert len(results) >= 1
        assert any(r.get("name") == "Eiffel Tower" for r in results)

    def test_query_region(self, lgm, paris_region) -> None:
        p = GeoPoint(lat=48.855, lon=2.352)
        lgm.index_point(p, {"type": "landmark"})
        results = lgm.query_region(paris_region)
        assert any(r.get("type") == "landmark" for r in results)

    def test_point_outside_region_not_returned(self, lgm, paris_region) -> None:
        london = GeoPoint(lat=51.5, lon=-0.1)
        lgm.index_point(london, {"city": "London"})
        results = lgm.query_region(paris_region)
        assert all(r.get("city") != "London" for r in results)

    def test_load_tile(self, lgm, paris_region) -> None:
        tile = lgm.load_tile(
            paris_region,
            data={
                "name": "Paris",
                "features": [
                    {"coordinates": [48.855, 2.352], "type": "poi"},
                ],
            },
        )
        assert tile.tile_id in lgm._tiles

    def test_stats(self, lgm) -> None:
        stats = lgm.stats
        assert "indexed_points" in stats
        assert "resolution" in stats


class TestTelemetryStream:
    @pytest.mark.asyncio
    async def test_from_list(self) -> None:
        events = [
            TelemetryEvent(location=GeoPoint(lat=48.85 + i * 0.01, lon=2.35), source="gps")
            for i in range(5)
        ]
        stream = TelemetryStream.from_list(events)
        received = []
        async for event in stream:
            received.append(event)
        assert len(received) == 5

    @pytest.mark.asyncio
    async def test_filter(self) -> None:
        events = [
            TelemetryEvent(location=GeoPoint(lat=1.0, lon=1.0), quality=0.8),
            TelemetryEvent(location=GeoPoint(lat=2.0, lon=2.0), quality=0.2),
        ]
        stream = TelemetryStream.from_list(events)
        stream._filter = lambda e: e.quality > 0.5
        received = []
        async for event in stream:
            received.append(event)
        assert len(received) == 1
        assert received[0].quality == 0.8


class TestTelemetryAggregator:
    @pytest.mark.asyncio
    async def test_ingest_and_dispatch(self) -> None:
        agg = TelemetryAggregator(resolution=6, batch_size=3)
        dispatched: list = []

        @agg.on_batch
        def handler(cell_id, events) -> None:
            dispatched.extend(events)

        events = [
            TelemetryEvent(location=GeoPoint(lat=48.855 + i * 0.001, lon=2.352), source="gps")
            for i in range(10)
        ]
        stream = TelemetryStream.from_list(events)
        count = await agg.ingest(stream)
        assert count == 10
        assert len(dispatched) > 0

    def test_summarise_cell(self) -> None:
        agg = TelemetryAggregator(resolution=8)
        events = [
            TelemetryEvent(location=GeoPoint(lat=48.85, lon=2.35)),
            TelemetryEvent(location=GeoPoint(lat=48.86, lon=2.36)),
        ]
        cell_id = "test_cell"
        agg._cells[cell_id] = events
        summary = agg.summarise_cell(cell_id)
        assert summary["count"] == 2
        assert "lat_range" in summary


class TestSpatialChunker:
    def test_chunk_features_basic(self) -> None:
        chunker = SpatialChunker(max_tokens_per_chunk=50)
        features = [{"id": i, "name": f"Feature number {i}", "type": "POI"} for i in range(20)]
        chunks = chunker.chunk_features(features, tile_id="t1")
        assert len(chunks) > 1
        # All features should be covered
        total_features = sum(len(c.features) for c in chunks)
        assert total_features >= len(features)

    def test_chunk_respects_token_budget(self) -> None:
        chunker = SpatialChunker(max_tokens_per_chunk=100)
        features = [{"data": "x" * 200, "id": i} for i in range(10)]
        chunks = chunker.chunk_features(features, tile_id="t1")
        for chunk in chunks:
            assert chunk.token_estimate <= 120  # Some tolerance for last chunk

    def test_chunk_index_and_total(self) -> None:
        chunker = SpatialChunker(max_tokens_per_chunk=50)
        features = [{"v": i} for i in range(20)]
        chunks = chunker.chunk_features(features, tile_id="t1")
        assert chunks[0].chunk_index == 0
        assert chunks[-1].is_last is True
        assert all(c.total_chunks == len(chunks) for c in chunks)

    def test_empty_features_returns_empty(self) -> None:
        chunker = SpatialChunker()
        assert chunker.chunk_features([], tile_id="t1") == []

    def test_to_text(self) -> None:
        chunker = SpatialChunker()
        chunks = chunker.chunk_features([{"name": "Park"}], tile_id="t1")
        text = chunks[0].to_text()
        assert "SpatialChunk" in text
        assert "t1" in text

    @pytest.mark.asyncio
    async def test_async_chunking(self) -> None:
        chunker = SpatialChunker(max_tokens_per_chunk=50)
        features = [{"id": i} for i in range(15)]
        chunks = []
        async for chunk in chunker.chunk_tile_async(features, tile_id="t1"):
            chunks.append(chunk)
        assert len(chunks) >= 1

    def test_chunk_cells(self) -> None:
        chunker = SpatialChunker(max_tokens_per_chunk=100)
        cell_map = {f"cell_{i}": [{"feat": j} for j in range(5)] for i in range(6)}
        chunks = chunker.chunk_cells(cell_map, tile_id="t1")
        assert len(chunks) >= 1
        assert all(c.total_chunks == len(chunks) for c in chunks)
