"""
MCP Server Models
=================
Server-side models and initialization options.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from mcp_sdk.types import ServerCapabilities


class ServerInfo(BaseModel):
    name: str
    version: str


class InitializationOptions(BaseModel):
    """Options for initializing an MCP server."""

    server_info: ServerInfo
    capabilities: ServerCapabilities
    client_info: dict[str, Any] | None = None

    class Config:
        extra = "allow"


class RequestContext(BaseModel):
    """Context for incoming requests."""

    request_id: str | None = None
    method: str
    params: dict[str, Any] | None = None


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
ResourceHandler = Callable[[str], Awaitable[dict[str, Any]]]
PromptHandler = Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]


class ServerHandlers(BaseModel):
    """Handlers for server operations."""

    list_tools: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
    call_tool: ToolHandler | None = None
    list_resources: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
    read_resource: ResourceHandler | None = None
    list_prompts: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
    get_prompt: PromptHandler | None = None
