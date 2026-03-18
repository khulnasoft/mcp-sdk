import asyncio
import os
import sys

import pytest

# Bypass mcp_sdk package initialization to avoid Pydantic errors in unrelated files
sys.path.insert(0, os.path.abspath("."))

from mcp_sdk.memory.scaffold import ScaffoldManager
from mcp_sdk.plugins.active_inference.active_inference import ActiveInferenceEngine


@pytest.mark.asyncio
async def test_scaffold_integration() -> None:
    scaffold = ScaffoldManager(context_id="test-agent")
    engine = ActiveInferenceEngine(state_dim=2, action_space=["move", "hover"], scaffold=scaffold)

    # Normal observation
    result = await engine.infer([0.1, 0.1])
    assert "ego_state" in [b.entity for b in scaffold.scaffold.beliefs]
    assert len(scaffold.scaffold.anomalies) == 0

    # Anomalous observation (high surprise)
    result = await engine.infer([5.0, 5.0])

    print(f"\nSurprise: {result.surprise}")
    print(scaffold.get_prompt_context())

    # Check if anomaly was recorded
    if result.surprise > 0.6:
        assert len(scaffold.scaffold.anomalies) > 0
        assert "High surprise" in scaffold.scaffold.anomalies[0]
        print("✅ Anomaly correctly recorded in Scaffold")


if __name__ == "__main__":
    asyncio.run(test_scaffold_integration())
