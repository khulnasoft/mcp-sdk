"""
Tool Registry
=============
Central registry for MCP tools. Supports discovery, schema validation,
and middleware-wrapped invocation.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel

from mcp_sdk.core.exceptions import ToolNotFoundError

logger = structlog.get_logger(__name__)


class ToolDefinition(BaseModel):
    """Metadata and schema for a registered tool."""

    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = {}
    returns_schema: dict[str, Any] = {}
    tags: list[str] = []
    is_async: bool = True
    version: str = "1.0.0"


class ToolRegistry:
    """
    Registry for named, callable tools with automatic schema inference.

    Tools are registered with names and are accessible by agents via
    the MCP protocol. The registry introspects Python type hints to
    generate JSON Schema-compatible descriptions.

    Example::

        registry = ToolRegistry()

        @registry.register("get_weather")
        async def get_weather(city: str, units: str = "metric") -> dict:
            '''Get current weather for a city.'''
            return {"city": city, "temp": 22, "units": units}

        result = await registry.invoke("get_weather", city="London")
    """

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._middleware: list[Callable[..., Any]] = []

    def register(
        self,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
        version: str = "1.0.0",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a function as a named tool."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            schema = self._build_schema(fn)
            definition = ToolDefinition(
                name=name,
                description=description or inspect.getdoc(fn) or "",
                parameters_schema=schema,
                is_async=asyncio.iscoroutinefunction(fn),
                tags=tags or [],
                version=version,
            )
            self._tools[name] = (definition, fn)
            logger.debug("Tool registered", tool=name)
            return fn

        return decorator

    def register_fn(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str = "",
    ) -> None:
        """Register a function as a tool without using as a decorator."""
        tool_name = name or fn.__name__
        self.register(tool_name, description)(fn)

    def use_middleware(self, fn: Callable[..., Any]) -> None:
        """Add invocation middleware (e.g. auth checks, logging)."""
        self._middleware.append(fn)

    async def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke a tool by name, running through middleware."""
        if name not in self._tools:
            raise ToolNotFoundError(name)

        definition, fn = self._tools[name]

        # Run middleware
        for mw in self._middleware:
            kwargs = await mw(name, kwargs) if asyncio.iscoroutinefunction(mw) else mw(name, kwargs)

        logger.debug("Invoking tool", tool=name)
        if asyncio.iscoroutinefunction(fn):
            return await fn(**kwargs)
        return fn(**kwargs)

    def get_definition(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name][0]

    def list_tools(self) -> list[ToolDefinition]:
        return [defn for defn, _ in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    @staticmethod
    def _build_schema(fn: Callable[..., Any]) -> dict[str, Any]:
        """Introspect function signature to produce a JSON Schema-like dict."""
        sig = inspect.signature(fn)
        props: dict[str, Any] = {}
        required: list[str] = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            annotation = param.annotation
            json_type = type_map.get(annotation, "string")
            props[param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "object",
            "properties": props,
            "required": required,
        }

    # ------------------------------------------------------------------ #
    #  Global singleton                                                    #
    # ------------------------------------------------------------------ #

    _global: ToolRegistry | None = None

    @classmethod
    def global_registry(cls) -> ToolRegistry:
        if cls._global is None:
            cls._global = cls()
        return cls._global
