from __future__ import annotations


class ContextCompressor:
    """
    Reduces the size of tool outputs and logs to fit within agent context windows.
    """

    @staticmethod
    def compress(text: str, max_lines: int = 50, max_chars: int = 2000) -> str:
        """
        Heuristic-based compression:
        - Truncates long outputs.
        - Keeps head and tail for large blocks.
        - Ready for future integration with LLM summarizers.
        """
        if not text:
            return ""

        TRUNC_MARKER = "\n\n[... content truncated for context efficiency ...]\n\n"

        # Line-based truncation
        lines = text.splitlines()
        if len(lines) > max_lines:
            head = lines[: max_lines // 2]
            tail = lines[-(max_lines // 2) :]
            text = "\n".join(head) + TRUNC_MARKER + "\n".join(tail)

        # Character-based truncation
        if len(text) > max_chars:
            text = text[: max_chars // 2] + TRUNC_MARKER + text[-(max_chars // 2) :]

        return text

    @staticmethod
    def summarize_patterns(text: str) -> str:
        """
        Placeholder for pattern-based summarization (e.g., repeating errors).
        """
        # In a real implementation, this would detect repeating sequences
        # and replace them with "Repeated X times: ..."
        return text
