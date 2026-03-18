"""
BaseAgent — Abstract Agent Foundation
======================================
All agent types (A2A, A2B, B2B, B2C) inherit from this base class.
Provides lifecycle management, tool binding, rule enforcement, and MCP integration.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

import structlog
from pydantic import BaseModel, Field

from mcp_sdk.core.config import MCPConfig
from mcp_sdk.core.error_handling import (
    error_context,
    handle_errors,
)
from mcp_sdk.memory.store import MemoryStore
from mcp_sdk.rules.engine import RuleEngine
from mcp_sdk.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class AgentState(StrEnum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


class AgentMetadata(BaseModel):
    """Metadata describing an agent instance."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    version: str = "1.0.0"
    agent_type: str = "base"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    max_concurrent_tasks: int = 10
    timeout_seconds: int = 300
    state: AgentState = AgentState.INITIALIZING


class AgentContext(BaseModel):
    """Runtime context passed to agent methods."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    tenant_id: str | None = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)
    channel: str = "default"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentMessage(BaseModel):
    """A message exchanged between agents or between agent and user."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    recipient_id: str
    content: Any
    message_type: str = "text"
    context: AgentContext = Field(default_factory=AgentContext)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reply_to: str | None = None


class AgentResponse(BaseModel):
    """Standard response structure from an agent."""

    success: bool = True
    data: Any = None
    error: str | None = None
    agent_id: str = ""
    context: AgentContext | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all MCP agents.

    Provides:
    - Lifecycle management (startup/shutdown)
    - Rule engine integration
    - Memory store access
    - Tool registry binding
    - Message handling interface

    Subclass and implement :meth:`handle_message` and :meth:`get_capabilities`.

    Example::

        class MyAgent(BaseAgent):
            AGENT_TYPE = "my_agent"

            async def handle_message(self, message, context):
                return AgentResponse(data=f"Hello from {self.metadata.name}")

            def get_capabilities(self):
                return ["greeting", "farewell"]
    """

    AGENT_TYPE: ClassVar[str] = "base"

    def __init__(
        self,
        name: str,
        description: str = "",
        config: MCPConfig | None = None,
        rule_engine: RuleEngine | None = None,
        memory: MemoryStore | None = None,
        tools: ToolRegistry | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.metadata = AgentMetadata(
            name=name,
            description=description,
            agent_type=self.AGENT_TYPE,
            tags=tags or [],
        )
        self.config = config or MCPConfig()
        self.rule_engine = rule_engine or RuleEngine()
        self.memory = memory or MemoryStore()
        self.tools = tools or ToolRegistry()
        self._running = False
        self._task_semaphore = asyncio.Semaphore(self.metadata.max_concurrent_tasks)
        self._log = logger.bind(agent_id=self.metadata.id, agent_name=name)

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def name(self) -> str:
        return self.metadata.name

    # ------------------------------------------------------------------ #
    #  Abstract interface                                                   #
    # ------------------------------------------------------------------ #

    @abstractmethod
    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        """Handle an incoming message and return a response."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the list of capability strings this agent supports."""
        ...

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    @handle_errors("AGENT_START_ERROR")
    async def start(self) -> None:
        """Start the agent with proper lifecycle management."""
        async with error_context("agent_start", {"agent_id": self.metadata.id}):
            self._set_state(AgentState.INITIALIZING)

            # Initialize components
            await self._initialize_components()

            # Call custom startup logic
            await self.on_start()

            self._running = True
            self._set_state(AgentState.READY)

            self._log.info("Agent started successfully",
                          agent_type=self.AGENT_TYPE,
                          capabilities=self.get_capabilities())

    @handle_errors("AGENT_STOP_ERROR")
    async def stop(self) -> None:
        """Gracefully stop the agent."""
        async with error_context("agent_stop", {"agent_id": self.metadata.id}):
            self._set_state(AgentState.SHUTTING_DOWN)
            self._running = False

            # Call custom shutdown logic
            await self.on_stop()

            # Cleanup components
            await self._cleanup_components()

            self._set_state(AgentState.SHUTDOWN)
            self._log.info("Agent stopped successfully")

    async def restart(self) -> None:
        """Restart the agent."""
        self._log.info("Restarting agent")
        await self.stop()
        await asyncio.sleep(1)  # Brief pause
        await self.start()

    async def _initialize_components(self) -> None:
        """Initialize agent components."""
        # Initialize rule engine
        if self.rule_engine:
            await self.rule_engine.initialize()

        # Initialize memory store
        if self.memory:
            await self.memory.initialize()

        # Initialize tool registry
        if self.tools:
            await self.tools.initialize()

    async def _cleanup_components(self) -> None:
        """Cleanup agent components."""
        # Cleanup tool registry
        if self.tools:
            await self.tools.cleanup()

        # Cleanup memory store
        if self.memory:
            await self.memory.cleanup()

        # Cleanup rule engine
        if self.rule_engine:
            await self.rule_engine.cleanup()

    def _set_state(self, state: AgentState) -> None:
        """Update agent state and timestamp."""
        self.metadata.state = state
        self.metadata.updated_at = datetime.now(UTC)
        self._log.info("Agent state changed", state=state.value)

    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self.metadata.state

    @property
    def is_running(self) -> bool:
        """Check if agent is running."""
        return self._running and self.metadata.state in [AgentState.READY, AgentState.BUSY]

    async def on_start(self) -> None:
        """Override to add startup logic."""
        pass

    async def on_stop(self) -> None:
        """Override to add shutdown logic."""
        pass

    # ------------------------------------------------------------------ #
    #  Rule-enforced message dispatch                                      #
    # ------------------------------------------------------------------ #

    async def process(
        self, message: AgentMessage, context: AgentContext | None = None
    ) -> AgentResponse:
        """
        Public entry point for message processing.
        Runs rule checks before and after handling.
        """
        if not self._running:
            await self.start()

        ctx = context or AgentContext()
        start_time = asyncio.get_event_loop().time()

        async with self._task_semaphore:
            # Pre-processing rules
            pre_result = await self.rule_engine.evaluate_pre(
                agent=self, message=message, context=ctx
            )
            if not pre_result.allowed:
                return AgentResponse(
                    success=False,
                    error=f"Rule blocked: {pre_result.reason}",
                    agent_id=self.id,
                )

            try:
                response = await asyncio.wait_for(
                    self.handle_message(message, ctx),
                    timeout=self.metadata.timeout_seconds,
                )
            except TimeoutError:
                return AgentResponse(
                    success=False,
                    error="Agent timed out",
                    agent_id=self.id,
                )
            except Exception as exc:
                self._log.error("Message handling failed", error=str(exc))
                return AgentResponse(success=False, error=str(exc), agent_id=self.id)

            # Post-processing rules
            await self.rule_engine.evaluate_post(
                agent=self, message=message, response=response, context=ctx
            )

            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            response.agent_id = self.id
            response.execution_time_ms = elapsed
            response.context = ctx

            # Persist to memory
            await self.memory.save_interaction(
                agent_id=self.id,
                message=message,
                response=response,
                context=ctx,
            )

            return response

    # ------------------------------------------------------------------ #
    #  Utilities                                                           #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        return self.metadata.model_dump()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id={self.id!r}, name={self.name!r}, "
            f"type={self.AGENT_TYPE!r})"
        )
