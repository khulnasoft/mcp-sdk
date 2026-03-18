"""Tests for Taxonomy Classifier."""

import pytest

from mcp_sdk.plugins.taxonomy.classifier import (
    Taxonomy,
    TaxonomyRegistry,
)


class TestTaxonomy:
    @pytest.fixture
    def taxonomy(self) -> Taxonomy:
        t = Taxonomy(name="capabilities", description="Test taxonomy")
        t.add_root("capabilities", "All Capabilities")
        t.add_node(
            "nlp",
            "Natural Language Processing",
            parent_slug="capabilities",
            synonyms=["text processing", "language"],
        )
        t.add_node(
            "summarization",
            "Text Summarization",
            parent_slug="nlp",
            synonyms=["summarize", "condense"],
        )
        t.add_node(
            "sentiment", "Sentiment Analysis", parent_slug="nlp", synonyms=["emotion", "opinion"]
        )
        t.add_node(
            "search",
            "Search & Retrieval",
            parent_slug="capabilities",
            synonyms=["lookup", "find", "query"],
        )
        return t

    def test_add_and_find_by_slug(self, taxonomy: Taxonomy) -> None:
        node = taxonomy.find_by_slug("nlp")
        assert node is not None
        assert node.name == "Natural Language Processing"

    def test_children(self, taxonomy: Taxonomy) -> None:
        children = taxonomy.get_children("nlp")
        slugs = {c.slug for c in children}
        assert "summarization" in slugs
        assert "sentiment" in slugs

    def test_ancestors(self, taxonomy: Taxonomy) -> None:
        ancestors = taxonomy.get_ancestors("summarization")
        slugs = [a.slug for a in ancestors]
        assert "capabilities" in slugs
        assert "nlp" in slugs

    def test_path(self, taxonomy: Taxonomy) -> None:
        path = taxonomy.get_path("summarization")
        assert path == ["capabilities", "nlp", "summarization"]

    def test_subtree(self, taxonomy: Taxonomy) -> None:
        subtree = taxonomy.get_subtree("nlp")
        slugs = {n.slug for n in subtree}
        assert "nlp" in slugs
        assert "summarization" in slugs
        assert "sentiment" in slugs

    def test_classify_by_name(self, taxonomy: Taxonomy) -> None:
        results = taxonomy.classify("I need nlp processing")
        assert len(results) > 0
        best = results[0]
        assert "nlp" in best.node.slug or any("nlp" in r.node.slug for r in results)

    def test_classify_by_synonym(self, taxonomy: Taxonomy) -> None:
        results = taxonomy.classify("please summarize this text")
        slugs = [r.node.slug for r in results]
        assert "summarization" in slugs

    def test_classify_unknown_returns_empty(self, taxonomy: Taxonomy) -> None:
        results = taxonomy.classify("xyzabcunknownterm12345")
        assert len(results) == 0

    def test_unknown_parent_raises(self, taxonomy: Taxonomy) -> None:
        with pytest.raises(ValueError):
            taxonomy.add_node("test", "Test", parent_slug="nonexistent")

    def test_to_dict_round_trip(self, taxonomy: Taxonomy) -> None:
        data = taxonomy.to_dict()
        restored = Taxonomy.from_dict(data)
        assert restored.name == taxonomy.name
        assert len(restored.list_all()) == len(taxonomy.list_all())

    def test_root_node(self, taxonomy: Taxonomy) -> None:
        root = taxonomy.find_by_slug("capabilities")
        assert root is not None
        assert root.is_root


class TestTaxonomyRegistry:
    def test_with_defaults_has_standard_taxonomies(self) -> None:
        registry = TaxonomyRegistry.with_defaults()
        assert registry.get("agent_types") is not None
        assert registry.get("capabilities") is not None
        assert registry.get("security") is not None

    def test_classify_agent_pattern(self) -> None:
        registry = TaxonomyRegistry.with_defaults()
        cap_tax = registry.get("capabilities")
        assert cap_tax is not None
        results = cap_tax.classify("I want to summarize a long document")
        assert len(results) > 0

    def test_classify_security_threat(self) -> None:
        registry = TaxonomyRegistry.with_defaults()
        sec_tax = registry.get("security")
        results = sec_tax.classify("sql injection attack")
        slugs = [r.node.slug for r in results]
        assert any("injection" in s for s in slugs)

    def test_register_custom(self) -> None:
        registry = TaxonomyRegistry()
        t = Taxonomy(name="custom")
        t.add_root("root", "Root")
        registry.register(t)
        assert registry.get("custom") is not None

    def test_list_names(self) -> None:
        registry = TaxonomyRegistry.with_defaults()
        names = registry.list_names()
        assert "agent_types" in names
        assert "capabilities" in names
