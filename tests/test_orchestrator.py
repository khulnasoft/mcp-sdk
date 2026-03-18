"""Tests for Orchestrator."""

import pytest

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.agents.registry import AgentRegistry
from mcp_sdk.agents.types import A2AAgent
from mcp_sdk.orchestrator.manager import (
    OrchestratorManager,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
)


class EchoAgent(A2AAgent):
    async def handle_message(self, message, context):
        return AgentResponse(data={"echo": message.content, "from": self.name})


class TestOrchestrator:
    @pytest.fixture
    def registry(self):
        return AgentRegistry()

    @pytest.fixture
    async def populated_registry(self, registry):
        a1 = EchoAgent(name="step-1-agent")
        a2 = EchoAgent(name="step-2-agent")
        await a1.start()
        await a2.start()
        await registry.register(a1)
        await registry.register(a2)
        return registry, a1, a2

    @pytest.fixture
    async def manager(self, populated_registry):
        registry, a1, a2 = populated_registry
        return OrchestratorManager(registry=registry), registry, a1, a2

    @pytest.mark.asyncio
    async def test_sequential_workflow(self, manager) -> None:
        orch, registry, a1, a2 = manager
        wf = WorkflowDefinition(
            name="test-seq",
            steps=[
                WorkflowStep(name="step1", agent_id=a1.id, output_key="step1_out"),
                WorkflowStep(
                    name="step2",
                    agent_id=a2.id,
                    output_key="step2_out",
                    depends_on=["step1_out"],
                ),
            ],
        )
        # Fix: depends_on uses step_ids, not output_keys
        wf.steps[1].depends_on = [wf.steps[0].step_id]

        msg = AgentMessage(sender_id="user", recipient_id=a1.id, content="start")
        ctx = AgentContext(user_id="alice")

        execution = await orch.execute_workflow(wf, msg, ctx)
        assert execution.status == WorkflowStatus.COMPLETED
        assert "step1_out" in execution.step_results
        assert "step2_out" in execution.step_results

    @pytest.mark.asyncio
    async def test_parallel_workflow(self, manager) -> None:
        orch, registry, a1, a2 = manager
        wf = WorkflowDefinition(
            name="test-parallel",
            parallel=True,
            steps=[
                WorkflowStep(name="step1", agent_id=a1.id, output_key="r1"),
                WorkflowStep(name="step2", agent_id=a2.id, output_key="r2"),
            ],
        )
        msg = AgentMessage(sender_id="user", recipient_id=a1.id, content="go")
        ctx = AgentContext(user_id="alice")
        execution = await orch.execute_workflow(wf, msg, ctx)
        assert execution.status == WorkflowStatus.COMPLETED
        assert len(execution.step_results) == 2

    @pytest.mark.asyncio
    async def test_route_direct(self, manager) -> None:
        orch, registry, a1, a2 = manager
        msg = AgentMessage(sender_id="user", recipient_id=a1.id, content="ping")
        ctx = AgentContext(user_id="alice")
        response = await orch.route(msg, ctx, strategy="direct")
        assert response.success is True

    @pytest.mark.asyncio
    async def test_route_by_capability(self, manager) -> None:
        orch, registry, a1, a2 = manager
        msg = AgentMessage(sender_id="user", recipient_id="delegate", content="task")
        ctx = AgentContext(user_id="alice")
        response = await orch.route(msg, ctx, strategy="capability")
        assert response.success is True

    def test_execution_tracking(self, event_loop, manager) -> None:
        import asyncio

        orch, registry, a1, a2 = (
            event_loop.run_until_complete(asyncio.coroutine(lambda: manager)())
            if False
            else manager
        )  # just test the sync accessor
        assert orch.list_executions() == []
