from collections.abc import Callable
from typing import Any


def recommend_tools(registry_ignored=None) -> Callable:
    def _recommend_tools(goal: str) -> list[dict[str, Any]]:
        """Suggest tools based on a goal."""
        from mcp_sdk.core.registry import get_registry

        reg = get_registry()
        recommendations = reg.discover_tools(goal)
        results = []
        for name, score in recommendations:
            meta = reg.get_tool_metadata(name)
            results.append(
                {
                    "name": name,
                    "score": score,
                    "description": meta.get("description"),
                    "tags": meta.get("tags"),
                }
            )
        return results[:5]  # Top 5 recommendations

    return _recommend_tools


def list_capabilities(registry_ignored=None) -> Callable:
    def _list_capabilities() -> dict[str, Any]:
        """List all active plugins and their tools."""
        from mcp_sdk.core.registry import get_registry

        reg = get_registry()
        plugins = {}
        for name in list(reg._plugins.keys()):
            tools = [t for t in reg._tools if t.startswith(f"{name}.")]
            p_instance = reg.get_plugin(name)
            meta = p_instance.manifest if p_instance else {}
            plugins[name] = {
                "version": meta.get("version"),
                "description": meta.get("description"),
                "tools": tools,
            }
        return {"plugins": plugins}

    return _list_capabilities
