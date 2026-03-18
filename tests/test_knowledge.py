"""Tests for Knowledge Graph Memory."""

import pytest

from mcp_sdk.knowledge.graph import KnowledgeGraph


class TestKnowledgeGraph:
    @pytest.fixture
    def kg(self):
        return KnowledgeGraph(namespace="test")

    @pytest.fixture
    def populated_kg(self):
        graph = KnowledgeGraph(namespace="org")
        alice = graph.add_entity("Alice", entity_type="person", properties={"role": "engineer"})
        bob = graph.add_entity("Bob", entity_type="person")
        acme = graph.add_entity("Acme Corp", entity_type="org")
        mcp = graph.add_entity("MCP Project", entity_type="project")

        graph.add_relationship(alice.id, "works_for", acme.id)
        graph.add_relationship(bob.id, "works_for", acme.id)
        graph.add_relationship(alice.id, "leads", mcp.id)
        graph.add_relationship(bob.id, "contributes_to", mcp.id)

        graph.add_fact(alice.id, "Alice is the lead architect of the MCP platform")
        graph.add_fact(acme.id, "Acme Corp was founded in 2010")
        return graph, alice, bob, acme, mcp

    # ── Entity operations ─────────────────────────────────────────────

    def test_add_and_find_entity(self, kg) -> None:
        kg.add_entity("Python", entity_type="language")
        found = kg.find_entity("Python")
        assert found is not None
        assert found.name == "Python"
        assert found.entity_type == "language"

    def test_entity_deduplication(self, kg) -> None:
        e1 = kg.add_entity("Alice")
        e2 = kg.add_entity("Alice")
        assert e1.id == e2.id
        assert e2.observation_count == 2

    def test_entity_properties_merged(self, kg) -> None:
        kg.add_entity("Alice", properties={"role": "engineer"})
        e = kg.add_entity("Alice", properties={"dept": "platform"})
        assert e.properties.get("role") == "engineer"
        assert e.properties.get("dept") == "platform"

    def test_find_entities_by_type(self, populated_kg) -> None:
        graph, alice, bob, acme, mcp = populated_kg
        persons = graph.find_entities("person")
        assert len(persons) == 2
        assert all(p.entity_type == "person" for p in persons)

    def test_remove_entity(self, kg) -> None:
        e = kg.add_entity("Temp")
        kg.remove_entity(e.id)
        assert kg.find_entity("Temp") is None

    # ── Relationship operations ───────────────────────────────────────

    def test_add_relationship(self, populated_kg) -> None:
        graph, alice, bob, acme, mcp = populated_kg
        neighbors = graph.get_neighbors(alice.id, direction="out")
        rel_types = {r.relation_type for r, _ in neighbors}
        assert "works_for" in rel_types
        assert "leads" in rel_types

    def test_relationship_deduplication(self, kg) -> None:
        a = kg.add_entity("A")
        b = kg.add_entity("B")
        r1 = kg.add_relationship(a.id, "knows", b.id)
        r2 = kg.add_relationship(a.id, "knows", b.id)
        assert r1.id == r2.id
        assert r2.observation_count == 2

    def test_incoming_neighbors(self, populated_kg) -> None:
        graph, alice, bob, acme, mcp = populated_kg
        # acme's incoming neighbors should include alice and bob
        incoming = graph.get_neighbors(acme.id, direction="in")
        names = {e.name for _, e in incoming}
        assert "Alice" in names
        assert "Bob" in names

    # ── Facts ─────────────────────────────────────────────────────────

    def test_add_and_retrieve_facts(self, populated_kg) -> None:
        graph, alice, *_ = populated_kg
        facts = graph.get_facts(alice.id)
        assert len(facts) == 1
        assert "lead architect" in facts[0].fact

    # ── Traversal ─────────────────────────────────────────────────────

    def test_bfs_traversal(self, populated_kg) -> None:
        graph, alice, bob, acme, mcp = populated_kg
        paths = graph.traverse(alice.id, max_depth=2)
        end_entities = {p.entities[-1].name for p in paths}
        assert "Acme Corp" in end_entities
        assert "MCP Project" in end_entities

    def test_shortest_path(self, populated_kg) -> None:
        graph, alice, bob, acme, mcp = populated_kg
        path = graph.shortest_path(alice.id, acme.id)
        assert path is not None
        assert path.depth == 1
        assert path.entities[0].name == "Alice"
        assert path.entities[-1].name == "Acme Corp"

    def test_no_path_returns_none(self, kg) -> None:
        a = kg.add_entity("Isolated A")
        b = kg.add_entity("Isolated B")
        path = kg.shortest_path(a.id, b.id)
        assert path is None

    # ── Context generation ────────────────────────────────────────────

    def test_get_context(self, populated_kg) -> None:
        graph, alice, *_ = populated_kg
        ctx = graph.get_context_for(alice.id)
        assert "Alice" in ctx
        assert "engineer" in ctx  # from properties

    # ── Export ────────────────────────────────────────────────────────

    def test_to_json(self, populated_kg) -> None:
        graph, *_ = populated_kg
        data = graph.to_json()
        import json

        parsed = json.loads(data)
        assert parsed["namespace"] == "org"
        assert len(parsed["entities"]) == 4
        assert len(parsed["relationships"]) == 4

    def test_to_dot(self, populated_kg) -> None:
        graph, *_ = populated_kg
        dot = graph.to_dot()
        assert "digraph" in dot
        assert "works_for" in dot

    # ── Stats ─────────────────────────────────────────────────────────

    def test_stats(self, populated_kg) -> None:
        graph, *_ = populated_kg
        s = graph.stats
        assert s["entities"] == 4
        assert s["relationships"] == 4
        assert s["facts"] == 2
