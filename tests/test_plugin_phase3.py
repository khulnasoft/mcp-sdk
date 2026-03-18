import asyncio
import inspect

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_hot_reload() -> None:
    """Verify that hot-reloading a plugin updates its behavior."""
    print("\nStarting Hot Reload verification...")

    # 1. Setup
    registry = PluginRegistry()
    manager = PluginManager(registry)

    # Ensure github plugin is enabled
    manager.state.set_plugin_enabled("github", True)

    # 2. Initial Load
    print("Initial loading...")
    await manager.load_and_activate_all()

    github_plugin = registry.get_plugin("github")
    assert github_plugin is not None

    tool = registry.get_tool("github.create_issue")
    if inspect.iscoroutinefunction(tool):
        result = await tool(title="Original", body="Test body")
    else:
        result = tool(title="Original", body="Test body")

    print(f"Original tool result: {result}")
    assert result["title"] == "Original"

    # 3. Modify Plugin Code on Disk
    plugin_file = manager.plugin_dir / "github" / "tools" / "create_issue.py"
    with open(plugin_file) as f:
        original_code = f.read()

    modified_code = original_code.replace('"title": title', '"title": title + " (Reloaded)"')

    print("Modifying plugin code on disk...")
    with open(plugin_file, "w") as f:
        f.write(modified_code)

    try:
        # 4. Reload
        print("Reloading plugin...")
        success = await manager.reload_plugin("github")
        assert success is True

        # 5. Verify Updated Behavior
        tool = registry.get_tool("github.create_issue")
        if inspect.iscoroutinefunction(tool):
            result = await tool(title="Test", body="Test body")
        else:
            result = tool(title="Test", body="Test body")

        print(f"Reloaded tool result: {result}")
        assert "(Reloaded)" in str(result)
        print("SUCCESS: Hot reload verified!")

    finally:
        # Restore original code
        print("Restoring original code...")
        with open(plugin_file, "w") as f:
            f.write(original_code)


if __name__ == "__main__":
    asyncio.run(test_hot_reload())
