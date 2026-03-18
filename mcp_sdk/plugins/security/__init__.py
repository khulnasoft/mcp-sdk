"""
Security Plugin for MCP SDK
===========================
Provides automated security scanning for prompt injection,
PII exposure, and other architectural anti-patterns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp_sdk.core.plugin import PluginBase
from mcp_sdk.plugins.security.scanner import (
    SECURITY_PATTERNS,
    AntiPatternCategory,
    AntiPatternMatch,
    AntiPatternSeverity,
    SecurityPattern,
    SecurityScanner,
)


class SecurityPlugin(PluginBase):
    """
    Plugin for security monitoring.
    Registers middleware for real-time scanning of interactions.
    """

    def __init__(self, protocol: Any) -> None:
        super().__init__(protocol)
        self.scanner = SecurityScanner()

    @property
    def name(self) -> str:
        return "security"

    @property
    def version(self) -> str:
        return "0.2.0"

    async def setup(self) -> None:
        """Register security middleware."""

        @self.protocol.use_middleware
        async def security_middleware(kwargs: dict[str, Any]) -> dict[str, Any]:
            # Scan incoming tool arguments and message content
            text_to_scan = str(kwargs)
            matches = self.scanner.scan(text_to_scan)

            if matches:
                highest = self.scanner.highest_severity(matches)
                if highest in (AntiPatternSeverity.CRITICAL, AntiPatternSeverity.HIGH):
                    from mcp_sdk.core.exceptions import SecurityBlockError

                    raise SecurityBlockError(f"Security policy violation: {matches[0].description}")

            return kwargs

        @self.protocol.tool(
            "security_scan_text", description="Manually scan text for security anti-patterns."
        )
        async def scan_text(text: str) -> list[dict[str, Any]]:
            matches = self.scanner.scan(text)
            return [m.model_dump() for m in matches]

    async def teardown(self) -> None:
        pass


__all__ = [
    "SecurityPlugin",
    "SecurityScanner",
    "SecurityPattern",
    "AntiPatternCategory",
    "AntiPatternSeverity",
    "AntiPatternMatch",
    "SECURITY_PATTERNS",
]
