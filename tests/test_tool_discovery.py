import asyncio

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_tool_discovery() -> None:
    print("\nStarting Tool Discovery verification...")

    registry = PluginRegistry()
    manager = PluginManager(registry)

    # 1. Load plugins
    print("Loading plugins...")
    await manager.load_and_activate_all()

    # 2. Discover all tools
    all_tools = registry.discover_tools()
    print(f"Total tools discovered: {len(all_tools)}")
    assert "github.create_issue" in all_tools

    # 3. Discover by tag
    git_tools = registry.discover_tools(tag="git")
    print(f"Tools with tag 'git': {list(git_tools.keys())}")
    assert "github.create_issue" in git_tools

    # 4. Verify metadata
    metadata = registry.get_tool_metadata("github.create_issue")
    print(f"Tool metadata: {metadata}")
    assert metadata["description"] == "Create a new GitHub issue"
    assert "issue" in metadata["tags"]

    # 5. Search for non-existent tag
    missing_tools = registry.discover_tools(tag="non-existent")
    assert len(missing_tools) == 0

    print("SUCCESS: Tool discovery and routing verified!")


if __name__ == "__main__":
    asyncio.run(test_tool_discovery())
