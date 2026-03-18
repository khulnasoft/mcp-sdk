"""
Taxonomy System
================
Hierarchical classification framework for agents, capabilities, intents,
and domain concepts. Supports:

- Multi-level hierarchical taxonomies (tree + DAG)
- Tag-based classification with inheritance
- Intent classification and routing
- Agent capability taxonomies for discovery
- Domain-specific ontology import (JSON/YAML)
- Fuzzy / partial matching
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class TaxonomyNode(BaseModel):
    """A single node in a taxonomy tree."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str = ""  # URL-safe identifier
    description: str = ""
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    synonyms: list[str] = Field(default_factory=list)
    weight: float = 1.0  # Relevance weight for scoring

    def model_post_init(self, __context: Any) -> None:
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "_").replace("-", "_")

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def matches(self, query: str, fuzzy: bool = False) -> bool:
        normalized = query.strip().lower()
        exact = (
            normalized == self.name.lower()
            or normalized == self.slug
            or normalized in [s.lower() for s in self.synonyms]
        )
        if exact:
            return True
        if fuzzy:
            return (
                normalized in self.name.lower()
                or self.name.lower() in normalized
                or any(normalized in s.lower() for s in self.synonyms)
            )
        return False


class ClassificationResult(BaseModel):
    """Result of classifying text against a taxonomy."""

    node: TaxonomyNode
    confidence: float = Field(ge=0.0, le=1.0)
    path: list[str] = Field(default_factory=list)  # Ancestor slugs
    depth: int = 0


