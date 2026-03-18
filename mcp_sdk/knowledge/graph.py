"""
Knowledge Graph Memory
=======================
Graph-based long-term memory for agents. Stores entities, relationships,
and facts as a directed, typed property graph.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class KGEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    entity_type: str = "concept"
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    observation_count: int = 1

    def touch(self) -> None:
        self.last_seen = time.time()
        self.observation_count += 1

    @property
    def recency_score(self) -> float:
        age_hours = (time.time() - self.last_seen) / 3600
        return 0.95**age_hours


class KGRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    relation_type: str
    weight: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    observation_count: int = 1

    def touch(self) -> None:
        self.last_seen = time.time()
        self.observation_count += 1
        self.weight = min(self.weight + 0.1, 10.0)


class KGFact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str
    fact: str
    source: str = ""
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)


@dataclass
class TraversalPath:
    entities: list[KGEntity]
    relationships: list[KGRelationship]
    total_weight: float = 0.0
    depth: int = 0

    def __str__(self) -> str:
        parts: list[str] = []
        for i, entity in enumerate(self.entities):
            parts.append(entity.name)
            if i < len(self.relationships):
                parts.append(f"--[{self.relationships[i].relation_type}]-->")
        return " ".join(parts)


class KnowledgeGraph:
    """
    In-memory directed property graph for agent long-term memory.

    Example::

        kg = KnowledgeGraph(namespace="user-alice")
        alice = kg.add_entity("Alice", entity_type="person")
        acme = kg.add_entity("Acme Corp", entity_type="org")
        kg.add_relationship(alice.id, "works_for", acme.id)
        kg.add_fact(alice.id, "Alice is the lead engineer")
        context = kg.get_context_for(alice.id)
    """

    def __init__(self, namespace: str = "default") -> None:
        self.namespace = namespace
        self._entities: dict[str, KGEntity] = {}
        self._relationships: dict[str, KGRelationship] = {}
        self._facts: dict[str, KGFact] = {}
        self._out_edges: dict[str, dict[str, list[str]]] = {}
        self._in_edges: dict[str, list[str]] = {}
        self._name_index: dict[str, str] = {}

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        properties: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
        confidence: float = 1.0,
    ) -> KGEntity:
        existing = self.find_entity(name)
        if existing:
            existing.touch()
            if properties:
                existing.properties.update(properties)
            return existing
        entity = KGEntity(
            name=name,
            entity_type=entity_type,
            aliases=aliases or [],
            properties=properties or {},
            confidence=confidence,
        )
        self._entities[entity.id] = entity
        self._name_index[name.lower()] = entity.id
        for alias in entity.aliases:
            self._name_index[alias.lower()] = entity.id
        return entity

    def get_entity(self, entity_id: str) -> KGEntity | None:
        return self._entities.get(entity_id)

    def find_entity(self, name: str) -> KGEntity | None:
        entity_id = self._name_index.get(name.strip().lower())
        return self._entities.get(entity_id) if entity_id else None

    def find_entities(self, entity_type: str) -> list[KGEntity]:
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def add_relationship(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        weight: float = 1.0,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> KGRelationship:
        existing = self._find_relationship(source_id, relation_type, target_id)
        if existing:
            existing.touch()
            return existing
        rel = KGRelationship(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            confidence=confidence,
            properties=properties or {},
        )
        self._relationships[rel.id] = rel
        self._out_edges.setdefault(source_id, {}).setdefault(relation_type, []).append(rel.id)
        self._in_edges.setdefault(target_id, []).append(rel.id)
        return rel

    def _find_relationship(
        self, source_id: str, relation_type: str, target_id: str
    ) -> KGRelationship | None:
        for rel_id in self._out_edges.get(source_id, {}).get(relation_type, []):
            rel = self._relationships.get(rel_id)
            if rel and rel.target_id == target_id:
                return rel
        return None

    def get_neighbors(
        self, entity_id: str, relation_type: str | None = None, direction: str = "out"
    ) -> list[tuple[KGRelationship, KGEntity]]:
        results: list[tuple[KGRelationship, KGEntity]] = []
        if direction in ("out", "both"):
            for rtype, rel_ids in self._out_edges.get(entity_id, {}).items():
                if relation_type and rtype != relation_type:
                    continue
                for rid in rel_ids:
                    rel = self._relationships.get(rid)
                    if rel and rel.target_id in self._entities:
                        results.append((rel, self._entities[rel.target_id]))
        if direction in ("in", "both"):
            for rid in self._in_edges.get(entity_id, []):
                rel = self._relationships.get(rid)
                if rel and (not relation_type or rel.relation_type == relation_type):
                    if rel.source_id in self._entities:
                        results.append((rel, self._entities[rel.source_id]))
        return results

    def add_fact(
        self, entity_id: str, fact: str, source: str = "", confidence: float = 1.0
    ) -> KGFact:
        kg_fact = KGFact(entity_id=entity_id, fact=fact, source=source, confidence=confidence)
        self._facts[kg_fact.id] = kg_fact
        return kg_fact

    def get_facts(self, entity_id: str) -> list[KGFact]:
        return [f for f in self._facts.values() if f.entity_id == entity_id]

    def traverse(self, start_id: str, max_depth: int = 3) -> list[TraversalPath]:
        paths: list[TraversalPath] = []
        queue: list[tuple[list[str], list[str], float]] = [([start_id], [], 0.0)]
        visited_depth: dict[str, int] = {start_id: 0}

        while queue:
            entity_ids, rel_ids, total_weight = queue.pop(0)
            current_id = entity_ids[-1]
            depth = len(entity_ids) - 1
            if depth > 0:
                entities = [self._entities[eid] for eid in entity_ids if eid in self._entities]
                rels = [self._relationships[rid] for rid in rel_ids if rid in self._relationships]
                paths.append(
                    TraversalPath(
                        entities=entities,
                        relationships=rels,
                        total_weight=total_weight,
                        depth=depth,
                    )
                )
            if depth >= max_depth:
                continue
            for rel, neighbor in self.get_neighbors(current_id):
                if visited_depth.get(neighbor.id, 999) <= depth + 1:
                    continue
                visited_depth[neighbor.id] = depth + 1
                queue.append(
                    (entity_ids + [neighbor.id], rel_ids + [rel.id], total_weight + rel.weight)
                )
        return paths

    def shortest_path(self, source_id: str, target_id: str) -> TraversalPath | None:
        if source_id == target_id:
            e = self._entities.get(source_id)
            return TraversalPath(entities=[e], relationships=[]) if e else None
        visited: set[str] = {source_id}
        queue: list[tuple[list[str], list[str]]] = [([source_id], [])]
        while queue:
            entity_ids, rel_ids = queue.pop(0)
            for rel, neighbor in self.get_neighbors(entity_ids[-1]):
                if neighbor.id in visited:
                    continue
                visited.add(neighbor.id)
                new_eids = entity_ids + [neighbor.id]
                new_rids = rel_ids + [rel.id]
                if neighbor.id == target_id:
                    entities = [self._entities[eid] for eid in new_eids if eid in self._entities]
                    rels = [
                        self._relationships[rid] for rid in new_rids if rid in self._relationships
                    ]
                    return TraversalPath(
                        entities=entities,
                        relationships=rels,
                        total_weight=sum(r.weight for r in rels),
                        depth=len(entities) - 1,
                    )
                queue.append((new_eids, new_rids))
        return None

    def get_context_for(self, entity_id: str, depth: int = 2) -> str:
        entity = self._entities.get(entity_id)
        if not entity:
            return ""
        lines = [f"Known information about {entity.name} ({entity.entity_type}):"]
        for fact in self.get_facts(entity_id):
            lines.append(f"  • {fact.fact}")
        for k, v in entity.properties.items():
            lines.append(f"  • {k}: {v}")
        seen: set[str] = set()
        for path in self.traverse(entity_id, max_depth=depth):
            desc = str(path)
            if desc not in seen:
                lines.append(f"  → {desc}")
                seen.add(desc)
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "namespace": self.namespace,
                "entities": [e.model_dump() for e in self._entities.values()],
                "relationships": [r.model_dump() for r in self._relationships.values()],
                "facts": [f.model_dump() for f in self._facts.values()],
            },
            default=str,
            indent=2,
        )

    def to_dot(self) -> str:
        lines = [f'digraph "{self.namespace}" {{', "  rankdir=LR;"]
        for e in self._entities.values():
            lines.append(f'  "{e.id}" [label="{e.name}\\n({e.entity_type})"];')
        for r in self._relationships.values():
            lines.append(f'  "{r.source_id}" -> "{r.target_id}" [label="{r.relation_type}"];')
        lines.append("}")
        return "\n".join(lines)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "entities": len(self._entities),
            "relationships": len(self._relationships),
            "facts": len(self._facts),
        }

    def __repr__(self) -> str:
        s = self.stats
        return f"KnowledgeGraph(ns={self.namespace!r}, entities={s['entities']}, relationships={s['relationships']})"
