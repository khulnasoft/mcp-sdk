"""
Worker sidecar for isolated plugin execution.
============================================
This script is executed as a subprocess to load and run plugin tools in isolation.
"""

import asyncio
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any


def load_plugin_from_path(plugin_dir: str, entrypoint: str) -> Any:
    """Dynamically load the plugin class from its playbooksy."""
    path = Path(plugin_dir)
    module_name, class_name = entrypoint.split(":")

    # Setup the path so imports within the plugin work
    sys.path.insert(0, str(path.parent))

    # Construct the full module path
    # Expected: mcp_sdk.plugins.<dirname>.<module_name>
    full_module_path = f"mcp_sdk.plugins.{path.name}.{module_name}"

    try:
        module = importlib.import_module(full_module_path)
        return getattr(module, class_name)
    except Exception as e:
        print(f"ERROR: Failed to load plugin: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Persistent Cache for the plugin in this worker session
    plugin_instance = None
    registry = None

    while True:
        try:
            # 1. Read request from stdin (one per line)
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)

            plugin_dir = request["plugin_dir"]
            entrypoint = request["entrypoint"]
            tool_name = request["tool_name"]
            kwargs = request["kwargs"]
            manifest = request.get("manifest", {})

            # 2. Instantiate and Cache
            if plugin_instance is None:
                plugin_class = load_plugin_from_path(plugin_dir, entrypoint)
                plugin_instance = plugin_class()

                # Configure
                if hasattr(plugin_instance, "on_configure"):
                    plugin_instance.on_configure(manifest, path=Path(plugin_dir))

                # Register tools in local registry
                from mcp_sdk.core.registry import PluginRegistry

                registry = PluginRegistry()
                plugin_instance.register_tools(registry)

            # 3. Find and Execute Tool
            tool_func = registry.get_tool(f"{plugin_instance.name}.{tool_name}")
            if not tool_func:
                tool_func = registry.get_tool(tool_name)

            if not tool_func:
                result_blob = {"status": "error", "message": f"Tool {tool_name} not found"}
            else:
                # Execute with redirected stdout
                import contextlib

                with contextlib.redirect_stdout(sys.stderr):
                    if inspect.iscoroutinefunction(tool_func):
                        result = asyncio.run(tool_func(**kwargs))
                    else:
                        result = tool_func(**kwargs)
                result_blob = {"status": "success", "result": result}

            # 4. Send response (one per line)
            sys.stdout.write(json.dumps(result_blob) + "\n")
            sys.stdout.flush()

        except Exception as e:
            sys.stderr.write(f"FATAL in worker loop: {str(e)}\n")
            sys.stdout.write(json.dumps({"status": "error", "message": str(e)}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
