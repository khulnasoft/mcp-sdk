"""
Orchestrator Manager
=====================
Coordinates multiple agents, manages workflows, and routes messages
across A2A, A2B, B2B, and B2C channels.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.agents.registry import AgentRegistry
from mcp_sdk.channels.base import A2AChannel
from mcp_sdk.core.exceptions import OrchestratorError

logger = structlog.get_logger(__name__)


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    """A single step in a multi-agent workflow."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    agent_id: str
    input_transform: dict[str, Any] = {}  # JSONPath-like transforms
    output_key: str = "result"
    depends_on: list[str] = []  # step_ids this step waits for
    timeout_seconds: int = 60
    retry_count: int = 0
    retry_delay_seconds: int = 5


class WorkflowDefinition(BaseModel):
    """Defines a multi-step agent workflow."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    steps: list[WorkflowStep]
    parallel: bool = False  # Run all steps in parallel (ignores depends_on)
    timeout_seconds: int = 300


class WorkflowExecution(BaseModel):
    """Tracks the runtime state of a workflow execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_results: dict[str, Any] = {}
    error: str | None = None
    context: dict[str, Any] = {}


class OrchestratorManager:
    """
    Manages multi-agent workflow execution and routing.

    Features:
    - Sequential and parallel workflow execution
    - Dependency-aware step ordering (DAG-based)
    - Automatic retry with backoff
    - Cross-channel routing (A2A, A2B, B2B, B2C)
    - Execution tracking and history

    Example::

        manager = OrchestratorManager(registry)

        wf = WorkflowDefinition(
            name="Research Pipeline",
            steps=[
                WorkflowStep(name="search", agent_id="search-agent", output_key="results"),
                WorkflowStep(name="summarize", agent_id="summarizer", depends_on=["search"]),
            ],
        )

        execution = await manager.execute_workflow(wf, initial_message, context)
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        a2a_channel: A2AChannel | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry.global_registry()
        self.a2a_channel = a2a_channel or A2AChannel()
        self.a2a_channel.bind_registry(self.registry)
        self._executions: dict[str, WorkflowExecution] = {}

    # ------------------------------------------------------------------ #
    #  Single-agent routing                                                #
    # ------------------------------------------------------------------ #

    async def route(
        self,
        message: AgentMessage,
        context: AgentContext | None = None,
        strategy: str = "direct",
    ) -> AgentResponse:
        """
        Route a message to an agent.

        Strategies:
        - direct: Send to recipient_id exactly
        - capability: Find first agent matching recipient_id as capability
        - tag: Find agents by tag and round-robin
        """
        ctx = context or AgentContext()

        if strategy == "direct":
            return await self.a2a_channel.send(message, ctx)

        elif strategy == "capability":
            agents = self.registry.find_by_capability(message.recipient_id)
            if not agents:
                raise OrchestratorError(f"No agent with capability: {message.recipient_id}")
            target = agents[0]
            msg = message.model_copy(update={"recipient_id": target.id})
            return await target.process(msg, ctx)

        elif strategy == "tag":
            agents = self.registry.find_by_tag(message.recipient_id)
            if not agents:
                raise OrchestratorError(f"No agent with tag: {message.recipient_id}")
            target = agents[0]
            msg = message.model_copy(update={"recipient_id": target.id})
            return await target.process(msg, ctx)

        raise OrchestratorError(f"Unknown routing strategy: {strategy}")

    # ------------------------------------------------------------------ #
    #  Workflow execution                                                  #
    # ------------------------------------------------------------------ #

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        initial_message: AgentMessage,
        context: AgentContext | None = None,
    ) -> WorkflowExecution:
        """Execute a full multi-step workflow."""
        ctx = context or AgentContext()
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(UTC),
            context=ctx.model_dump(),
        )
        self._executions[execution.execution_id] = execution

        logger.info("Workflow started", workflow=workflow.name, exec_id=execution.execution_id)

        try:
            if workflow.parallel:
                await self._run_parallel(workflow, initial_message, ctx, execution)
            else:
                await self._run_sequential(workflow, initial_message, ctx, execution)

            execution.status = WorkflowStatus.COMPLETED
        except Exception as exc:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(exc)
            logger.error("Workflow failed", workflow=workflow.name, error=str(exc))
        finally:
            execution.completed_at = datetime.now(UTC)

        return execution

    async def _run_sequential(
        self,
        workflow: WorkflowDefinition,
        initial_message: AgentMessage,
        ctx: AgentContext,
        execution: WorkflowExecution,
    ) -> None:
        """Run steps in dependency order."""
        completed: set[str] = set()
        {s.step_id: s for s in workflow.steps}
        remaining = list(workflow.steps)
        current_content = initial_message.content

        while remaining:
            runnable = [s for s in remaining if all(dep in completed for dep in s.depends_on)]
            if not runnable:
                raise OrchestratorError("Workflow deadlock: circular dependency detected")

            for step in runnable:
                result = await self._run_step(step, current_content, ctx, execution)
                execution.step_results[step.output_key] = result
                current_content = result
                completed.add(step.step_id)
                remaining.remove(step)

    async def _run_parallel(
        self,
        workflow: WorkflowDefinition,
        initial_message: AgentMessage,
        ctx: AgentContext,
        execution: WorkflowExecution,
    ) -> None:
        """Run all steps in parallel."""
        tasks = [
            self._run_step(step, initial_message.content, ctx, execution) for step in workflow.steps
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for step, result in zip(workflow.steps, results, strict=False):
            if isinstance(result, Exception):
                raise OrchestratorError(f"Step '{step.name}' failed: {result}")
            execution.step_results[step.output_key] = result

    async def _run_step(
        self,
        step: WorkflowStep,
        content: Any,
        ctx: AgentContext,
        execution: WorkflowExecution,
    ) -> Any:
        """Execute a single workflow step with retry logic."""
        agent = self.registry.get(step.agent_id)
        message = AgentMessage(
            sender_id="orchestrator",
            recipient_id=step.agent_id,
            content=content,
            context=ctx,
        )

        for attempt in range(step.retry_count + 1):
            try:
                response = await asyncio.wait_for(
                    agent.process(message, ctx),
                    timeout=step.timeout_seconds,
                )
                if response.success:
                    logger.debug("Step completed", step=step.name, attempt=attempt)
                    return response.data
                raise OrchestratorError(f"Step '{step.name}' returned failure: {response.error}")
            except (TimeoutError, OrchestratorError):
                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay_seconds)
                else:
                    raise

        raise OrchestratorError(f"Step '{step.name}' exhausted retries")

    # ------------------------------------------------------------------ #
    #  Execution history                                                   #
    # ------------------------------------------------------------------ #

    def get_execution(self, execution_id: str) -> WorkflowExecution | None:
        return self._executions.get(execution_id)

    def list_executions(self) -> list[WorkflowExecution]:
        return list(self._executions.values())
