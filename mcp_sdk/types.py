"""
MCP Type Definitions
====================
Core types for Model Context Protocol.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Union

from pydantic import BaseModel, Field


class LoggingLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TextContent(BaseModel):
    type: str = "text"
    text: str


class ImageContent(BaseModel):
    type: str = "image"
    data: str
    mimeType: str


class EmbeddedResource(BaseModel):
    type: str = "resource"
    resource: Resource


Content = Union[TextContent, ImageContent, EmbeddedResource]


class Tool(BaseModel):
    name: str
    description: str | None = None
    inputSchema: dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    uri: str
    name: str | None = None
    description: str | None = None
    mimeType: str | None = None


class PromptMessage(BaseModel):
    role: str
    content: Content


class PromptArgument(BaseModel):
    name: str
    description: str | None = None
    required: bool = False


class Prompt(BaseModel):
    name: str
    description: str | None = None
    arguments: list[PromptArgument] = Field(default_factory=list)


class TextResourceContent(BaseModel):
    uri: str
    mimeType: str | None = None
    text: str | None = None
    blob: str | None = None


class ResourceContent(BaseModel):
    uri: str
    mimeType: str | None = None
    text: str | None = None
    blob: str | None = None


class CallToolResult(BaseModel):
    content: list[Content]
    isError: bool = False


class GetPromptResult(BaseModel):
    messages: list[PromptMessage]
    prompt: Prompt | None = None


class ReadResourceResult(BaseModel):
    contents: list[ResourceContent]


class ListToolsResult(BaseModel):
    tools: list[Tool]


class ListResourcesResult(BaseModel):
    resources: list[Resource]


class ListPromptsResult(BaseModel):
    prompts: list[Prompt]


class ServerCapabilities(BaseModel):
    tools: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    prompts: dict[str, Any] | None = None
    logging: dict[str, Any] | None = None
    sampling: dict[str, Any] | None = None


class InitializeResult(BaseModel):
    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: dict[str, Any]


class JSONRPCMessage(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
