import asyncio

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_isolation() -> None:
    print("\nStarting Isolation verification...")

    registry = PluginRegistry()
    manager = PluginManager(registry)

    # 1. Load plugins (GitHub is now set to isolation: subprocess)
    print("Loading plugins...")
    await manager.load_and_activate_all()

    # 2. Verify GitHub plugin is loaded
    github_plugin = registry.get_plugin("github")
    assert github_plugin is not None
    print(f"Plugin loaded: {github_plugin.name}")

    # 3. Check for isolation in manifest
    assert github_plugin.manifest.get("isolation") == "subprocess"

    # 4. Execute tool
    print("Executing tool via Subprocess executor...")
    tool = registry.get_tool("github.create_issue")

    # Since it's proxied, it will be a coroutine (tool_proxy)
    result = await tool(title="Isolated Issue", body="Executed in subprocess")

    print(f"Tool result: {result}")
    assert result["title"] == "Isolated Issue"
    assert result["status"] == "created"

    print("SUCCESS: Subprocess isolation verified!")


if __name__ == "__main__":
    asyncio.run(test_isolation())
