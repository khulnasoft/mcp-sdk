"""
Spatial Chunker
================
Breaks large geospatial payloads into token-budget-safe chunks,
enabling the Observation-Action Loop to process massive map data
without overloading the context window.

Usage::

    from mcp_sdk.plugins.context.manager import TokenBudgetManager, ContextItem
    from mcp_sdk.plugins.geospatial.chunker import SpatialChunker, SpatialChunk

    chunker = SpatialChunker(max_tokens_per_chunk=1024)
    async for chunk in chunker.chunk_tile(tile):
        ctx_mgr.add(ContextItem(content=chunk.to_text(), priority=0.6))
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class SpatialChunk(BaseModel):
    """A bounded, token-safe slice of geospatial data."""

    chunk_id: str
    tile_id: str
    chunk_index: int
    total_chunks: int
    cell_ids: list[str] = Field(default_factory=list)
    features: list[dict[str, Any]] = Field(default_factory=list)
    token_estimate: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_text(self) -> str:
        """Compact text representation for context injection."""
        lines = [
            f"[SpatialChunk {self.chunk_index+1}/{self.total_chunks} | tile={self.tile_id}]",
            f"cells={len(self.cell_ids)} features={len(self.features)}",
        ]
        for feat in self.features[:10]:  # Cap inline features
            lines.append(f"  - {json.dumps(feat, default=str)[:120]}")
        if len(self.features) > 10:
            lines.append(f"  ... and {len(self.features) - 10} more features")
        return "\n".join(lines)

    @property
    def is_last(self) -> bool:
        return self.chunk_index == self.total_chunks - 1


def _estimate_tokens(text: str) -> int:
    """4 chars ≈ 1 token (no tiktoken dependency required)."""
    return max(1, len(text) // 4)


class SpatialChunker:
    """
    Splits GeoTile data into token-budget-safe SpatialChunks.

    Chunking strategy:
    1. Convert tile data features to text
    2. Measure token cost per feature group
    3. Yield chunks that stay under max_tokens_per_chunk

    Example::

        chunker = SpatialChunker(max_tokens_per_chunk=1024)
        chunks = list(chunker.chunk_features(features, tile_id="t1"))
        print(f"{len(chunks)} chunks from {len(features)} features")
    """

    def __init__(
        self,
        max_tokens_per_chunk: int = 1024,
        overlap_features: int = 2,
    ) -> None:
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.overlap_features = overlap_features  # Features repeated in adjacent chunks

    def chunk_features(
        self,
        features: list[dict[str, Any]],
        tile_id: str = "unknown",
        cell_ids: list[str] | None = None,
    ) -> list[SpatialChunk]:
        """Split a flat list of features into token-safe chunks."""
        if not features:
            return []

        chunks: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_tokens = 0

        for feat in features:
            feat_text = json.dumps(feat, default=str)
            feat_tokens = _estimate_tokens(feat_text)

            if current_tokens + feat_tokens > self.max_tokens_per_chunk and current:
                chunks.append(current)
                # Overlap: carry last N features to next chunk
                current = current[-self.overlap_features :] if self.overlap_features else []
                current_tokens = sum(_estimate_tokens(json.dumps(f, default=str)) for f in current)

            current.append(feat)
            current_tokens += feat_tokens

        if current:
            chunks.append(current)

        total = len(chunks)
        result: list[SpatialChunk] = []
        for i, chunk_feats in enumerate(chunks):
            chunk_text = "\n".join(json.dumps(f, default=str) for f in chunk_feats)
            result.append(
                SpatialChunk(
                    chunk_id=f"{tile_id}_{i}",
                    tile_id=tile_id,
                    chunk_index=i,
                    total_chunks=total,
                    cell_ids=cell_ids or [],
                    features=chunk_feats,
                    token_estimate=_estimate_tokens(chunk_text),
                    metadata={"overlap": self.overlap_features},
                )
            )

        logger.debug(
            "Spatial chunking complete", tile=tile_id, input_features=len(features), chunks=total
        )
        return result

    async def chunk_tile_async(
        self,
        features: list[dict[str, Any]],
        tile_id: str = "unknown",
        cell_ids: list[str] | None = None,
    ) -> AsyncGenerator[SpatialChunk, None]:
        """Async generator yielding chunks one by one (backpressure-friendly)."""
        for chunk in self.chunk_features(features, tile_id, cell_ids):
            yield chunk

    def chunk_cells(
        self,
        cell_map: dict[str, list[dict[str, Any]]],
        tile_id: str = "unknown",
    ) -> list[SpatialChunk]:
        """Chunk a cell_id → features mapping, keeping cells grouped."""
        chunks: list[SpatialChunk] = []
        current_cells: list[str] = []
        current_features: list[dict[str, Any]] = []
        current_tokens = 0

        for cell_id, features in cell_map.items():
            cell_text = json.dumps(features, default=str)
            cell_tokens = _estimate_tokens(cell_text)

            if current_tokens + cell_tokens > self.max_tokens_per_chunk and current_cells:
                chunks.append(self._make_chunk(chunks, tile_id, current_cells, current_features))
                current_cells, current_features, current_tokens = [], [], 0

            current_cells.append(cell_id)
            current_features.extend(features)
            current_tokens += cell_tokens

        if current_cells:
            chunks.append(self._make_chunk(chunks, tile_id, current_cells, current_features))

        # Patch total_chunks
        total = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total
        return chunks

    @staticmethod
    def _make_chunk(
        existing: list[SpatialChunk],
        tile_id: str,
        cells: list[str],
        features: list[dict[str, Any]],
    ) -> SpatialChunk:
        idx = len(existing)
        feat_text = json.dumps(features, default=str)
        return SpatialChunk(
            chunk_id=f"{tile_id}_{idx}",
            tile_id=tile_id,
            chunk_index=idx,
            total_chunks=0,  # Patched after all chunks built
            cell_ids=cells,
            features=features,
            token_estimate=_estimate_tokens(feat_text),
        )
