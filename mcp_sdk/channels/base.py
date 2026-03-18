"""
Channel Implementations
========================
A2A, A2B, B2B, B2C channel definitions and base class.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.core.exceptions import ChannelError

logger = structlog.get_logger(__name__)


class BaseChannel(ABC):
    """Abstract base for all communication channels."""

    CHANNEL_NAME: str = "base"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._handlers: list[Any] = []
        self._log = logger.bind(channel=self.CHANNEL_NAME)

    @abstractmethod
    async def send(self, message: AgentMessage, context: AgentContext) -> AgentResponse: ...

    @abstractmethod
    async def receive(self) -> AgentMessage | None: ...

    def on_message(self, handler: Any) -> None:
        """Register a message handler callback."""
        self._handlers.append(handler)

    async def _dispatch(self, message: AgentMessage, context: AgentContext) -> None:
        for handler in self._handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler(message, context)
            else:
                handler(message, context)


class A2AChannel(BaseChannel):
    """
    Agent-to-Agent channel.
    Direct, low-latency messaging between agents within the same platform.
    Backed by an in-process asyncio Queue for local delivery.
    """

    CHANNEL_NAME = "a2a"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._queue: asyncio.Queue[AgentMessage] = asyncio.Queue(maxsize=1000)
        self._registry_ref: Any = None

    def bind_registry(self, registry: Any) -> None:
        """Bind an AgentRegistry for direct dispatch."""
        self._registry_ref = registry

    async def send(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        """Send a message to a specific agent by recipient_id."""
        if self._registry_ref:
            try:
                target = self._registry_ref.get(message.recipient_id)
                self._log.debug("Dispatching A2A", to=message.recipient_id)
                return await target.process(message, context)
            except Exception as exc:
                raise ChannelError("a2a", str(exc)) from exc
        # Fallback: queue-based
        await self._queue.put(message)
        return AgentResponse(data={"queued": True})

    async def receive(self) -> AgentMessage | None:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def receive_blocking(self, timeout: float = 5.0) -> AgentMessage | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None


class A2BChannel(BaseChannel):
    """
    Agent-to-Business channel.
    Translates agent messages into business API calls via HTTP.
    """

    CHANNEL_NAME = "a2b"

    def __init__(
        self,
        base_url: str = "",
        auth_token: str = "",
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config)
        self.base_url = base_url
        self.auth_token = auth_token

    async def send(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        """Forward message content to a business API endpoint."""
        import httpx

        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/messages",
                    json={"content": message.content, "session_id": context.session_id},
                    headers=headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
                return AgentResponse(data=resp.json())
        except Exception as exc:
            raise ChannelError("a2b", str(exc)) from exc

    async def receive(self) -> AgentMessage | None:
        """Poll business API for incoming messages (webhook alternative)."""
        return None


class B2BChannel(BaseChannel):
    """
    Business-to-Business channel.
    Supports async, multi-tenant message exchange between organizations.
    """

    CHANNEL_NAME = "b2b"

    def __init__(
        self,
        tenant_id: str = "",
        partner_endpoint: str = "",
        api_key: str = "",
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config)
        self.tenant_id = tenant_id
        self.partner_endpoint = partner_endpoint
        self.api_key = api_key

    async def send(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        import httpx

        headers = {
            "X-API-Key": self.api_key,
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }
        payload = {
            "sender": message.sender_id,
            "recipient": message.recipient_id,
            "content": message.content,
            "tenant_id": self.tenant_id,
            "correlation_id": context.correlation_id,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.partner_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=60.0,
                )
                resp.raise_for_status()
                return AgentResponse(data=resp.json())
        except Exception as exc:
            raise ChannelError("b2b", str(exc)) from exc

    async def receive(self) -> AgentMessage | None:
        return None


class B2CChannel(BaseChannel):
    """
    Business-to-Customer channel.
    Delivers messages to end-users via multiple channels (WebSocket, SMS, email).
    """

    CHANNEL_NAME = "b2c"

    def __init__(
        self,
        delivery_mode: str = "websocket",
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config)
        self.delivery_mode = delivery_mode
        self._ws_connections: dict[str, Any] = {}  # user_id -> websocket

    def register_websocket(self, user_id: str, ws: Any) -> None:
        """Register a WebSocket connection for a user."""
        self._ws_connections[user_id] = ws
        self._log.info("WebSocket registered", user_id=user_id)

    def unregister_websocket(self, user_id: str) -> None:
        self._ws_connections.pop(user_id, None)

    async def send(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        user_id = context.user_id or message.recipient_id

        if self.delivery_mode == "websocket":
            ws = self._ws_connections.get(user_id)
            if ws:
                try:
                    import json as _json

                    await ws.send(
                        _json.dumps({"content": str(message.content), "from": message.sender_id})
                    )
                    return AgentResponse(data={"delivered": True, "mode": "websocket"})
                except Exception as exc:
                    raise ChannelError("b2c", f"WebSocket send failed: {exc}") from exc
            else:
                self._log.warning("No WebSocket connection for user", user_id=user_id)
                return AgentResponse(data={"delivered": False, "reason": "no_connection"})

        return AgentResponse(data={"delivered": False, "mode": self.delivery_mode})

    async def receive(self) -> AgentMessage | None:
        return None
