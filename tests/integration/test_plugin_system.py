"""
Integration Tests for Plugin System
==================================
End-to-end testing of plugin discovery, loading, and execution.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry


class TestPlugin(MCPPlugin):
    """Test plugin for integration testing."""

    def __init__(self, name: str = "test_plugin") -> None:
        super().__init__()
        self._name = name
        self.activated = False
        self.tools_registered = False

    @property
    def name(self) -> str:
        return self._name

    async def on_activate(self, protocol) -> None:
        """Plugin activation."""
        self.activated = True
        await super().on_activate(protocol)

    def register_tools(self, registry) -> None:
        """Register plugin tools."""
        self.tools_registered = True

        async def test_tool(message: str) -> str:
            return f"Plugin tool: {message}"

        registry.register_tool(
            f"{self.name}.test_tool",
            test_tool,
            {"description": "Test tool from plugin"}
        )


@pytest_asyncio.fixture
async def plugin_manager():
    """Create a test plugin manager."""
    registry = PluginRegistry()
    manager = PluginManager(registry)
    return manager


@pytest_asyncio.fixture
async def temp_plugin_dir():
    """Create a temporary plugin directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        plugin_dir = Path(temp_dir)

        # Create a test plugin
        plugin_path = plugin_dir / "test_plugin"
        plugin_path.mkdir()

        # Create plugin manifest
        manifest = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "main": "__init__.py",
            "dependencies": [],
            "capabilities": ["tools"],
            "config": {}
        }

        with open(plugin_path / "manifest.yaml", "w") as f:
            yaml.dump(manifest, f)

        # Create plugin code
        plugin_code = '''
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry

class Plugin(MCPPlugin):
    def __init__(self):
        super().__init__()
        self.activated = False

    @property
    def name(self):
        return "test_plugin"

    async def on_activate(self, protocol):
        self.activated = True
        await super().on_activate(protocol)

    def register_tools(self, registry):
        async def test_tool(message: str) -> str:
            return f"Plugin tool: {message}"

        registry.register_tool(
            "test_plugin.test_tool",
            test_tool,
            {"description": "Test tool from plugin"}
        )
'''

        with open(plugin_path / "__init__.py", "w") as f:
            f.write(plugin_code)

        yield plugin_dir


