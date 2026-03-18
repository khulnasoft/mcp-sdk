"""
Memory Store
=============
Pluggable memory backend for agents. Supports in-memory, Redis, and SQL backends.
Stores interaction history, user preferences, and agent state.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog

from mcp_sdk.memory.scaffold import ScaffoldManager

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------ #
#  Abstract Backend                                                    #
# ------------------------------------------------------------------ #


class MemoryBackend(ABC):
    """Abstract interface for memory storage backends."""

    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def list_keys(self, pattern: str = "*") -> list[str]: ...

    @abstractmethod
    async def append_to_list(self, key: str, value: Any, max_length: int | None = None) -> None: ...

    @abstractmethod
    async def get_list(self, key: str, limit: int = 100) -> list[Any]: ...


class InMemoryBackend(MemoryBackend):
    """
    In-process dict-based backend.
    Suitable for development and testing.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._lists: dict[str, list[Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        async with self._lock:
            self._store[key] = value

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)
            self._lists.pop(key, None)

    async def list_keys(self, pattern: str = "*") -> list[str]:
        import fnmatch

        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    async def append_to_list(self, key: str, value: Any, max_length: int | None = None) -> None:
        async with self._lock:
            lst = self._lists.setdefault(key, [])
            lst.append(value)
            if max_length and len(lst) > max_length:
                self._lists[key] = lst[-max_length:]

    async def get_list(self, key: str, limit: int = 100) -> list[Any]:
        lst = self._lists.get(key, [])
        return lst[-limit:]


class RedisMemoryBackend(MemoryBackend):
    """Redis-backed memory store for production multi-agent setups."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._url = url
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis  # type: ignore

            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        val = await client.get(key)
        return json.loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = await self._get_client()
        encoded = json.dumps(value)
        if ttl:
            await client.setex(key, ttl, encoded)
        else:
            await client.set(key, encoded)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def list_keys(self, pattern: str = "*") -> list[str]:
        client = await self._get_client()
        return await client.keys(pattern)

    async def append_to_list(self, key: str, value: Any, max_length: int | None = None) -> None:
        client = await self._get_client()
        await client.rpush(key, json.dumps(value))
        if max_length:
            await client.ltrim(key, -max_length, -1)

    async def get_list(self, key: str, limit: int = 100) -> list[Any]:
        client = await self._get_client()
        raw_items = await client.lrange(key, -limit, -1)
        return [json.loads(item) for item in raw_items]


# ------------------------------------------------------------------ #
#  Higher-level MemoryStore                                            #
# ------------------------------------------------------------------ #


class MemoryStore:
    """
    High-level memory store for agent interactions, sessions, and state.

    Provides:
    - Interaction history per agent
    - User session data
    - Agent working memory (key-value)
    - Cross-agent shared memory

    Example::

        store = MemoryStore()

        await store.set_agent_state("agent-1", "task", {"status": "running"})
        state = await store.get_agent_state("agent-1", "task")

        await store.save_interaction(agent_id, message, response, context)
        history = await store.get_agent_history("agent-1", limit=20)
    """

    def __init__(self, backend: MemoryBackend | None = None) -> None:
        self._backend = backend or InMemoryBackend()
        self._scaffolds: dict[str, ScaffoldManager] = {}

    def get_scaffold(self, agent_id: str) -> ScaffoldManager:
        """Get or create a ScaffoldManager for an agent."""
        if agent_id not in self._scaffolds:
            self._scaffolds[agent_id] = ScaffoldManager(context_id=agent_id)
        return self._scaffolds[agent_id]

    # ------------------------------------------------------------------ #
    #  Agent State                                                         #
    # ------------------------------------------------------------------ #

    async def set_agent_state(
        self, agent_id: str, key: str, value: Any, ttl: int | None = None
    ) -> None:
        await self._backend.set(f"agent:{agent_id}:state:{key}", value, ttl=ttl)

    async def get_agent_state(self, agent_id: str, key: str) -> Any:
        return await self._backend.get(f"agent:{agent_id}:state:{key}")

    async def delete_agent_state(self, agent_id: str, key: str) -> None:
        await self._backend.delete(f"agent:{agent_id}:state:{key}")

    # ------------------------------------------------------------------ #
    #  Interaction History                                                 #
    # ------------------------------------------------------------------ #

    async def save_interaction(
        self,
        agent_id: str,
        message: Any,
        response: Any,
        context: Any,
    ) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "message": message.model_dump() if hasattr(message, "model_dump") else str(message),
            "response": response.model_dump() if hasattr(response, "model_dump") else str(response),
            "context": context.model_dump() if hasattr(context, "model_dump") else str(context),
        }
        await self._backend.append_to_list(f"agent:{agent_id}:history", record, max_length=1000)

    async def get_agent_history(self, agent_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend.get_list(f"agent:{agent_id}:history", limit=limit)

    # ------------------------------------------------------------------ #
    #  User History                                                        #
    # ------------------------------------------------------------------ #

    async def save_user_message(self, user_id: str, record: dict[str, Any]) -> None:
        await self._backend.append_to_list(f"user:{user_id}:history", record, max_length=500)

    async def get_user_history(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return await self._backend.get_list(f"user:{user_id}:history", limit=limit)

    # ------------------------------------------------------------------ #
    #  Session                                                             #
    # ------------------------------------------------------------------ #

    async def set_session(self, session_id: str, data: dict[str, Any], ttl: int = 3600) -> None:
        await self._backend.set(f"session:{session_id}", data, ttl=ttl)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._backend.get(f"session:{session_id}")

    async def delete_session(self, session_id: str) -> None:
        await self._backend.delete(f"session:{session_id}")

    # ------------------------------------------------------------------ #
    #  Shared / Cross-agent Memory                                         #
    # ------------------------------------------------------------------ #

    async def set_shared(self, namespace: str, key: str, value: Any) -> None:
        await self._backend.set(f"shared:{namespace}:{key}", value)

    async def get_shared(self, namespace: str, key: str) -> Any:
        return await self._backend.get(f"shared:{namespace}:{key}")
