"""
MCP Core Protocol Layer
========================
Implements the Model Context Protocol server/client foundation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel

from mcp_sdk.core.config import MCPConfig
from mcp_sdk.core.error_handling import handle_errors
from mcp_sdk.core.exceptions import MCPProtocolError
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry
from mcp_sdk.core.retry import RetryConfig, retry_async
from mcp_sdk.server import Server
from mcp_sdk.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    PromptMessage,
    ReadResourceResult,
    Resource,
    ResourceContent,
    ServerCapabilities,
    TextContent,
    Tool,
)

logger = structlog.get_logger(__name__)


class ServerCapabilities(BaseModel):
    """Describes what this MCP server supports."""

    tools: bool = True
    resources: bool = True
    prompts: bool = True
    logging: bool = True
    sampling: bool = False


class MCPProtocol:
    """
    Core MCP Protocol handler.

    Wraps the MCP Server with higher-level abstractions for tool, resource,
    and prompt registration while adding observability and error handling.

    Example::

        protocol = MCPProtocol(name="my-agent", version="1.0.0")

        @protocol.tool("search_web")
        async def search(query: str) -> str:
            return f"Results for: {query}"

        await protocol.serve()
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        config: MCPConfig | None = None,
        capabilities: ServerCapabilities | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.config = config or MCPConfig()
        self.capabilities = capabilities or ServerCapabilities()
        self._server = Server(name)
        self.registry = PluginRegistry()
        self.plugins = PluginManager(self.registry)
        self._tools: dict[str, Callable[..., Any]] = {}
        self._resources: dict[str, Callable[..., Any]] = {}
        self._prompts: dict[str, Callable[..., Any]] = {}
        self._middleware: list[Callable[..., Any]] = []
        self._on_startup: list[Callable[[], Any]] = []
        self._on_shutdown: list[Callable[[], Any]] = []
        self._register_handlers()
        logger.info("MCPProtocol initialized", name=name, version=version)

    # ------------------------------------------------------------------ #
    #  Decorators                                                          #
    # ------------------------------------------------------------------ #

    def tool(
        self,
        name: str,
        description: str = "",
        schema: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a callable as an MCP tool."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name] = fn
            logger.debug("Tool registered", tool=name)
            return fn

        return decorator

    def resource(
        self,
        uri_pattern: str,
        name: str = "",
        description: str = "",
        mime_type: str = "application/json",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a callable as an MCP resource provider."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._resources[uri_pattern] = fn
            logger.debug("Resource registered", uri=uri_pattern)
            return fn

        return decorator

    def prompt(
        self,
        name: str,
        description: str = "",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a callable as an MCP prompt template."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._prompts[name] = fn
            logger.debug("Prompt registered", prompt=name)
            return fn

        return decorator

    def on_startup(self, fn: Callable[[], Any]) -> Callable[[], Any]:
        """Register a startup hook."""
        self._on_startup.append(fn)
        return fn

    def on_shutdown(self, fn: Callable[[], Any]) -> Callable[[], Any]:
        """Register a shutdown hook."""
        self._on_shutdown.append(fn)
        return fn

    def use_middleware(self, fn: Callable[..., Any]) -> None:
        """Add middleware to the request pipeline."""
        self._middleware.append(fn)

    async def load_plugin(self, plugin_class: type[MCPPlugin]) -> MCPPlugin:
        """Load a plugin into the protocol (legacy wrapper)."""
        # This is now handled more robustly by PluginManager,
        # but kept for backward compatibility if needed.
        plugin = plugin_class()
        await plugin.on_activate(self)
        plugin.register_tools(self.registry)
        return plugin

    # ------------------------------------------------------------------ #
    #  Internal MCP handler wiring                                         #
    # ------------------------------------------------------------------ #

    def _register_handlers(self) -> None:
        """Wire MCP server handlers to internal registries."""

        @self._server.list_tools()
        @handle_errors("LIST_TOOLS_ERROR")
        async def _list_tools() -> ListToolsResult:
            tools = []
            # Add registered tools
            for k, v in self._tools.items():
                tools.append(Tool(
                    name=k,
                    description=getattr(v, "__doc__", "") or "",
                    inputSchema=getattr(v, "__schema__", {})
                ))
            # Add plugin tools
            for tool_name, tool_info in self.registry.list_tools().items():
                tools.append(Tool(
                    name=tool_name,
                    description=tool_info.get("description", ""),
                    inputSchema=tool_info.get("inputSchema", {})
                ))
            return ListToolsResult(tools=tools)

        @self._server.call_tool()
        @handle_errors("CALL_TOOL_ERROR")
        async def _call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
            # Try local tools first
            if name in self._tools:
                try:
                    result = await self._invoke(self._tools[name], **arguments)
                    return CallToolResult(content=[TextContent(type="text", text=str(result))])
                except Exception as exc:
                    logger.error("Local tool execution failed", tool=name, error=str(exc))
                    raise MCPProtocolError(f"Tool '{name}' execution failed: {str(exc)}")

            # Try plugin tools
            try:
                result = await retry_async(
                    self.registry.call_tool,
                    name,
                    arguments,
                    config=RetryConfig(max_attempts=3)
                )
                return result
            except Exception as exc:
                logger.error("Plugin tool execution failed", tool=name, error=str(exc))
                raise MCPProtocolError(f"Tool '{name}' not found or execution failed")

        @self._server.list_resources()
        @handle_errors("LIST_RESOURCES_ERROR")
        async def _list_resources() -> ListResourcesResult:
            resources = []
            # Add registered resources
            for k, v in self._resources.items():
                resources.append(Resource(
                    uri=k,
                    name=k,
                    description=getattr(v, "__doc__", "") or "",
                    mimeType="application/json"
                ))
            return ListResourcesResult(resources=resources)

        @self._server.read_resource()
        @handle_errors("READ_RESOURCE_ERROR")
        async def _read_resource(uri: str) -> ReadResourceResult:
            # Try local resources first
            for pattern, fn in self._resources.items():
                if uri.startswith(pattern.rstrip("*")):
                    try:
                        result = await self._invoke(fn, uri=uri)
                        return ReadResourceResult(contents=[
                            ResourceContent(
                                uri=uri,
                                mimeType="text/plain",
                                text=str(result)
                            )
                        ])
                    except Exception as exc:
                        logger.error("Local resource read failed", uri=uri, error=str(exc))
                        raise MCPProtocolError(f"Failed to read resource '{uri}': {str(exc)}")

            # Try plugin resources
            try:
                result = await retry_async(
                    self.registry.read_resource,
                    uri,
                    config=RetryConfig(max_attempts=3)
                )
                return result
            except Exception as exc:
                logger.error("Plugin resource read failed", uri=uri, error=str(exc))
                raise MCPProtocolError(f"Resource '{uri}' not found or read failed")

        @self._server.list_prompts()
        @handle_errors("LIST_PROMPTS_ERROR")
        async def _list_prompts() -> ListPromptsResult:
            prompts = []
            # Add registered prompts
            for k, v in self._prompts.items():
                prompts.append(Prompt(
                    name=k,
                    description=getattr(v, "__doc__", "") or ""
                ))
            return ListPromptsResult(prompts=prompts)

        @self._server.get_prompt()
        async def _get_prompt(
            name: str, arguments: dict[str, str] | None = None
        ) -> GetPromptResult:
            if name not in self._prompts:
                raise MCPProtocolError(f"Prompt '{name}' not found")
            result = await self._invoke(self._prompts[name], **(arguments or {}))

            return GetPromptResult(
                messages=[
                    PromptMessage(role="user", content=TextContent(type="text", text=str(result)))
                ],
            )

    async def _invoke(self, fn: Callable[..., Any], **kwargs: Any) -> Any:
        """Invoke a handler through middleware chain."""
        for mw in self._middleware:
            kwargs = await mw(kwargs) if asyncio.iscoroutinefunction(mw) else mw(kwargs)
        if asyncio.iscoroutinefunction(fn):
            return await fn(**kwargs)
        return fn(**kwargs)

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def startup(self) -> None:
        """Run all startup hooks and plugin setups."""
        await self.plugins.load_and_activate_all(ctx=self)
        for hook in self._on_startup:
            if asyncio.iscoroutinefunction(hook):
                await hook()
            else:
                hook()

    async def shutdown(self) -> None:
        """Run all shutdown hooks and plugin teardowns."""
        await self.plugins.deactivate_all()
        for hook in self._on_shutdown:
            if asyncio.iscoroutinefunction(hook):
                await hook()
            else:
                hook()

    async def serve_stdio(self) -> None:
        """Serve over stdio (default MCP transport)."""
        import json
        import sys

        from mcp_sdk.types import JSONRPCMessage

        logger.info("Starting MCP server (stdio)", name=self.name)
        await self.startup()

        try:
            for line in sys.stdin:
                if line.strip():
                    try:
                        data = json.loads(line)
                        message = JSONRPCMessage(**data)
                        response = await self._server.handle_request(message)
                        if response:
                            print(response.model_dump_json(), flush=True)
                    except Exception as e:
                        error_msg = JSONRPCMessage(
                            id=None, error={"code": -32700, "message": str(e)}
                        )
                        print(error_msg.model_dump_json(), flush=True)
        finally:
            await self.shutdown()

    async def serve_http(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Serve over HTTP/SSE transport for web-based MCP clients."""
        import uvicorn

        from mcp_sdk.transport.http import create_http_app

        app = create_http_app(self._server, self.name)
        await self.startup()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        try:
            await server.serve()
        finally:
            await self.shutdown()
