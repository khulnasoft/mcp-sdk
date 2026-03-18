"""Tests for Token-Budget Context Manager."""

import time

import pytest

from mcp_sdk.plugins.context.manager import (
    ContextCompressor,
    ContextItem,
    TokenBudgetManager,
    estimate_tokens,
)


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 1  # min 1

    def test_rough_estimate(self) -> None:
        text = "a" * 400
        est = estimate_tokens(text)
        assert 90 <= est <= 110  # ~100 tokens at 4 chars/tok

    def test_longer_text_more_tokens(self) -> None:
        short = estimate_tokens("short")
        long = estimate_tokens("x" * 1000)
        assert long > short


class TestContextItem:
    def test_token_auto_estimate(self) -> None:
        item = ContextItem(content="Hello world this is a test")
        assert item.token_count > 0

    def test_pinned_default_false(self) -> None:
        item = ContextItem(content="test")
        assert item.pinned is False

    def test_eviction_score_pinned_ignored_by_caller(self) -> None:
        item = ContextItem(content="x", priority=0.3)
        assert item.eviction_score() > 0

    def test_age_seconds(self) -> None:
        item = ContextItem(content="test")
        time.sleep(0.01)
        assert item.age_seconds >= 0.01


class TestContextCompressor:
    def test_dedup_removes_duplicates(self) -> None:
        comp = ContextCompressor()
        items = [
            ContextItem(content="same content here"),
            ContextItem(content="same content here"),  # dup
            ContextItem(content="different content"),
        ]
        deduped = comp.deduplicate(items)
        assert len(deduped) == 2

    def test_compress_returns_single_item(self) -> None:
        comp = ContextCompressor(max_summary_tokens=100)
        items = [ContextItem(content=f"item {i} " * 10, priority=0.5) for i in range(5)]
        compressed = comp.compress(items)
        assert isinstance(compressed, ContextItem)
        assert compressed.metadata.get("compressed") is True

    def test_compress_truncates_to_budget(self) -> None:
        comp = ContextCompressor(max_summary_tokens=20)
        items = [ContextItem(content="x" * 200, priority=0.5)] * 5
        compressed = comp.compress(items)
        assert compressed.token_count <= 30  # Some tolerance

    def test_compress_with_summary_fn(self) -> None:
        comp = ContextCompressor(summary_fn=lambda text: "SUMMARIZED")
        items = [ContextItem(content="anything") for _ in range(3)]
        result = comp.compress(items)
        assert result.content == "SUMMARIZED"


class TestTokenBudgetManager:
    @pytest.fixture
    def mgr(self):
        return TokenBudgetManager(max_tokens=100)

    def test_add_item_within_budget(self, mgr) -> None:
        item = ContextItem(content="small item", token_count=10)
        added = mgr.add(item)
        assert added is True
        assert mgr.token_usage == 10

    def test_add_pinned_item(self, mgr) -> None:
        item = ContextItem(content="pinned", token_count=20, pinned=True)
        mgr.add(item)
        assert mgr.token_usage == 20

    def test_eviction_on_overflow(self) -> None:
        mgr = TokenBudgetManager(max_tokens=50)
        low = ContextItem(content="low priority", token_count=30, priority=0.1)
        mgr.add(low)
        high = ContextItem(content="high priority", token_count=30, priority=0.9)
        mgr.add(high)
        # Low priority item should have been evicted to make room
        assert mgr.token_usage <= 50
        assert mgr._evicted_count >= 1

    def test_pinned_item_not_evicted(self) -> None:
        mgr = TokenBudgetManager(max_tokens=50)
        pinned = ContextItem(content="pinned", token_count=30, priority=0.1, pinned=True)
        mgr.add(pinned)
        new_item = ContextItem(content="new", token_count=40, priority=0.9)
        mgr.add(new_item)
        pinned_ids = {i.item_id for i in mgr._items if i.pinned}
        assert pinned.item_id in pinned_ids

    def test_get_context_window_priority_order(self) -> None:
        mgr = TokenBudgetManager(max_tokens=200)
        mgr.add(ContextItem(content="low", token_count=10, priority=0.2))
        mgr.add(ContextItem(content="high", token_count=10, priority=0.8))
        mgr.add(ContextItem(content="mid", token_count=10, priority=0.5))
        window = mgr.get_context_window(order="priority")
        priorities = [i.priority for i in window]
        assert priorities == sorted(priorities, reverse=True)

    def test_get_context_window_chronological(self) -> None:
        mgr = TokenBudgetManager(max_tokens=200)
        t = time.time()
        a = ContextItem(content="a", token_count=10, timestamp=t)
        b = ContextItem(content="b", token_count=10, timestamp=t + 1)
        mgr.add(a)
        mgr.add(b)
        window = mgr.get_context_window(order="chronological")
        assert window[0].content == "a"

    def test_compress_old(self) -> None:
        mgr = TokenBudgetManager(max_tokens=500)
        # Add old items
        for i in range(5):
            item = ContextItem(content=f"old item {i}", token_count=20)
            item.timestamp = time.time() - 300  # 5 minutes old
            mgr._items.append(item)
        count = mgr.compress_old(older_than_seconds=60)
        assert count == 5
        assert mgr._compressed_count == 5

    def test_compress_old_skips_pinned(self) -> None:
        mgr = TokenBudgetManager(max_tokens=500)
        pinned = ContextItem(content="keep this", token_count=10, pinned=True)
        pinned.timestamp = time.time() - 300
        mgr._items.append(pinned)
        old = ContextItem(content="compress this", token_count=10)
        old.timestamp = time.time() - 300
        mgr._items.append(old)
        mgr.compress_old(older_than_seconds=60)
        # Pinned still present
        assert pinned in mgr._items

    def test_pin_item(self) -> None:
        mgr = TokenBudgetManager(max_tokens=200)
        item = ContextItem(content="test", token_count=10)
        mgr.add(item)
        result = mgr.pin(item.item_id)
        assert result is True
        pinned_item = next(i for i in mgr._items if i.item_id == item.item_id)
        assert pinned_item.pinned is True

    def test_remove_item(self) -> None:
        mgr = TokenBudgetManager(max_tokens=200)
        item = ContextItem(content="remove me", token_count=10)
        mgr.add(item)
        removed = mgr.remove(item.item_id)
        assert removed is True
        assert mgr.token_usage == 0

    def test_clear_unpinned(self) -> None:
        mgr = TokenBudgetManager(max_tokens=500)
        pinned = ContextItem(content="keep", token_count=10, pinned=True)
        unpinned = ContextItem(content="clear", token_count=10)
        mgr.add(pinned)
        mgr.add(unpinned)
        cleared = mgr.clear_unpinned()
        assert cleared == 1
        assert len(mgr._items) == 1

    def test_stats(self, mgr) -> None:
        item = ContextItem(content="test item here", token_count=15)
        mgr.add(item)
        stats = mgr.stats()
        assert stats["items"] == 1
        assert stats["token_usage"] == 15
        assert "utilisation_pct" in stats

    def test_budget_remaining(self) -> None:
        mgr = TokenBudgetManager(max_tokens=100)
        mgr.add(ContextItem(content="x", token_count=30))
        assert mgr.token_budget_remaining == 70
