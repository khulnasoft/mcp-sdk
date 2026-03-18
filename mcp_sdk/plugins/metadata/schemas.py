"""
Standardized Context Object Schemas
===================================
Defines the "agent-grade" schemas for geospatial context objects.
These wrap raw GeoJSON with administrative metadata and semantic labels.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class SemanticMetadata(BaseModel):
    """Administrative and semantic metadata for context objects."""

    owner: str = "system"
    source_url: str | None = None
    license: str = "proprietary"
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class StandardizedFeature(BaseModel):
    """
    A GeoJSON-compatible feature with enhanced semantic metadata.
    Designed for agent comprehension.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "Feature"
    geometry: dict[str, Any]  # GeoJSON Geometry object
    properties: dict[str, Any]
    semantic: SemanticMetadata = Field(default_factory=SemanticMetadata)

    @classmethod
    def from_geojson(cls, geojson: dict[str, Any], **metadata) -> StandardizedFeature:
        """Convert standard GeoJSON to agent-grade context object."""
        return cls(
            id=geojson.get("id", str(uuid.uuid4())),
            geometry=geojson["geometry"],
            properties=geojson["properties"],
            semantic=SemanticMetadata(**metadata),
        )


class StandardizedFeatureCollection(BaseModel):
    """A collection of standardized features."""

    type: str = "FeatureCollection"
    features: list[StandardizedFeature]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_scaffold(self) -> str:
        """Condensed representation for the Scaffold working memory."""
        summary = f"Geospatial Context ({len(self.features)} features)\n"
        for i, feat in enumerate(self.features[:5]):
            name = feat.properties.get("name", f"Feature {i}")
            kind = feat.properties.get("kind", "unknown")
            summary += f"- {name} ({kind}): {feat.semantic.confidence:.1%} confidence\n"
        if len(self.features) > 5:
            summary += f"- ... ({len(self.features)-5} more features)"
        return summary
