"""
Integration Tests for Agent Lifecycle
=====================================
End-to-end testing of agent lifecycle management.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse, AgentState, BaseAgent
from mcp_sdk.core.config import MCPConfig
from mcp_sdk.memory.store import MemoryStore
from mcp_sdk.rules.engine import RuleEngine
from mcp_sdk.tools.registry import ToolRegistry


class TestAgent(BaseAgent):
    """Test agent implementation for lifecycle testing."""

    AGENT_TYPE = "test_agent"

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.startup_called = False
        self.shutdown_called = False
        self.message_count = 0

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        """Handle incoming messages."""
        self.message_count += 1

        if message.content == "error":
            raise ValueError("Test error")

        return AgentResponse(
            success=True,
            data=f"Processed: {message.content}",
            agent_id=self.id,
            context=context,
            metadata={"message_count": self.message_count}
        )

    def get_capabilities(self) -> list[str]:
        """Return agent capabilities."""
        return ["test_capability", "message_processing"]

    async def on_start(self) -> None:
        """Custom startup logic."""
        self.startup_called = True
        await super().on_start()

    async def on_stop(self) -> None:
        """Custom shutdown logic."""
        self.shutdown_called = True
        await super().on_stop()


@pytest_asyncio.fixture
async def test_agent():
    """Create a test agent instance."""
    config = MCPConfig()
    rule_engine = RuleEngine()
    memory = MemoryStore()
    tools = ToolRegistry()

    agent = TestAgent(
        "test-agent",
        description="Test agent for lifecycle testing",
        config=config,
        rule_engine=rule_engine,
        memory=memory,
        tools=tools,
    )

    yield agent

    # Cleanup
    if agent.is_running:
        await agent.stop()


@pytest.mark.asyncio
class TestAgentLifecycle:
    """Test agent lifecycle management."""

    async def test_agent_initialization(self, test_agent: TestAgent) -> None:
        """Test agent initialization."""
        assert test_agent.name == "test-agent"
        assert test_agent.metadata.agent_type == "test_agent"
        assert test_agent.state == AgentState.INITIALIZING
        assert not test_agent.is_running
        assert not test_agent.startup_called
        assert not test_agent.shutdown_called

    async def test_agent_startup(self, test_agent: TestAgent) -> None:
        """Test agent startup process."""
        await test_agent.start()

        assert test_agent.state == AgentState.READY
        assert test_agent.is_running
        assert test_agent.startup_called
        assert not test_agent.shutdown_called
        assert test_agent.message_count == 0

    async def test_agent_shutdown(self, test_agent: TestAgent) -> None:
        """Test agent shutdown process."""
        await test_agent.start()
        await test_agent.stop()

        assert test_agent.state == AgentState.SHUTDOWN
        assert not test_agent.is_running
        assert test_agent.startup_called
        assert test_agent.shutdown_called

    async def test_agent_restart(self, test_agent: TestAgent) -> None:
        """Test agent restart functionality."""
        await test_agent.start()

        # Process a message
        message = AgentMessage(
            sender_id="user",
            recipient_id=test_agent.id,
            content="test message"
        )
        context = AgentContext()
        await test_agent.handle_message(message, context)

        assert test_agent.message_count == 1

        # Restart agent
        await test_agent.restart()

        assert test_agent.state == AgentState.READY
        assert test_agent.is_running
        # Message count should be preserved during restart
        assert test_agent.message_count == 1

    async def test_agent_message_processing(self, test_agent: TestAgent) -> None:
        """Test agent message processing."""
        await test_agent.start()

        message = AgentMessage(
            sender_id="user",
            recipient_id=test_agent.id,
            content="Hello, agent!"
        )
        context = AgentContext(user_id="test_user")

        response = await test_agent.handle_message(message, context)

        assert response.success is True
        assert response.data == "Processed: Hello, agent!"
        assert response.agent_id == test_agent.id
        assert response.context == context
        assert response.metadata["message_count"] == 1

    async def test_agent_error_handling(self, test_agent: TestAgent) -> None:
        """Test agent error handling."""
        await test_agent.start()

        message = AgentMessage(
            sender_id="user",
            recipient_id=test_agent.id,
            content="error"
        )
        context = AgentContext()

        with pytest.raises(ValueError, match="Test error"):
            await test_agent.handle_message(message, context)

        # Agent should still be running after error
        assert test_agent.is_running
        assert test_agent.state == AgentState.READY

    async def test_agent_concurrent_messages(self, test_agent: TestAgent) -> None:
        """Test handling concurrent messages."""
        await test_agent.start()

        # Send multiple messages concurrently
        messages = [
            AgentMessage(
                sender_id="user",
                recipient_id=test_agent.id,
                content=f"message_{i}"
            )
            for i in range(10)
        ]

        tasks = [
            test_agent.handle_message(msg, AgentContext())
            for msg in messages
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 10
        for i, response in enumerate(responses):
            assert response.success is True
            assert response.data == f"Processed: message_{i}"
            assert response.metadata["message_count"] == i + 1

    async def test_agent_capabilities(self, test_agent: TestAgent) -> None:
        """Test agent capability reporting."""
        capabilities = test_agent.get_capabilities()

        assert isinstance(capabilities, list)
        assert "test_capability" in capabilities
        assert "message_processing" in capabilities

    async def test_agent_state_transitions(self, test_agent: TestAgent) -> None:
        """Test agent state transitions."""
        # Initial state
        assert test_agent.state == AgentState.INITIALIZING

        # Start
        await test_agent.start()
        assert test_agent.state == AgentState.READY

        # Process message (should transition to BUSY during processing)
        message = AgentMessage(
            sender_id="user",
            recipient_id=test_agent.id,
            content="test"
        )

        # Monitor state during processing
        await test_agent.handle_message(message, AgentContext())
        # State should return to READY after processing
        assert test_agent.state == AgentState.READY

        # Stop
        await test_agent.stop()
        assert test_agent.state == AgentState.SHUTDOWN


@pytest.mark.asyncio
class TestAgentIntegration:
    """Test agent integration with other components."""

    async def test_agent_with_rule_engine(self) -> None:
        """Test agent integration with rule engine."""
        rule_engine = RuleEngine()

        # Add a simple rule
        from mcp_sdk.rules.builder import RuleBuilder
        RuleBuilder.add_rule(
            rule_engine,
            id="test_rule",
            name="Test Rule",
            conditions=[],
            actions=[{"action_type": "allow"}],
            priority=100
        )

        agent = TestAgent(
            "rule-test-agent",
            rule_engine=rule_engine
        )

        await agent.start()

        message = AgentMessage(
            sender_id="user",
            recipient_id=agent.id,
            content="test"
        )
        context = AgentContext()

        response = await agent.handle_message(message, context)
        assert response.success is True

        await agent.stop()

    async def test_agent_with_memory_store(self) -> None:
        """Test agent integration with memory store."""
        memory = MemoryStore()
        await memory.initialize()

        agent = TestAgent(
            "memory-test-agent",
            memory=memory
        )

        await agent.start()

        # Store something in memory
        await memory.store("test_key", {"data": "test_value"})

        # Retrieve from memory in agent
        retrieved = await memory.retrieve("test_key")
        assert retrieved["data"] == "test_value"

        await agent.stop()
        await memory.cleanup()

    async def test_agent_with_tool_registry(self) -> None:
        """Test agent integration with tool registry."""
        tools = ToolRegistry()
        await tools.initialize()

        # Register a test tool
        async def test_tool(message: str) -> str:
            return f"Tool processed: {message}"

        tools.register_tool("test_tool", test_tool, {"description": "Test tool"})

        agent = TestAgent(
            "tool-test-agent",
            tools=tools
        )

        await agent.start()

        # Tool should be available
        assert "test_tool" in tools.list_tools()

        await agent.stop()
        await tools.cleanup()


@pytest.mark.asyncio
class TestAgentPerformance:
    """Performance tests for agent lifecycle."""

    async def test_agent_startup_performance(self) -> None:
        """Test agent startup performance."""
        import time

        start_time = time.perf_counter()

        agent = TestAgent("perf-test-agent")
        await agent.start()

        startup_time = time.perf_counter() - start_time

        # Should start within reasonable time
        assert startup_time < 1.0  # 1 second

        await agent.stop()

    async def test_agent_message_throughput(self, test_agent: TestAgent) -> None:
        """Test agent message processing throughput."""
        import time

        await test_agent.start()

        num_messages = 100
        messages = [
            AgentMessage(
                sender_id="user",
                recipient_id=test_agent.id,
                content=f"message_{i}"
            )
            for i in range(num_messages)
        ]

        start_time = time.perf_counter()

        tasks = [
            test_agent.handle_message(msg, AgentContext())
            for msg in messages
        ]

        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time
        throughput = num_messages / duration

        # Should process at least 10 messages per second
        assert throughput > 10.0

        print(f"Processed {num_messages} messages in {duration:.2f}s ({throughput:.2f} msg/s)")

        await test_agent.stop()

    async def test_agent_memory_usage(self, test_agent: TestAgent) -> None:
        """Test agent memory usage during operation."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        await test_agent.start()

        # Process many messages
        for i in range(1000):
            message = AgentMessage(
                sender_id="user",
                recipient_id=test_agent.id,
                content=f"message_{i}"
            )
            await test_agent.handle_message(message, AgentContext())

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024  # 100MB

        print(f"Memory increase: {memory_increase / 1024 / 1024:.2f} MB")

        await test_agent.stop()
