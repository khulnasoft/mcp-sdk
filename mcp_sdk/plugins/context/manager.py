"""
Token-Budget Context Manager
==============================
Solves the token-bloat problem that emerges when agents process large
spatial payloads, live telemetry, or deep reasoning chains.

Core components:
- ContextItem      — A single piece of context with token cost + priority
- TokenBudgetManager — Priority-queue context window with eviction
- ContextCompressor  — Semantic deduplication + summarisation of old items

Design principles:
- Pinned items are NEVER evicted (system prompt, critical facts)
- Eviction removes lowest (priority × recency) items first
- Compression summarises old items rather than discarding them cold
- Token estimation works without tiktoken (char-based fallback)

Usage::

    mgr = TokenBudgetManager(max_tokens=8192)
    mgr.add(ContextItem(content="System: you are a geospatial agent", priority=1.0, pinned=True))
    mgr.add(ContextItem(content=big_map_tile_text, priority=0.4))
    mgr.add(ContextItem(content=latest_sensor_reading, priority=0.9))

    # Get what fits in the window, highest priority first
    window = mgr.get_context_window()
    prompt = "\\n".join(item.content for item in window)
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Token estimation
# ─────────────────────────────────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """
    Character-based token estimate (4 chars ≈ 1 token for English).
    Falls back gracefully when tiktoken is unavailable.
    """
    try:
        import tiktoken  # type: ignore[import]

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except (ImportError, Exception):
        return max(1, len(text) // 4)


# ─────────────────────────────────────────────────────────────────────────────
# Context Item
# ─────────────────────────────────────────────────────────────────────────────


class ContextItem(BaseModel):
    """A single item in the managed context window."""

    item_id: str = Field(
        default_factory=lambda: hashlib.sha1(str(time.time_ns()).encode()).hexdigest()[:12]
    )
    content: str
    token_count: int = Field(default=0)
    priority: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0=disposable, 1=critical; higher survives eviction",
    )
    pinned: bool = Field(default=False, description="Pinned items are NEVER evicted")
    timestamp: float = Field(default_factory=time.time)
    source: str = ""  # e.g. "telemetry", "reasoning", "user"
    metadata: dict[str, Any] = Field(default_factory=dict)
    _score: float = 0.0  # computed eviction score (internal)

    def model_post_init(self, __context: Any) -> None:
        if self.token_count == 0:
            self.token_count = estimate_tokens(self.content)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def eviction_score(self) -> float:
        """
        Lower score → evicted first.
        score = priority * recency_factor
        recency_factor = exp(-age / half_life_seconds)
        """
        half_life = 300.0  # 5 minutes
        recency = 2 ** (-self.age_seconds / half_life)
        return self.priority * recency


# ─────────────────────────────────────────────────────────────────────────────
# Context Compressor
# ─────────────────────────────────────────────────────────────────────────────


class ContextCompressor:
    """
    Reduces a list of ContextItems into a single condensed summary item.

    Steps:
    1. Deduplicate near-identical content (by content hash prefix)
    2. Sort by priority descending
    3. Concatenate until token budget is met, or call `summary_fn` if set
    """

    def __init__(
        self,
        max_summary_tokens: int = 512,
        summary_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.max_summary_tokens = max_summary_tokens
        self.summary_fn = summary_fn  # Optional LLM-based summariser

    def deduplicate(self, items: list[ContextItem]) -> list[ContextItem]:
        """Remove near-duplicate items by first-64-char content hash."""
        seen: set[str] = set()
        unique: list[ContextItem] = []
        for item in items:
            key = hashlib.sha1(item.content[:64].encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def compress(self, items: list[ContextItem]) -> ContextItem:
        """Compress a list of items into a single summary ContextItem."""
        deduped = self.deduplicate(items)
        deduped.sort(key=lambda x: x.priority, reverse=True)

        if self.summary_fn:
            combined_text = "\n".join(i.content for i in deduped)
            summary_text = self.summary_fn(combined_text)
        else:
            # Truncation-based fallback
            lines: list[str] = []
            tokens_used = 0
            for item in deduped:
                if tokens_used + item.token_count > self.max_summary_tokens:
                    break
                lines.append(item.content)
                tokens_used += item.token_count
            summary_text = "\n---\n".join(lines)
            if len(deduped) > len(lines):
                summary_text += f"\n[{len(deduped) - len(lines)} older items omitted]"

        logger.debug(
            "Context compressed", items_in=len(items), tokens_out=estimate_tokens(summary_text)
        )
        return ContextItem(
            content=summary_text,
            priority=max(i.priority for i in deduped) * 0.8,  # Slightly lower than originals
            source="compressor",
            metadata={"original_count": len(items), "compressed": True},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Token Budget Manager
# ─────────────────────────────────────────────────────────────────────────────


class TokenBudgetManager:
    """
    Sliding context window with token budget enforcement.

    Maintains a list of ContextItems ordered by eviction score.
    When adding a new item would exceed `max_tokens`, the lowest-scoring
    non-pinned items are evicted first.

    Example::

        mgr = TokenBudgetManager(max_tokens=8192)

        mgr.add(ContextItem(content="System prompt...", priority=1.0, pinned=True))
        mgr.add(ContextItem(content=map_tile_json, priority=0.3, source="geo"))

        window = mgr.get_context_window()   # fits within budget
        mgr.compress_old(older_than_seconds=120)
    """

    def __init__(
        self,
        max_tokens: int = 8192,
        compressor: ContextCompressor | None = None,
        eviction_strategy: str = "priority_x_recency",
    ) -> None:
        self.max_tokens = max_tokens
        self.compressor = compressor or ContextCompressor()
        self.eviction_strategy = eviction_strategy
        self._items: list[ContextItem] = []
        self._evicted_count = 0
        self._compressed_count = 0

    @property
    def token_usage(self) -> int:
        return sum(i.token_count for i in self._items)

    @property
    def token_budget_remaining(self) -> int:
        return max(0, self.max_tokens - self.token_usage)

    @property
    def utilisation(self) -> float:
        return self.token_usage / self.max_tokens if self.max_tokens else 0.0

    def add(self, item: ContextItem) -> bool:
        """
        Add an item to the context window.
        Returns True if added without eviction, False if eviction was needed.
        """
        needed = self.token_usage + item.token_count
        evicted = False

        if needed > self.max_tokens:
            evicted = self._evict_to_fit(item.token_count)
            if self.token_usage + item.token_count > self.max_tokens:
                logger.warning(
                    "Item too large to add even after eviction",
                    item_tokens=item.token_count,
                    budget=self.max_tokens,
                )
                return False

        self._items.append(item)
        logger.debug(
            "Context item added",
            source=item.source,
            tokens=item.token_count,
            utilisation=f"{self.utilisation:.0%}",
        )
        return not evicted

    def _evict_to_fit(self, needed_tokens: int) -> bool:
        """Evict lowest-scoring non-pinned items until `needed_tokens` are free."""
        non_pinned = [i for i in self._items if not i.pinned]
        non_pinned.sort(key=lambda x: x.eviction_score())  # lowest score first

        freed = 0
        evicted: list[ContextItem] = []
        for item in non_pinned:
            if self.token_usage - freed + needed_tokens <= self.max_tokens:
                break
            freed += item.token_count
            evicted.append(item)

        for item in evicted:
            self._items.remove(item)
            self._evicted_count += 1
            logger.debug(
                "Context item evicted",
                source=item.source,
                priority=item.priority,
                tokens=item.token_count,
            )
        return bool(evicted)

    def get_context_window(self, order: str = "priority") -> list[ContextItem]:
        """
        Return items that fit within the token budget.
        `order`: "priority" (highest first) | "chronological" (oldest first) | "recency" (newest first)
        """
        if order == "priority":
            return sorted(self._items, key=lambda x: -x.priority)
        elif order == "chronological":
            return sorted(self._items, key=lambda x: x.timestamp)
        elif order == "recency":
            return sorted(self._items, key=lambda x: -x.timestamp)
        return list(self._items)

    def compress_old(self, older_than_seconds: float = 120) -> int:
        """
        Compress items older than `older_than_seconds` into a single item.
        Returns number of items compressed.
        """
        cutoff = time.time() - older_than_seconds
        old_items = [i for i in self._items if i.timestamp < cutoff and not i.pinned]
        if len(old_items) < 2:
            return 0

        compressed = self.compressor.compress(old_items)
        for item in old_items:
            self._items.remove(item)
        self._items.append(compressed)
        self._compressed_count += len(old_items)
        logger.info(
            "Context compressed",
            items=len(old_items),
            saved_tokens=sum(i.token_count for i in old_items) - compressed.token_count,
        )
        return len(old_items)

    def pin(self, item_id: str) -> bool:
        for item in self._items:
            if item.item_id == item_id:
                item.pinned = True
                return True
        return False

    def remove(self, item_id: str) -> bool:
        for i, item in enumerate(self._items):
            if item.item_id == item_id:
                self._items.pop(i)
                return True
        return False

    def clear_unpinned(self) -> int:
        before = len(self._items)
        self._items = [i for i in self._items if i.pinned]
        return before - len(self._items)

    def stats(self) -> dict[str, Any]:
        return {
            "items": len(self._items),
            "pinned": sum(1 for i in self._items if i.pinned),
            "token_usage": self.token_usage,
            "max_tokens": self.max_tokens,
            "utilisation_pct": round(self.utilisation * 100, 1),
            "evicted_total": self._evicted_count,
            "compressed_total": self._compressed_count,
        }

    def __repr__(self) -> str:
        return (
            f"TokenBudgetManager(used={self.token_usage}/{self.max_tokens}, "
            f"items={len(self._items)}, evicted={self._evicted_count})"
        )
