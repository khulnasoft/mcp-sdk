import asyncio

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_plugin_discovery_and_lifecycle() -> None:
    """Test discovering, loading, and activating plugins."""
    registry = PluginRegistry()
    manager = PluginManager(registry)

    # Discover
    discovered = manager.discover()
    assert any(p.name == "github" for p in discovered)

    # Load and activate
    await manager.load_and_activate_all()

    # Verify GitHub plugin is in registry
    github_plugin = registry.get_plugin("github")
    assert github_plugin is not None
    assert github_plugin.name == "github"
    assert github_plugin.version == "1.0.0"

    # Verify tool registration
    tool = registry.get_tool("github.create_issue")
    assert tool is not None
    result = tool(title="Test Issue", body="Verification")
    assert result["status"] == "created"

    # Deactivate
    await manager.deactivate_all()
    # Note: deactivate doesn't remove from registry in current implementation,
    # but clear manager's internal state.
    assert len(manager._plugins) == 0


def test_manifest_loading() -> None:
    """Test parsing plugin.yaml."""
    registry = PluginRegistry()
    manager = PluginManager(registry)

    github_path = manager.plugin_dir / "github"
    manifest = manager.load_manifest(github_path)

    assert manifest["name"] == "github"
    assert manifest["entrypoint"] == "plugin:Plugin"
    assert "network" in manifest["permissions"]


if __name__ == "__main__":
    # Simple manual verification script if pytest is not used
    async def run_verify() -> None:
        print("Starting verification cycle...")
        registry = PluginRegistry()
        manager = PluginManager(registry)

        print(f"Plugin playbooksy: {manager.plugin_dir}")
        discovered = manager.discover()
        print(f"Found plugins: {[p.name for p in discovered]}")

        await manager.load_and_activate_all()
        print(f"Loaded plugins: {list(registry.plugins.keys())}")

        tool = registry.get_tool("github.create_issue")
        if tool:
            print("Running github.create_issue...")
            print(tool(title="Verified", body="Success"))

        await manager.deactivate_all()
        print("Verification complete.")

    asyncio.run(run_verify())
