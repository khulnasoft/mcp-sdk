"""
Plugin Executors for MCP SDK
============================
Handles the execution of plugin tools in different environments (Local, Subprocess, etc.)
"""

from __future__ import annotations

import abc
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp_sdk.core.registry import PluginRegistry  # Added this import for PluginRegistry type hint

if TYPE_CHECKING:
    from mcp_sdk.core.plugin import MCPPlugin


class BasePluginExecutor(abc.ABC):
    """Base class for executing plugin tools."""

    @abc.abstractmethod
    async def execute_tool(
        self, plugin: MCPPlugin, tool_name: str, registry: PluginRegistry | None = None, **kwargs
    ) -> Any:
        """Execute a tool on the given plugin."""
        pass


class LocalPluginExecutor(BasePluginExecutor):
    """Executes tools directly in the current process."""

    async def execute_tool(
        self, plugin: MCPPlugin, tool_name: str, registry: PluginRegistry | None = None, **kwargs
    ) -> Any:
        """
        Dynamically discovers the tool function from the plugin instance.
        """
        # CRITICAL: We MUST use a fresh registry here to find the RAW tool function.
        # If we use the provided 'registry' (the master one), we will hit the PROXY
        # and cause infinite recursion.
        from mcp_sdk.core.registry import PluginRegistry

        temp_registry = PluginRegistry()
        plugin.register_tools(temp_registry)

        tool_func = temp_registry.get_tool(f"{plugin.name}.{tool_name}")
        if not tool_func:
            tool_func = temp_registry.get_tool(tool_name)

        if not tool_func:
            raise RuntimeError(f"Tool {tool_name} not found in plugin {plugin.name}")

        import inspect

        if inspect.iscoroutinefunction(tool_func):
            return await tool_func(**kwargs)
        else:
            return tool_func(**kwargs)


class SubprocessPluginExecutor(BasePluginExecutor):
    """Executes tools in a separate subprocess for isolation."""

    def __init__(self, python_path: str | None = None) -> None:
        self.python_path = python_path or sys.executable
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def _get_process(self, plugin: MCPPlugin) -> asyncio.subprocess.Process:
        plugin_id = plugin.name
        if plugin_id in self._processes and self._processes[plugin_id].returncode is None:
            return self._processes[plugin_id]

        import asyncio
        import os

        worker_script = Path(__file__).parent / "worker.py"

        process = await asyncio.create_subprocess_exec(
            self.python_path,
            str(worker_script),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ,
        )
        self._processes[plugin_id] = process
        return process

    async def execute_tool(
        self, plugin: MCPPlugin, tool_name: str, registry: PluginRegistry | None = None, **kwargs
    ) -> Any:
        """
        Sends a request to a persistent worker script.
        """
        process = await self._get_process(plugin)

        request = {
            "plugin_dir": str(plugin.path),
            "entrypoint": plugin.manifest.get("entrypoint", "plugin:Plugin"),
            "tool_name": tool_name,
            "kwargs": kwargs,
            "manifest": plugin.manifest,
        }

        # Send request
        process.stdin.write(json.dumps(request).encode() + b"\n")
        await process.stdin.drain()

        # Read response
        line = await process.stdout.readline()
        if not line:
            # Subprocess might have died, check stderr
            stderr_data = await process.stderr.read()
            raise RuntimeError(f"Subprocess died. Stderr: {stderr_data.decode()}")

        response = json.loads(line.decode().strip())
        if response["status"] == "error":
            raise RuntimeError(f"Plugin tool error: {response['message']}")

        return response["result"]

    async def shutdown(self) -> None:
        """Terminate all workers."""
        for proc in self._processes.values():
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()
