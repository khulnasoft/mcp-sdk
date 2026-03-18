"""
MCP Server
==========
Server-side implementation of MCP protocol.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, Optional

import structlog

from mcp_sdk.server.models import InitializationOptions, ServerHandlers, ServerInfo
from mcp_sdk.types import (
    CallToolResult,
    GetPromptResult,
    JSONRPCMessage,
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


class MCPServer:
    """
    MCP Server implementation.

    Handles all server-side MCP operations including tool, resource,
    and prompt handling.
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        capabilities: ServerCapabilities | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.capabilities = capabilities or ServerCapabilities(
            tools={"listChanged": True},
            resources={"subscribe": True, "listChanged": True},
            prompts={"listChanged": True},
            logging={},
        )
        self._handlers = ServerHandlers()
        self._initialized = False
        self._transport = None

    def set_handlers(self, handlers: ServerHandlers) -> None:
        """Set the handlers for server operations."""
        self._handlers = handlers

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        self._initialized = True

        return {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": self.capabilities.model_dump(exclude_none=True),
            "serverInfo": {"name": self.name, "version": self.version},
        }

    async def _handle_tools_list(self) -> dict[str, Any]:
        """Handle tools/list request."""
        if self._handlers.list_tools:
            tools = await self._handlers.list_tools()
        else:
            tools = []

        return {"tools": tools}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request."""
        if not self._handlers.call_tool:
            raise RuntimeError("Tool handler not set")

        result = await self._handlers.call_tool(params)
        return result

    async def _handle_resources_list(self) -> dict[str, Any]:
        """Handle resources/list request."""
        if self._handlers.list_resources:
            resources = await self._handlers.list_resources()
        else:
            resources = []

        return {"resources": resources}

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/read request."""
        if not self._handlers.read_resource:
            raise RuntimeError("Resource handler not set")

        uri = params.get("uri")
        result = await self._handlers.read_resource(uri)
        return result

    async def _handle_prompts_list(self) -> dict[str, Any]:
        """Handle prompts/list request."""
        if self._handlers.list_prompts:
            prompts = await self._handlers.list_prompts()
        else:
            prompts = []

        return {"prompts": prompts}

    async def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle prompts/get request."""
        if not self._handlers.get_prompt:
            raise RuntimeError("Prompt handler not set")

        name = params.get("name")
        arguments = params.get("arguments")
        result = await self._handlers.get_prompt(name, arguments)
        return result

    async def handle_request(self, message: JSONRPCMessage) -> JSONRPCMessage | None:
        """Handle an incoming JSON-RPC message."""
        method = message.method
        params = message.params or {}

        try:
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list()
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "resources/list":
                result = await self._handle_resources_list()
            elif method == "resources/read":
                result = await self._handle_resources_read(params)
            elif method == "prompts/list":
                result = await self._handle_prompts_list()
            elif method == "prompts/get":
                result = await self._handle_prompts_get(params)
            else:
                result = None

            if message.id is not None:
                return JSONRPCMessage(id=message.id, result=result)
        except Exception as e:
            logger.error("request_error", method=method, error=str(e))
            if message.id is not None:
                return JSONRPCMessage(id=message.id, error={"code": -32603, "message": str(e)})

        return None

    async def run(self, transport=None) -> None:
        """Run the server with the given transport."""
        self._transport = transport

        if hasattr(transport, "on_message"):
            transport.on_message = self.handle_request

        logger.info("server_started", name=self.name, version=self.version)


class Server:
    """Alias for MCPServer for backwards compatibility."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._server = MCPServer(name)
        self._handlers = ServerHandlers()

    def set_handlers(self, handlers: ServerHandlers) -> None:
        self._server.set_handlers(handlers)
        self._handlers = handlers

    def list_tools(self, handler: Callable):
        self._handlers.list_tools = handler
        return handler

    def call_tool(self, handler: Callable):
        self._handlers.call_tool = handler
        return handler

    def list_resources(self, handler: Callable):
        self._handlers.list_resources = handler
        return handler

    def read_resource(self, handler: Callable):
        self._handlers.read_resource = handler
        return handler

    def list_prompts(self, handler: Callable):
        self._handlers.list_prompts = handler
        return handler

    def get_prompt(self, handler: Callable):
        self._handlers.get_prompt = handler
        return handler

    def get_capabilities(self, **kwargs) -> ServerCapabilities:
        return self._server.capabilities

    async def run(self, *args, **kwargs) -> None:
        await self._server.run(*args, **kwargs)
