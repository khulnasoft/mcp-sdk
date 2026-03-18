"""
Plugin Manager for MCP SDK
==========================
Handles discovery, manifest parsing, and lifecycle management for MCP plugins.
"""

from __future__ import annotations

import importlib
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

from mcp_sdk.core.compression import ContextCompressor
from mcp_sdk.core.error_handling import (
    ErrorCollector,
)
from mcp_sdk.core.negotiator import CapabilityNegotiator
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry
from mcp_sdk.core.state import StateManager
from mcp_sdk.core.streaming import StreamManager

if TYPE_CHECKING:
    from mcp_sdk.core.registry import PluginRegistry

logger = structlog.get_logger(__name__)


class PluginManager:
    """
    Manages plugin discovery, loading, and lifecycle.
    
    Features:
    - Plugin discovery from multiple playbooksies
    - Manifest validation and parsing
    - Dependency resolution and ordering
    - Isolated execution environments
    - Error collection and recovery
    """

    def __init__(
        self,
        registry: PluginRegistry,
        plugin_dirs: list[Path] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.registry = registry
        self.plugin_dirs = plugin_dirs or []
        self.config = config or {}

        # Core components
        self.compressor = ContextCompressor()
        self.negotiator = CapabilityNegotiator()
        self.state_manager = StateManager()
        self.stream_manager = StreamManager()

        # Plugin state tracking
        self._plugins: dict[str, MCPPlugin] = {}
        self._manifests: dict[str, dict[str, Any]] = {}
        self._executors: dict[str, Any] = {}
        self._load_order: list[str] = []

        # Error handling
        self.error_collector = ErrorCollector()

        # Add core plugin playbooksy
        core_plugin_dir = Path(__file__).parent.parent / "plugins"
        if core_plugin_dir.exists():
            self.plugin_dirs.append(core_plugin_dir)
            sys.path.insert(0, str(core_plugin_dir))

        # 2. User Plugins
        if self.plugin_dir.exists():
            for path in self.plugin_dir.iterdir():
                if path.is_dir() and (path / "plugin.yaml").exists():
                    discovered.append(path)

        return discovered

    def load_manifest(self, plugin_path: Path) -> dict[str, Any]:
        """Load and parse the 'plugin.yaml' manifest."""
        manifest_path = plugin_path / "plugin.yaml"
        with open(manifest_path) as f:
            return yaml.safe_load(f)

    def validate_permissions(self, name: str, manifest: dict[str, Any]) -> bool:
        """
        Validate plugin permissions.
        Placeholder for real security policy enforcement.
        """
        requested = manifest.get("permissions", [])
        # For now, we just log them. In a real system, we'd check against a whitelist.
        logger.debug("Plugin requested permissions", name=name, permissions=requested)
        return True

    async def load_and_activate_all(self, ctx: Any = None) -> None:
        """Discover, load, and activate all enabled plugins."""
        discovered_paths = self.discover()

        # Phase 1: Load all manifests and check dependencies
        loaded_manifests = {}
        for path in discovered_paths:
            try:
                manifest = self.load_manifest(path)
                name = manifest.get("name")
                if not name:
                    continue

                # Check persistence state
                if not self.state.is_plugin_enabled(name):
                    logger.info("Plugin disabled, skipping charge", name=name)
                    continue

                loaded_manifests[name] = (path, manifest)
            except Exception as e:
                logger.error("Failed to parse manifest", path=path, error=str(e))

        # Phase 2: Activation Order (Simplified Dependency Resolution)
        activated: set[str] = set()
        to_activate = list(loaded_manifests.keys())

        while to_activate:
            progress = False
            for name in list(to_activate):
                path, manifest = loaded_manifests[name]
                deps = manifest.get("depends", [])

                if all(dep in activated for dep in deps):
                    # All dependencies met, activate
                    await self._activate_plugin(name, path, manifest, ctx)
                    activated.add(name)
                    to_activate.remove(name)
                    progress = True

            if not progress and to_activate:
                logger.error(
                    "Circular dependency or missing dependency detected", remaining=to_activate
                )
                break

    async def _activate_plugin(
        self, name: str, path: Path, manifest: dict[str, Any], ctx: Any
    ) -> None:
        """Internal helper to instantiate and activate a single plugin."""

        start_time = time.perf_counter()

        try:
            if not self.validate_permissions(name, manifest):
                logger.error("Permission validation failed", name=name)
                return

            entrypoint = manifest.get("entrypoint", "plugin:Plugin")
            module_name, class_name = entrypoint.split(":")

            full_module_path = f"mcp_sdk.plugins.{path.name}.{module_name}"

            # Use reload if already present (for hot-reloading)
            if full_module_path in sys.modules:
                module = importlib.reload(sys.modules[full_module_path])
            else:
                module = importlib.import_module(full_module_path)

            plugin_class: type[MCPPlugin] = getattr(module, class_name)
            plugin_instance = plugin_class()

            # Setup
            plugin_instance.on_configure(manifest, path=path)
            await plugin_instance.on_activate(ctx)

            # Choose Executor
            from mcp_sdk.core.executor import LocalPluginExecutor, SubprocessPluginExecutor

            isolation = manifest.get("isolation", "local")
            if isolation == "subprocess":
                executor = SubprocessPluginExecutor()
            else:
                executor = LocalPluginExecutor()

            # Proxy tool registration to use executor
            original_register = plugin_instance.register_tools

            def proxied_register_tools(registry: PluginRegistry) -> None:
                original_reg_tool = registry.register_tool

                def wrapped_reg_tool(
                    tool_name: str, func: Callable, metadata: dict[str, Any] | None = None
                ) -> None:
                    meta = (metadata or {}).copy()
                    meta["plugin_name"] = name  # Ensure negotiator knows the owner

                    async def tool_proxy(**kwargs):
                        agent_id = kwargs.pop("_agent_id", "default")
                        if not self.negotiator.can_use_tool(agent_id, tool_name, context=kwargs):
                            raise PermissionError(
                                f"Agent '{agent_id}' is not authorized to use tool '{tool_name}'"
                            )

                        # 2. Execute via Executor
                        base_name = tool_name.split(".")[-1]
                        result = await executor.execute_tool(
                            plugin_instance, base_name, registry=self.registry, **kwargs
                        )

                        if isinstance(result, str):
                            result = self.compressor.compress(result)

                        return result

                    original_reg_tool(tool_name, tool_proxy, meta)

                registry.register_tool = wrapped_reg_tool
                try:
                    original_register(registry)
                finally:
                    registry.register_tool = original_reg_tool

            # Replace the method for this activation
            proxied_register_tools(self.registry)

            # Keep track
            self._plugins[name] = plugin_instance
            self.registry.register_plugin(plugin_instance)
            self._manifests[name] = manifest

            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Plugin loaded and activated",
                name=name,
                version=manifest.get("version"),
                ms=f"{elapsed:.2f}",
            )

        except Exception as e:
            logger.error("Failed to activate plugin", name=name, error=str(e))

    async def reload_plugin(self, name: str, ctx: Any = None) -> bool:
        """Hot-reload a single plugin without restarting the core."""
        if name not in self._plugins:
            logger.error("Cannot reload: plugin not found", name=name)
            return False

        path = None
        # Find the path from discovery (simple approach)
        for p in self.discover():
            manifest = self.load_manifest(p)
            if manifest.get("name") == name:
                path = p
                break

        if not path:
            logger.error("Cannot reload: plugin path not found", name=name)
            return False

        logger.info("Hot-reloading plugin...", name=name)

        # 1. Deactivate old
        try:
            await self._plugins[name].on_deactivate()
        except Exception as e:
            logger.warning("Error during old plugin deactivation", name=name, error=str(e))

        # 2. Unregister from registry
        self.registry.unregister_plugin(name)

        # 3. Clear from sys.modules for deep reload
        plugin_pkg_prefix = f"mcp_sdk.plugins.{path.name}."
        to_del = [
            m
            for m in sys.modules
            if m.startswith(plugin_pkg_prefix) or m == f"mcp_sdk.plugins.{path.name}"
        ]
        for m in to_del:
            del sys.modules[m]
            logger.debug("Cleared module from sys.modules", module=m)

        # 4. Re-activate (this will use importlib.import_module and load fresh)
        await self._activate_plugin(name, path, self._manifests[name], ctx)
        return True

    async def install_plugin(self, source: str) -> bool:
        """
        Shim for installing a plugin.
        If source is a local path, it copies it.
        If source is a URL, it would download (simulated).
        """
        import shutil

        source_path = Path(source)

        if source_path.exists() and source_path.is_dir():
            target_path = self.plugin_dir / source_path.name
            if target_path.exists():
                logger.warning("Plugin already exists, overwriting", name=source_path.name)
                shutil.rmtree(target_path)

            shutil.copytree(source_path, target_path)
            logger.info(
                "Plugin installed from local source", name=source_path.name, target=target_path
            )
            return True
        elif source.startswith("http"):
            # Simulated download
            logger.info("Simulating plugin download...", url=source)
            # In a real implementation, we'd use httpx and zipfile here
            return True
        else:
            logger.error("Invalid plugin source", source=source)
            return False

    async def deactivate_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.on_deactivate()
                logger.info("Plugin deactivated", name=name)
            except Exception as e:
                logger.error("Deactivation failed", name=name, error=str(e))
        self._plugins.clear()
        self.registry.clear_plugins()