@pytest.mark.asyncio
class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    async def test_discover_plugins(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin discovery from directory."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        discovered = await plugin_manager.discover()

        assert len(discovered) >= 1
        assert any(p.name == "test_plugin" for p in discovered)

    async def test_load_manifest(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test loading plugin manifest."""
        plugin_path = temp_plugin_dir / "test_plugin"

        manifest = await plugin_manager._load_manifest(plugin_path)

        assert manifest is not None
        assert manifest["name"] == "test_plugin"
        assert manifest["version"] == "1.0.0"
        assert "dependencies" in manifest
        assert "capabilities" in manifest

    async def test_load_plugin(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test loading a plugin."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        plugin = await plugin_manager.load_plugin("test_plugin")

        assert plugin is not None
        assert plugin.name == "test_plugin"
        assert isinstance(plugin, MCPPlugin)


@pytest.mark.asyncio
class TestPluginLoading:
    """Test plugin loading and lifecycle."""

    async def test_load_all_plugins(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test loading all plugins from directory."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        loaded_plugins = await plugin_manager.load_all()

        assert len(loaded_plugins) >= 1
        assert "test_plugin" in loaded_plugins

        plugin = loaded_plugins["test_plugin"]
        assert plugin.name == "test_plugin"

    async def test_plugin_activation(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin activation."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        plugin = await plugin_manager.load_plugin("test_plugin")
        assert plugin is not None

        # Mock protocol for activation
        class MockProtocol:
            pass

        await plugin.on_activate(MockProtocol())

        assert plugin.activated is True

    async def test_plugin_tool_registration(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin tool registration."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        await plugin_manager.load_all()

        # Check if tools were registered
        tools = plugin_manager.registry.list_tools()
        assert "test_plugin.test_tool" in tools

    async def test_plugin_dependency_resolution(self) -> None:
        """Test plugin dependency resolution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)

            # Create plugin with dependency
            plugin1_path = plugin_dir / "plugin1"
            plugin1_path.mkdir()

            manifest1 = {
                "name": "plugin1",
                "version": "1.0.0",
                "dependencies": [],
                "capabilities": ["tools"]
            }

            with open(plugin1_path / "manifest.yaml", "w") as f:
                yaml.dump(manifest1, f)

            with open(plugin1_path / "__init__.py", "w") as f:
                f.write("from mcp_sdk.core.plugin import MCPPlugin\nclass Plugin(MCPPlugin): pass")

            # Create plugin that depends on plugin1
            plugin2_path = plugin_dir / "plugin2"
            plugin2_path.mkdir()

            manifest2 = {
                "name": "plugin2",
                "version": "1.0.0",
                "dependencies": ["plugin1"],
                "capabilities": ["tools"]
            }

            with open(plugin2_path / "manifest.yaml", "w") as f:
                yaml.dump(manifest2, f)

            with open(plugin2_path / "__init__.py", "w") as f:
                f.write("from mcp_sdk.core.plugin import MCPPlugin\nclass Plugin(MCPPlugin): pass")

            registry = PluginRegistry()
            manager = PluginManager(registry, plugin_dirs=[plugin_dir])

            # Load all plugins - should handle dependencies correctly
            loaded_plugins = await manager.load_all()

            assert "plugin1" in loaded_plugins
            assert "plugin2" in loaded_plugins


@pytest.mark.asyncio
class TestPluginExecution:
    """Test plugin execution and tool calling."""

    async def test_plugin_tool_execution(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test executing tools from loaded plugins."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        await plugin_manager.load_all()

        # Execute plugin tool
        result = await plugin_manager.registry.call_tool(
            "test_plugin.test_tool",
            {"message": "Hello from test"}
        )

        assert result is not None
        assert "Plugin tool: Hello from test" in str(result)

    async def test_plugin_error_handling(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test error handling in plugin operations."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        # Try to load non-existent plugin
        with pytest.raises(Exception):
            await plugin_manager.load_plugin("non_existent_plugin")

    async def test_plugin_concurrent_execution(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test concurrent plugin tool execution."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        await plugin_manager.load_all()

        # Execute multiple tool calls concurrently
        tasks = [
            plugin_manager.registry.call_tool(
                "test_plugin.test_tool",
                {"message": f"Message {i}"}
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for i, result in enumerate(results):
            assert f"Plugin tool: Message {i}" in str(result)


@pytest.mark.asyncio
class TestPluginManagement:
    """Test plugin management operations."""

    async def test_plugin_unloading(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin unloading."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        # Load plugin
        plugin = await plugin_manager.load_plugin("test_plugin")
        assert plugin is not None

        # Unload plugin
        await plugin_manager.unload_plugin("test_plugin")

        # Plugin should no longer be in active plugins
        assert "test_plugin" not in plugin_manager._plugins

    async def test_plugin_reload(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin reloading."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        # Load plugin
        plugin1 = await plugin_manager.load_plugin("test_plugin")
        plugin1_id = id(plugin1)

        # Reload plugin
        plugin2 = await plugin_manager.reload_plugin("test_plugin")

        # Should be a different instance
        assert plugin2 is not None
        assert id(plugin2) != plugin1_id

    async def test_plugin_status_monitoring(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin status monitoring."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        # Load plugin
        await plugin_manager.load_plugin("test_plugin")

        # Get plugin status
        status = await plugin_manager.get_plugin_status("test_plugin")

        assert status is not None
        assert status["name"] == "test_plugin"
        assert "loaded_at" in status
        assert "state" in status


@pytest.mark.asyncio
class TestPluginSecurity:
    """Test plugin security and isolation."""

    async def test_plugin_permission_checking(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin permission checking."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        await plugin_manager.load_all()

        # Test with unauthorized agent
        with pytest.raises(PermissionError):
            await plugin_manager.registry.call_tool(
                "test_plugin.test_tool",
                {"message": "test"},
                agent_id="unauthorized_agent"
            )

    async def test_plugin_resource_limits(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin resource limits."""
        plugin_manager.plugin_dirs = [temp_plugin_dir]

        await plugin_manager.load_all()

        # Test with large payload (should be limited)
        large_message = "x" * 1000000  # 1MB

        # This should either succeed or fail gracefully
        try:
            result = await plugin_manager.registry.call_tool(
                "test_plugin.test_tool",
                {"message": large_message}
            )
            assert result is not None
        except Exception as e:
            # Should fail gracefully, not crash
            assert "limit" in str(e).lower() or "size" in str(e).lower()


@pytest.mark.asyncio
class TestPluginPerformance:
    """Performance tests for plugin system."""

    async def test_plugin_loading_performance(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin loading performance."""
        import time

        start_time = time.perf_counter()

        await plugin_manager.load_all()

        load_time = time.perf_counter() - start_time

        # Should load within reasonable time
        assert load_time < 5.0  # 5 seconds

        print(f"Plugin loading time: {load_time:.2f}s")

    async def test_plugin_tool_execution_performance(self, plugin_manager: PluginManager, temp_plugin_dir: Path) -> None:
        """Test plugin tool execution performance."""
        import time

        await plugin_manager.load_all()

        num_calls = 100
        start_time = time.perf_counter()

        tasks = [
            plugin_manager.registry.call_tool(
                "test_plugin.test_tool",
                {"message": f"test_{i}"}
            )
            for i in range(num_calls)
        ]

        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time
        throughput = num_calls / duration

        # Should achieve reasonable throughput
        assert throughput > 10.0  # 10 calls per second

        print(f"Plugin tool throughput: {throughput:.2f} calls/s")
