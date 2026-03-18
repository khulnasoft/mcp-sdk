"""
Scaffold Working Memory
========================
Maintains an explicit, human-readable representation of the agent's world state
and current beliefs. This "Scaffold" is injected into the model's context
to ground its reasoning in verified facts rather than latent hallucinations.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class ScaffoldBelief(BaseModel):
    """A human-readable belief about a specific world entity or state."""

    entity: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    last_updated: float = Field(default_factory=time.time)
    source: str = "observation"


class Scaffold(BaseModel):
    """The complete 'Working Memory' scaffold for the agent."""

    context_id: str
    summary: str = "Initial state"
    beliefs: list[ScaffoldBelief] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Render the scaffold as markdown for LLM injection."""
        lines = [f"## World Scaffold ({self.context_id})", f"**Summary**: {self.summary}\n"]

        if self.beliefs:
            lines.append("### Current Beliefs")
            for b in self.beliefs:
                lines.append(f"- **{b.entity}**: {b.description} (Confidence: {b.confidence:.2f})")

        if self.anomalies:
            lines.append("\n### Detected Anomalies")
            for a in self.anomalies:
                lines.append(f"- ⚠️ {a}")

        return "\n".join(lines)


class ScaffoldManager:
    """Manages the creation and evolution of state scaffolds."""

    def __init__(self, context_id: str) -> None:
        self._scaffold = Scaffold(context_id=context_id)

    @property
    def scaffold(self) -> Scaffold:
        return self._scaffold

    def update_belief(
        self, entity: str, description: str, confidence: float, source: str = "observation"
    ) -> None:
        """Update or add a belief to the scaffold."""
        for b in self._scaffold.beliefs:
            if b.entity == entity:
                b.description = description
                b.confidence = confidence
                b.last_updated = time.time()
                b.source = source
                return

        self._scaffold.beliefs.append(
            ScaffoldBelief(
                entity=entity, description=description, confidence=confidence, source=source
            )
        )

    def record_anomaly(self, description: str) -> None:
        """Record a prediction error or physical inconsistency."""
        if description not in self._scaffold.anomalies:
            self._scaffold.anomalies.append(description)

    def set_summary(self, summary: str) -> None:
        """Set the high-level context summary."""
        self._scaffold.summary = summary

    def clear_anomalies(self) -> None:
        """Clear resolved anomalies."""
        self._scaffold.anomalies.clear()

    def get_prompt_context(self) -> str:
        """Returns the markdown representation for system prompting."""
        return self._scaffold.to_markdown()