class Taxonomy:
    """
    Hierarchical taxonomy for classification and discovery.

    Example::

        taxonomy = Taxonomy(name="agent_capabilities")
        root = taxonomy.add_root("capabilities", "Agent Capabilities")

        nlp = taxonomy.add_node("nlp", "NLP", parent_slug="capabilities")
        taxonomy.add_node("summarization", "Text Summarization", parent_slug="nlp")
        taxonomy.add_node("sentiment", "Sentiment Analysis", parent_slug="nlp")

        results = taxonomy.classify("summarize this document")
        for r in results:
            print(f"  {r.node.name}: {r.confidence:.0%} (path: {' > '.join(r.path)})")
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._nodes: dict[str, TaxonomyNode] = {}
        self._slug_index: dict[str, str] = {}  # slug -> node_id
        self._children: dict[str, list[str]] = {}  # parent_id -> [child_ids]

    def add_root(self, slug: str, name: str, description: str = "") -> TaxonomyNode:
        return self.add_node(slug, name, description=description, parent_slug=None)

    def add_node(
        self,
        slug: str,
        name: str,
        description: str = "",
        parent_slug: str | None = None,
        synonyms: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        weight: float = 1.0,
    ) -> TaxonomyNode:
        parent_id: str | None = None
        if parent_slug:
            parent = self.find_by_slug(parent_slug)
            if not parent:
                raise ValueError(f"Parent slug '{parent_slug}' not found in taxonomy '{self.name}'")
            parent_id = parent.id

        node = TaxonomyNode(
            name=name,
            slug=slug,
            description=description,
            parent_id=parent_id,
            synonyms=synonyms or [],
            metadata=metadata or {},
            weight=weight,
        )
        self._nodes[node.id] = node
        self._slug_index[slug] = node.id
        if parent_id:
            self._children.setdefault(parent_id, []).append(node.id)
        logger.debug("Taxonomy node added", taxonomy=self.name, slug=slug)
        return node

    def find_by_slug(self, slug: str) -> TaxonomyNode | None:
        node_id = self._slug_index.get(slug)
        return self._nodes.get(node_id) if node_id else None

    def find_by_id(self, node_id: str) -> TaxonomyNode | None:
        return self._nodes.get(node_id)

    def get_children(self, slug: str) -> list[TaxonomyNode]:
        node = self.find_by_slug(slug)
        if not node:
            return []
        return [self._nodes[cid] for cid in self._children.get(node.id, []) if cid in self._nodes]

    def get_ancestors(self, slug: str) -> list[TaxonomyNode]:
        node = self.find_by_slug(slug)
        if not node:
            return []
        ancestors: list[TaxonomyNode] = []
        current = node
        while current.parent_id:
            parent = self._nodes.get(current.parent_id)
            if not parent:
                break
            ancestors.insert(0, parent)
            current = parent
        return ancestors

    def get_path(self, slug: str) -> list[str]:
        """Return slugs from root to this node."""
        ancestors = self.get_ancestors(slug)
        node = self.find_by_slug(slug)
        return [a.slug for a in ancestors] + ([node.slug] if node else [])

    def get_subtree(self, slug: str) -> list[TaxonomyNode]:
        """Return all nodes in the subtree rooted at slug."""
        root = self.find_by_slug(slug)
        if not root:
            return []
        result: list[TaxonomyNode] = [root]
        queue = [root.id]
        while queue:
            node_id = queue.pop(0)
            for child_id in self._children.get(node_id, []):
                child = self._nodes.get(child_id)
                if child:
                    result.append(child)
                    queue.append(child_id)
        return result

    def classify(self, text: str, top_k: int = 5, fuzzy: bool = True) -> list[ClassificationResult]:
        """
        Classify text against all nodes, returning ranked matches.
        Uses keyword matching with TF-like scoring.
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        results: list[ClassificationResult] = []

        for node in self._nodes.values():
            score = self._score(node, text_lower, words, fuzzy)
            if score > 0:
                path = self.get_path(node.slug)
                depth = len(path) - 1
                results.append(
                    ClassificationResult(
                        node=node,
                        confidence=min(score, 1.0),
                        path=path,
                        depth=depth,
                    )
                )

        results.sort(key=lambda r: (-r.confidence, -r.depth))
        return results[:top_k]

    @staticmethod
    def _score(node: TaxonomyNode, text_lower: str, words: set[str], fuzzy: bool) -> float:
        score = 0.0
        name_lower = node.name.lower()
        slug_lower = node.slug.lower()

        # Exact slug/name match → high score
        if name_lower in text_lower or slug_lower in text_lower:
            score += 0.8 * node.weight
        # Word overlap
        node_words = set(name_lower.split("_") + name_lower.split())
        overlap = len(words & node_words)
        score += overlap * 0.2

        # Synonym matches
        for syn in node.synonyms:
            if syn.lower() in text_lower:
                score += 0.6 * node.weight

        if fuzzy and not score:
            for word in words:
                if len(word) > 3 and (word in name_lower or name_lower in word):
                    score += 0.3
        return score

    def list_all(self) -> list[TaxonomyNode]:
        return list(self._nodes.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [n.model_dump() for n in self._nodes.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Taxonomy:
        taxonomy = cls(name=data["name"], description=data.get("description", ""))
        for node_data in data.get("nodes", []):
            node = TaxonomyNode(**node_data)
            taxonomy._nodes[node.id] = node
            taxonomy._slug_index[node.slug] = node.id
            if node.parent_id:
                taxonomy._children.setdefault(node.parent_id, []).append(node.id)
        return taxonomy

    def __repr__(self) -> str:
        return f"Taxonomy(name={self.name!r}, nodes={len(self._nodes)})"


class TaxonomyRegistry:
    """Registry for named taxonomies across the platform."""

    def __init__(self) -> None:
        self._taxonomies: dict[str, Taxonomy] = {}

    def register(self, taxonomy: Taxonomy) -> None:
        self._taxonomies[taxonomy.name] = taxonomy

    def get(self, name: str) -> Taxonomy | None:
        return self._taxonomies.get(name)

    def list_names(self) -> list[str]:
        return list(self._taxonomies.keys())

    @classmethod
    def with_defaults(cls) -> TaxonomyRegistry:
        """Create a registry pre-loaded with standard platform taxonomies."""
        registry = cls()

        # Agent type taxonomy
        agent_tax = Taxonomy(name="agent_types", description="MCP agent interaction patterns")
        agent_tax.add_root("patterns", "Interaction Patterns")
        agent_tax.add_node(
            "a2a",
            "Agent-to-Agent",
            parent_slug="patterns",
            synonyms=["agent communication", "peer agents", "multi-agent"],
        )
        agent_tax.add_node(
            "a2b",
            "Agent-to-Business",
            parent_slug="patterns",
            synonyms=["business API", "enterprise integration", "SaaS"],
        )
        agent_tax.add_node(
            "b2b",
            "Business-to-Business",
            parent_slug="patterns",
            synonyms=["partner integration", "multi-tenant", "cross-org"],
        )
        agent_tax.add_node(
            "b2c",
            "Business-to-Customer",
            parent_slug="patterns",
            synonyms=["end user", "customer support", "conversational"],
        )
        registry.register(agent_tax)

        # Capability taxonomy
        cap_tax = Taxonomy(name="capabilities", description="Agent capability classification")
        cap_tax.add_root("capabilities", "All Capabilities")
        cap_tax.add_node("nlp", "Natural Language Processing", parent_slug="capabilities")
        cap_tax.add_node(
            "summarization",
            "Summarization",
            parent_slug="nlp",
            synonyms=["summarize", "condense", "tldr"],
        )
        cap_tax.add_node(
            "sentiment",
            "Sentiment Analysis",
            parent_slug="nlp",
            synonyms=["emotion", "opinion", "feeling"],
        )
        cap_tax.add_node(
            "translation",
            "Translation",
            parent_slug="nlp",
            synonyms=["translate", "multilingual", "language"],
        )
        cap_tax.add_node(
            "search",
            "Search & Retrieval",
            parent_slug="capabilities",
            synonyms=["lookup", "find", "query", "retrieve"],
        )
        cap_tax.add_node(
            "reasoning",
            "Reasoning",
            parent_slug="capabilities",
            synonyms=["think", "analyze", "deduce", "infer"],
        )
        cap_tax.add_node(
            "code",
            "Code Generation",
            parent_slug="capabilities",
            synonyms=["programming", "coding", "development"],
        )
        registry.register(cap_tax)

        # Security taxonomy
        sec_tax = Taxonomy(name="security", description="Security threat classification")
        sec_tax.add_root("threats", "Security Threats")
        sec_tax.add_node("injection", "Injection Attacks", parent_slug="threats")
        sec_tax.add_node("prompt_injection", "Prompt Injection", parent_slug="injection")
        sec_tax.add_node("sql_injection", "SQL Injection", parent_slug="injection")
        sec_tax.add_node("access_control", "Access Control", parent_slug="threats")
        sec_tax.add_node(
            "privilege_escalation", "Privilege Escalation", parent_slug="access_control"
        )
        sec_tax.add_node("data", "Data Security", parent_slug="threats")
        sec_tax.add_node("pii", "PII Exposure", parent_slug="data")
        sec_tax.add_node("exfiltration", "Data Exfiltration", parent_slug="data")
        registry.register(sec_tax)

        return registry

    _global: TaxonomyRegistry | None = None

    @classmethod
    def global_registry(cls) -> TaxonomyRegistry:
        if cls._global is None:
            cls._global = cls.with_defaults()
        return cls._global
