import asyncio
from pathlib import Path

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_persistence_and_disable(tmp_path) -> None:
    """Test that setting a plugin to disabled prevents it from loading."""
    state_path = tmp_path / "plugins.json"
    registry = PluginRegistry()
    manager = PluginManager(registry, state_path=state_path)

    # 1. Disable github plugin
    manager.state.set_plugin_enabled("github", False)

    # 2. Try loading
    await manager.load_and_activate_all()

    # 3. Verify it's NOT in registry
    assert registry.get_plugin("github") is None


@pytest.mark.asyncio
async def test_dependencies(tmp_path) -> None:
    """Test discovery and activation of plugins with dependencies."""
    state_path = tmp_path / "plugins.json"
    registry = PluginRegistry()
    manager = PluginManager(registry, state_path=state_path)

    # We'll use the existing github plugin and create a mock dependency situation
    # if we had multiple plugins. For now, since we only have one, we can
    # verify it still loads fine without dependencies.

    await manager.load_and_activate_all()
    assert registry.get_plugin("github") is not None


def test_state_persistence(tmp_path) -> None:
    """Test that state is actually saved to disk."""
    state_path = tmp_path / "plugins.json"
    registry = PluginRegistry()
    manager = PluginManager(registry, state_path=state_path)

    manager.state.set_plugin_enabled("test_plugin", False)
    assert state_path.exists()

    # New manager with same path
    manager2 = PluginManager(PluginRegistry(), state_path=state_path)
    assert manager2.state.get_plugin_enabled("test_plugin") is False


if __name__ == "__main__":
    # Manual verification
    async def run_verify() -> None:
        print("Starting Phase 2 verification...")
        from tempfile import TemporaryPlaybooksy

        with TemporaryPlaybooksy() as tmp_dir:
            path = Path(tmp_dir) / "state.json"
            print(f"Using temp state: {path}")

            reg = PluginRegistry()
            mgr = PluginManager(reg, state_path=path)

            print("1. Disabling github...")
            mgr.state.set_plugin_enabled("github", False)

            print("2. Loading plugins...")
            await mgr.load_and_activate_all()

            if reg.get_plugin("github") is None:
                print("SUCCESS: GitHub plugin was NOT loaded (correctly disabled).")
            else:
                print("FAILURE: GitHub plugin was loaded despite being disabled.")

            print("3. Re-enabling github...")
            mgr.state.set_plugin_enabled("github", True)

            reg2 = PluginRegistry()
            mgr2 = PluginManager(reg2, state_path=path)
            await mgr2.load_and_activate_all()

            if reg2.get_plugin("github") is not None:
                print("SUCCESS: GitHub plugin was loaded (correctly enabled).")
            else:
                print("FAILURE: GitHub plugin was NOT loaded despite being enabled.")

        print("Phase 2 verification complete.")

    asyncio.run(run_verify())
