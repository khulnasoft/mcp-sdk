"""
Protocol-Based Learning (Protoconf)
====================================
Implements the 'Files over Weights' paradigm. Behavioral rules and
environmental protocols are loaded from explicit files that can be
updated by the agent in response to active inference surprise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Protocol(BaseModel):
    """A behavioral or environmental protocol."""

    id: str
    version: str = "1.0.0"
    description: str
    rules: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Protoconf:
    """Manager for loading and updating protocol files."""

    def __init__(self, protocol_dir: Path) -> None:
        self.protocol_dir = protocol_dir
        self.protocol_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Protocol] = {}

    def get_protocol(self, protocol_id: str) -> Protocol | None:
        """Load a protocol from disk or cache."""
        if protocol_id in self._cache:
            return self._cache[protocol_id]

        path = self.protocol_dir / f"{protocol_id}.yaml"
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                protocol = Protocol(**data)
                self._cache[protocol_id] = protocol
                return protocol
        except Exception:
            return None

    def save_protocol(self, protocol: Protocol) -> None:
        """Persist a protocol to disk (Active Learning)."""
        self._cache[protocol.id] = protocol
        path = self.protocol_dir / f"{protocol.id}.yaml"

        with open(path, "w") as f:
            yaml.safe_dump(protocol.model_dump(), f)

    def update_rule(self, protocol_id: str, rule_id: str, updates: dict[str, Any]) -> None:
        """Update a specific rule within a protocol."""
        protocol = self.get_protocol(protocol_id)
        if not protocol:
            return

        for rule in protocol.rules:
            if rule.get("id") == rule_id:
                rule.update(updates)
                break
        else:
            # Add as new rule if not found
            updates["id"] = rule_id
            protocol.rules.append(updates)

        self.save_protocol(protocol)
