"""
MCP Client Session
==================
Client-side session for communicating with MCP servers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import structlog

from mcp_sdk.types import (
    CallToolResult,
    GetPromptResult,
    InitializeResult,
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


class MCPClientSession:
    """
    Client session for MCP protocol communication.

    Handles initialization and all client-side MCP operations.
    """

    def __init__(
        self, transport: Any = None, on_message: Callable[[JSONRPCMessage], None] | None = None
    ) -> None:
        self.transport = transport
        self.on_message = on_message
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._initialized = False
        self._server_capabilities: ServerCapabilities | None = None
        self._server_info: dict[str, Any] = {}

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = self._next_id()
        message = JSONRPCMessage(id=request_id, method=method, params=params)

        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            await self._send_message(message)
            result = await future
            return result
        finally:
            self._pending_requests.pop(request_id, None)

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        message = JSONRPCMessage(method=method, params=params)
        await self._send_message(message)

    async def _send_message(self, message: JSONRPCMessage) -> None:
        if self.transport:
            await self.transport.send(message.model_dump_json())
        logger.debug("sent_message", method=message.method, id=message.id)

    async def _handle_message(self, message: JSONRPCMessage) -> None:
        if message.id is not None and message.id in self._pending_requests:
            future = self._pending_requests[message.id]
            if message.error:
                future.set_exception(Exception(message.error))
            else:
                future.set_result(message.result)
        elif self.on_message:
            self.on_message(message)

    async def initialize(
        self, client_info: dict[str, Any], protocol_version: str = "2024-11-05"
    ) -> InitializeResult:
        """Initialize the session with the server."""
        result = await self._send_request(
            "initialize",
            {"protocolVersion": protocol_version, "clientInfo": client_info, "capabilities": {}},
        )

        self._server_capabilities = ServerCapabilities(**result.get("capabilities", {}))
        self._server_info = result.get("serverInfo", {})
        self._initialized = True

        await self._send_notification("initialized", {})

        return InitializeResult(
            protocolVersion=result.get("protocolVersion", protocol_version),
            capabilities=self._server_capabilities,
            serverInfo=self._server_info,
        )

    async def list_tools(self) -> ListToolsResult:
        """List available tools on the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request("tools/list")
        return ListToolsResult(tools=[Tool(**t) for t in result.get("tools", [])])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Call a tool on the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )

        content = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                content.append(TextContent(**item))
            else:
                content.append(item)

        return CallToolResult(content=content, isError=result.get("isError", False))

    async def list_resources(self) -> ListResourcesResult:
        """List available resources on the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request("resources/list")
        return ListResourcesResult(resources=[Resource(**r) for r in result.get("resources", [])])

    async def read_resource(self, uri: str) -> ReadResourceResult:
        """Read a resource from the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request("resources/read", {"uri": uri})

        contents = []
        for item in result.get("contents", []):
            contents.append(ResourceContent(**item))

        return ReadResourceResult(contents=contents)

    async def list_prompts(self) -> ListPromptsResult:
        """List available prompts on the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request("prompts/list")
        return ListPromptsResult(prompts=[Prompt(**p) for p in result.get("prompts", [])])

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> GetPromptResult:
        """Get a prompt from the server."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        result = await self._send_request(
            "prompts/get", {"name": name, "arguments": arguments or {}}
        )

        messages = []
        for msg in result.get("messages", []):
            messages.append(PromptMessage(**msg))

        return GetPromptResult(
            messages=messages, prompt=Prompt(**result["prompt"]) if "prompt" in result else None
        )

    async def close(self) -> None:
        """Close the session."""
        for future in self._pending_requests.values():
            future.cancel()
        self._pending_requests.clear()
        self._initialized = False

        if self.transport and hasattr(self.transport, "close"):
            await self.transport.close()


class ClientSession:
    """Alias for MCPClientSession for backwards compatibility."""

    def __init__(self, transport=None, on_message=None) -> None:
        self._session = MCPClientSession(transport, on_message)

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def initialize(self, client_info, protocol_version="2024-11-05"):
        return await self._session.initialize(client_info, protocol_version)

    async def list_tools(self):
        return await self._session.list_tools()

    async def call_tool(self, name, arguments=None):
        return await self._session.call_tool(name, arguments)

    async def list_resources(self):
        return await self._session.list_resources()

    async def read_resource(self, uri):
        return await self._session.read_resource(uri)

    async def list_prompts(self):
        return await self._session.list_prompts()

    async def get_prompt(self, name, arguments=None):
        return await self._session.get_prompt(name, arguments)

    async def close(self) -> None:
        await self._session.close()
