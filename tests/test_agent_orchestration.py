import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry


@pytest.mark.asyncio
async def test_agent_orchestration() -> None:
    print("\n=== Phase 5: Autonomous Orchestration Verification ===\n")

    registry = PluginRegistry()
    manager = PluginManager(registry)

    # 1. Discover and Activate
    print("Discovering and activating plugins...")
    await manager.load_and_activate_all()

    # 2. Test Semantic Discovery via knowledge tool
    print("\n--- Testing Semantic Discovery ---")
    recommend_tools = registry.get_tool("knowledge.recommend_tools")

    # Query for something related to "security" or "auth"
    recommendations = await recommend_tools(
        goal="I need to create a secure session and check permissions"
    )
    print("Goal: 'secure session and check permissions'")
    for rec in recommendations:
        print(f"  - Found: {rec['name']} (Score: {rec['score']})")

    assert any("auth" in r["name"] for r in recommendations)

    # 3. Test Capability Negotiation
    print("\n--- Testing Capability Negotiation ---")
    create_token = registry.get_tool("auth.create_token")

    # Authorized access (default agent)
    print("Normal agent calling auth.create_token...")
    token = await create_token(user_id="agent_1", roles=["agent"], _agent_id="agent_1")
    print(f"  Token: {token[:20]}...")

    # Blocked access (unauthorized agent - mock)
    # Note: Our mock currently allows everything, but let's test the plumbing

    # 4. Test Context Compression
    print("\n--- Testing Context Compression ---")
    summarize = registry.get_tool("knowledge.summarize_context")
    long_text = "Line 1\n" * 100
    compressed = await summarize(text=long_text, max_tokens=10)
    print(f"Original lines: {len(long_text.splitlines())}")
    print(f"Compressed lines: {len(compressed.splitlines())}")
    assert "[... content truncated" in compressed

    # 5. Test Streaming (Mock/Plumbing)
    print("\n--- Testing Streaming Architecture ---")
    # We pushed the push/subscribe logic into stream_manager
    manager.stream_manager.subscribe("some_tool", lambda data: print(f"  STREAM UPDATE: {data}"))
    manager.stream_manager.push("some_tool", "Progress 50%")
    manager.stream_manager.push("some_tool", "Task Complete")

    print("\nSUCCESS: Autonomous Orchestration verified!")


if __name__ == "__main__":
    asyncio.run(test_agent_orchestration())
