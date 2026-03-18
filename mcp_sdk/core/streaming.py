from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any


class StreamingMCPTool:
    """
    Wraps a generator or async generator to allow partial results and progress updates.
    """

    def __init__(self, func: Callable, metadata: dict[str, Any]) -> None:
        self.func = func
        self.metadata = metadata

    async def run_async(self, **kwargs) -> AsyncGenerator[Any, None]:
        """Execute the tool and yield partial results asynchronously."""
        result = self.func(**kwargs)

        if hasattr(result, "__aiter__"):
            async for partial in result:
                yield partial
        elif hasattr(result, "__iter__"):
            for partial in result:
                yield partial
                await asyncio.sleep(0)  # Allow context switching
        else:
            yield result


class StreamManager:
    """
    Handles subscriptions and dispatching of partial tool results to agents.
    """

    def __init__(self) -> None:
        self.active_streams: dict[str, list[Callable]] = {}

    def subscribe(self, tool_name: str, callback: Callable[[Any], None]) -> None:
        """Register a callback for partial results of a specific tool."""
        if tool_name not in self.active_streams:
            self.active_streams[tool_name] = []
        self.active_streams[tool_name].append(callback)

    def push(self, tool_name: str, data: Any) -> None:
        """Dispatch partial result to all subscribers."""
        if tool_name in self.active_streams:
            for callback in self.active_streams[tool_name]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Error in stream callback for {tool_name}: {e}")

    def unsubscribe(self, tool_name: str, callback: Callable) -> None:
        if tool_name in self.active_streams:
            self.active_streams[tool_name].remove(callback)
