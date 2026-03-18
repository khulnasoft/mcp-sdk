from mcp_sdk.core import MCPPlugin, PluginRegistry


class Plugin(MCPPlugin):
    """
    GitHub plugin implementation.
    """

    @property
    def name(self) -> str:
        return "github"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def on_activate(self, ctx) -> None:
        print("GitHub plugin activated")

    def register_tools(self, registry: PluginRegistry) -> None:
        """Register MCP tools"""
        from mcp_sdk.plugins.github.tools.create_issue import create_issue

        # In a real implementation, this could be dynamic based on the manifest
        tool_meta = next(
            (t for t in self.manifest.get("tools", []) if t["name"] == "create_issue"), {}
        )

        registry.register_tool(f"{self.name}.create_issue", create_issue, metadata=tool_meta)
