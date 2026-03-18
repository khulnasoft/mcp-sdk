import asyncio
import shutil
from pathlib import Path
from tempfile import TemporaryPlaybooksy

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_plugin_install() -> None:
    print("\nStarting Plugin Install verification...")

    with TemporaryPlaybooksy() as tmp_dir:
        # 1. Create a dummy plugin to install
        source_dir = Path(tmp_dir) / "test_install_plugin"
        source_dir.mkdir()
        (source_dir / "plugin.yaml").write_text("""
name: test_install
version: 1.0.0
description: A plugin installed via shim
entrypoint: plugin:Plugin
""")
        (source_dir / "__init__.py").write_text("")
        (source_dir / "plugin.py").write_text("""
from mcp_sdk.core.plugin import MCPPlugin
class Plugin(MCPPlugin):
    @property
    def name(self): return "test_install"
""")

        # 2. Setup Manager
        registry = PluginRegistry()
        manager = PluginManager(registry)

        # 3. Use Install Shim
        print(f"Installing plugin from {source_dir}...")
        success = await manager.install_plugin(str(source_dir))
        assert success is True

        # 4. Verify on disk
        installed_path = manager.plugin_dir / "test_install_plugin"
        assert installed_path.exists()
        assert (installed_path / "plugin.yaml").exists()
        print(f"Plugin verified on disk at {installed_path}")

        # 5. Verify Discovery
        await manager.load_and_activate_all()
        assert registry.get_plugin("test_install") is not None
        print("Plugin successfully loaded and activated after install!")

        # Cleanup
        if installed_path.exists():
            shutil.rmtree(installed_path)


if __name__ == "__main__":
    asyncio.run(test_plugin_install())
