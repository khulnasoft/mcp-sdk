"""Tests for Memory Store."""

import pytest

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.memory.store import InMemoryBackend, MemoryStore


class TestInMemoryBackend:
    @pytest.fixture
    def backend(self):
        return InMemoryBackend()

    @pytest.mark.asyncio
    async def test_set_and_get(self, backend) -> None:
        await backend.set("key1", {"data": 42})
        result = await backend.get("key1")
        assert result == {"data": 42}

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self, backend) -> None:
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, backend) -> None:
        await backend.set("key2", "value")
        await backend.delete("key2")
        assert await backend.get("key2") is None

    @pytest.mark.asyncio
    async def test_append_and_get_list(self, backend) -> None:
        for i in range(5):
            await backend.append_to_list("mylist", i)
        lst = await backend.get_list("mylist", limit=10)
        assert lst == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_list_max_length(self, backend) -> None:
        for i in range(10):
            await backend.append_to_list("bounded", i, max_length=5)
        lst = await backend.get_list("bounded")
        assert len(lst) == 5
        assert lst == [5, 6, 7, 8, 9]

    @pytest.mark.asyncio
    async def test_list_keys_pattern(self, backend) -> None:
        await backend.set("agent:1:state:x", 1)
        await backend.set("agent:2:state:y", 2)
        await backend.set("other:key", 3)
        keys = await backend.list_keys("agent:*")
        assert len(keys) == 2


class TestMemoryStore:
    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_agent_state(self, store) -> None:
        await store.set_agent_state("agent-1", "status", "running")
        result = await store.get_agent_state("agent-1", "status")
        assert result == "running"

    @pytest.mark.asyncio
    async def test_save_and_retrieve_interaction(self, store) -> None:
        msg = AgentMessage(sender_id="user", recipient_id="agent-1", content="hello")
        resp = AgentResponse(data={"reply": "hi"})
        ctx = AgentContext(user_id="alice")
        await store.save_interaction("agent-1", msg, resp, ctx)
        history = await store.get_agent_history("agent-1", limit=10)
        assert len(history) == 1
        assert "message" in history[0]
        assert "response" in history[0]

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, store) -> None:
        await store.set_session("sess-1", {"cart": ["item-a", "item-b"]})
        sess = await store.get_session("sess-1")
        assert sess["cart"] == ["item-a", "item-b"]
        await store.delete_session("sess-1")
        assert await store.get_session("sess-1") is None

    @pytest.mark.asyncio
    async def test_shared_memory(self, store) -> None:
        await store.set_shared("global", "counter", 0)
        val = await store.get_shared("global", "counter")
        assert val == 0

    @pytest.mark.asyncio
    async def test_user_history(self, store) -> None:
        for i in range(3):
            await store.save_user_message("user-1", {"msg": i})
        history = await store.get_user_history("user-1", limit=10)
        assert len(history) == 3
