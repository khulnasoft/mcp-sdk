"""Tests for agent base class and specialized types."""

import pytest

from mcp_sdk.agents.base import AgentContext, AgentMessage
from mcp_sdk.agents.registry import AgentRegistry
from mcp_sdk.agents.types import A2AAgent, B2BAgent, B2CAgent
from mcp_sdk.core.exceptions import AgentAlreadyExistsError, AgentNotFoundError

# ------------------------------------------------------------------ #
#  A2A Agent Tests                                                     #
# ------------------------------------------------------------------ #


class TestA2AAgent:
    @pytest.fixture
    async def agent(self) -> A2AAgent:
        a = A2AAgent(name="a2a-test", description="Test A2A Agent")
        await a.start()
        yield a
        await a.stop()

    def test_agent_type(self, agent) -> None:
        assert agent.AGENT_TYPE == "a2a"

    def test_capabilities(self, agent) -> None:
        caps = agent.get_capabilities()
        assert "delegate" in caps
        assert "collaborate" in caps

    @pytest.mark.asyncio
    async def test_handle_message_returns_response(self, agent) -> None:
        msg = AgentMessage(sender_id="user", recipient_id=agent.id, content="hello")
        ctx = AgentContext(user_id="alice")
        response = await agent.process(msg, ctx)
        assert response.success is True
        assert response.agent_id == agent.id

    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, agent) -> None:
        msg = AgentMessage(sender_id="user", recipient_id=agent.id, content="test")
        ctx = AgentContext(user_id="alice")
        response = await agent.process(msg, ctx)
        assert response.execution_time_ms >= 0

    def test_repr(self, agent) -> None:
        r = repr(agent)
        assert "A2AAgent" in r
        assert "a2a-test" in r


# ------------------------------------------------------------------ #
#  B2B Agent Tests                                                     #
# ------------------------------------------------------------------ #


class TestB2BAgent:
    @pytest.fixture
    async def agent(self) -> B2BAgent:
        a = B2BAgent(name="b2b-test", tenant_id="acme-corp")
        await a.start()
        yield a
        await a.stop()

    def test_agent_type(self, agent) -> None:
        assert agent.AGENT_TYPE == "b2b"

    @pytest.mark.asyncio
    async def test_tenant_mismatch_denied(self, agent) -> None:
        msg = AgentMessage(sender_id="user", recipient_id=agent.id, content="data")
        ctx = AgentContext(user_id="alice", tenant_id="OTHER-CORP")
        response = await agent.process(msg, ctx)
        assert response.success is False
        assert "mismatch" in (response.error or "").lower()

    @pytest.mark.asyncio
    async def test_correct_tenant_allowed(self, agent) -> None:
        msg = AgentMessage(sender_id="user", recipient_id=agent.id, content="data")
        ctx = AgentContext(user_id="alice", tenant_id="acme-corp")
        response = await agent.process(msg, ctx)
        assert response.success is True


# ------------------------------------------------------------------ #
#  B2C Agent Tests                                                     #
# ------------------------------------------------------------------ #


class TestB2CAgent:
    @pytest.fixture
    async def agent(self) -> B2CAgent:
        a = B2CAgent(name="b2c-test", persona="friendly bot", channels=["chat", "email"])
        await a.start()
        yield a
        await a.stop()

    def test_capabilities(self, agent) -> None:
        assert "conversational" in agent.get_capabilities()
        assert "personalization" in agent.get_capabilities()

    @pytest.mark.asyncio
    async def test_b2c_response(self, agent) -> None:
        msg = AgentMessage(sender_id="user", recipient_id=agent.id, content="Hi!")
        ctx = AgentContext(user_id="customer-1")
        response = await agent.process(msg, ctx)
        assert response.success is True
        assert "friendly bot" in str(response.data.get("reply", ""))


# ------------------------------------------------------------------ #
#  Agent Registry Tests                                                #
# ------------------------------------------------------------------ #


class TestAgentRegistry:
    @pytest.fixture
    def registry(self) -> AgentRegistry:
        return AgentRegistry()

    @pytest.fixture
    async def populated_registry(self, registry) -> AgentRegistry:
        a1 = A2AAgent(name="agent-1", tags=["nlp", "search"])
        a2 = B2CAgent(name="agent-2", tags=["support"])
        a3 = B2BAgent(name="agent-3", tenant_id="acme")
        await registry.register(a1)
        await registry.register(a2)
        await registry.register(a3)
        return registry

    @pytest.mark.asyncio
    async def test_register_and_get(self, registry) -> None:
        agent = A2AAgent(name="my-agent")
        await registry.register(agent)
        retrieved = registry.get(agent.id)
        assert retrieved.id == agent.id

    @pytest.mark.asyncio
    async def test_get_by_name(self, registry) -> None:
        agent = A2AAgent(name="named-agent")
        await registry.register(agent)
        retrieved = registry.get_by_name("named-agent")
        assert retrieved.name == "named-agent"

    @pytest.mark.asyncio
    async def test_duplicate_registration_raises(self, registry) -> None:
        agent = A2AAgent(name="dup-agent")
        await registry.register(agent)
        with pytest.raises(AgentAlreadyExistsError):
            await registry.register(agent)

    @pytest.mark.asyncio
    async def test_not_found_raises(self, registry) -> None:
        with pytest.raises(AgentNotFoundError):
            registry.get("nonexistent-id")

    @pytest.mark.asyncio
    async def test_find_by_type(self, populated_registry) -> None:
        a2a_agents = populated_registry.find_by_type("a2a")
        assert len(a2a_agents) == 1
        assert a2a_agents[0].name == "agent-1"

    @pytest.mark.asyncio
    async def test_find_by_capability(self, populated_registry) -> None:
        agents = populated_registry.find_by_capability("delegate")
        assert any(a.name == "agent-1" for a in agents)

    @pytest.mark.asyncio
    async def test_find_by_tag(self, populated_registry) -> None:
        agents = populated_registry.find_by_tag("nlp")
        assert len(agents) == 1

    @pytest.mark.asyncio
    async def test_unregister(self, registry) -> None:
        agent = A2AAgent(name="temp-agent")
        await registry.register(agent)
        assert registry.count() == 1
        await registry.unregister(agent.id)
        assert registry.count() == 0
