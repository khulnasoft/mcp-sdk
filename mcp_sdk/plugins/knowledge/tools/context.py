from __future__ import annotations

from collections.abc import Callable

from mcp_sdk.core.compression import ContextCompressor


def summarize_context() -> Callable:
    def _summarize_context(text: str, max_tokens: int = 500) -> str:
        """Compress and summarize text."""
        # Note: In a real implementation using tokens, we'd use a tokenizer.
        # For now, we use our ContextCompressor heuristic.
        return ContextCompressor.compress(text, max_lines=20, max_chars=max_tokens * 4)

    return _summarize_context
