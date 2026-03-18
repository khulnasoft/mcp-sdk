"""
Active Inquiry Automation
=========================
Triggers automated verification tools when the agent's "surprise threshold"
is exceeded. This resolves ambiguities in the Scaffold working memory.

Features:
- Surprise-triggered verification (threshold > 0.7)
- External tool orchestration (Mapbox DevKit, Google Maps API)
- Result re-ingestion into Active Inference Engine
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from mcp_sdk.core.registry import PluginRegistry
from mcp_sdk.plugins.active_inference.active_inference import ActiveInferenceEngine, InferenceResult

logger = structlog.get_logger(__name__)


class VerificationResult(BaseModel):
    """The outcome of an automated inquiry."""

    inquiry_id: str
    tool_name: str
    observation: Any
    confidence: float
    timestamp: float = Field(default_factory=lambda: 0.0)  # Placeholder


class ActiveInquiryManager:
    """
    Orchestrates "Active Inquiries" to resolve high prediction errors.
    """

    def __init__(
        self, registry: PluginRegistry, engine: ActiveInferenceEngine, threshold: float = 0.7
    ) -> None:
        self.registry = registry
        self.engine = engine
        self.threshold = threshold
        self._inquiry_count = 0

        # Register as callback for surprise
        self.engine._on_surprise = self.handle_surprise

    async def handle_surprise(self, result: InferenceResult) -> None:
        """Called by the inference engine when surprise is high."""
        if result.surprise > self.threshold:
            logger.info(
                "High surprise detected! Triggering active inquiry...",
                surprise=result.surprise,
                threshold=self.threshold,
            )
            await self.trigger_inquiry(result)

    async def trigger_inquiry(self, cause: InferenceResult) -> VerificationResult | None:
        """
        Automates the selection and execution of verification tools.
        """
        self._inquiry_count += 1

        # 1. Discover verification tools
        # In this vision, we look for tools tagged with 'verification' or 'groundtruth'
        tools = self.registry.discover_tools("verify groundtruth mapbox")
        if not tools:
            logger.warning("No verification tools found in registry.")
            return None

        best_tool_name, score = tools[0]
        logger.info("Selected verification tool", tool=best_tool_name, score=score)

        # 2. Execute inquiry tool
        # For the roadmap, we simulate calling 'mapbox.verify_location'
        tool_func = self.registry.get_tool(best_tool_name)
        if not tool_func:
            return None

        try:
            # We pass the causational observation to give the tool context
            # In a real system, the tool might perform a fresh API call to Mapbox
            inquiry_result = await tool_func(location=cause.observation)

            # 3. Process result
            verification = VerificationResult(
                inquiry_id=f"inq_{self._inquiry_count}",
                tool_name=best_tool_name,
                observation=inquiry_result,
                confidence=0.95,  # High confidence in ground-truth tools
            )

            # 4. Feedback loop: Feed verification back into inference engine
            # This 'resolves' the surprise by giving a high-precision observation
            if isinstance(inquiry_result, list):  # Expected vector format
                await self.engine.infer(inquiry_result)
                logger.info(
                    "Inquiry resolved surprise via feedback loop",
                    inquiry_id=verification.inquiry_id,
                )

            return verification

        except Exception as e:
            logger.error("Active inquiry failed", tool=best_tool_name, error=str(e))
            return None

    @property
    def stats(self) -> dict[str, Any]:
        return {"inquiries_triggered": self._inquiry_count, "current_threshold": self.threshold}
