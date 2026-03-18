"""
Example: A2A Agent Delegation
==============================
Demonstrates two A2A agents communicating via the registry:
- ResearchAgent searches for information
- SummarizerAgent summarizes the result
- Orchestrator coordinates the pipeline
"""

import asyncio

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.agents.registry import AgentRegistry
from mcp_sdk.agents.types import A2AAgent
from mcp_sdk.orchestrator.manager import OrchestratorManager, WorkflowDefinition, WorkflowStep
from mcp_sdk.rules.builder import RuleBuilder
from mcp_sdk.rules.engine import RuleEngine

# ------------------------------------------------------------------ #
#  Define specialist agents                                            #
# ------------------------------------------------------------------ #


class ResearchAgent(A2AAgent):
    """Simulates a web-search agent."""

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        query = str(message.content)
        # Simulate research
        results = [
            f"Result 1 about '{query}'",
            f"Result 2 about '{query}'",
            f"Result 3 about '{query}'",
        ]
        return AgentResponse(data={"query": query, "results": results})

    def get_capabilities(self) -> list[str]:
        return ["search", "research", "web_lookup"]


class SummarizerAgent(A2AAgent):
    """Summarizes content received from another agent."""

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        content = message.content
        if isinstance(content, dict) and "results" in content:
            summary = (
                f"Summary of {len(content['results'])} results about '{content.get('query', '')}'"
            )
        else:
            summary = f"Summary: {str(content)[:100]}"
        return AgentResponse(data={"summary": summary})

    def get_capabilities(self) -> list[str]:
        return ["summarize", "condense", "extract"]


# ------------------------------------------------------------------ #
#  Build rules                                                         #
# ------------------------------------------------------------------ #


def build_rules() -> RuleEngine:
    engine = RuleEngine()

    # Require user authentication
    auth_rule = (
        RuleBuilder("require-auth")
        .named("Require Authentication")
        .with_priority(100)
        .when("context.user_id", "not_exists", None)
        .deny(reason="Authentication required to use research pipeline")
        .build()
    )
    engine.add_rule(auth_rule)

    # Log all research requests
    log_rule = (
        RuleBuilder("log-research")
        .named("Log Research Requests")
        .with_priority(10)
        .when_channel_is("a2a")
        .log(message="Research pipeline request received")
        .allow()
        .build()
    )
    engine.add_rule(log_rule)

    return engine


# ------------------------------------------------------------------ #
#  Main demo                                                           #
# ------------------------------------------------------------------ #


async def main() -> None:
    print("🤖 A2A Agent Delegation Example")
    print("=" * 50)

    # Create shared infrastructure
    registry = AgentRegistry()
    rule_engine = build_rules()

    # Instantiate agents
    researcher = ResearchAgent(name="researcher", rule_engine=rule_engine)
    summarizer = SummarizerAgent(name="summarizer", rule_engine=rule_engine)

    await researcher.start()
    await summarizer.start()

    await registry.register(researcher)
    await registry.register(summarizer)

    # Set up orchestrator
    orchestrator = OrchestratorManager(registry=registry)

    # Define a two-step workflow
    workflow = WorkflowDefinition(
        name="Research & Summarize",
        steps=[
            WorkflowStep(
                name="research",
                agent_id=researcher.id,
                output_key="research_results",
            ),
            WorkflowStep(
                name="summarize",
                agent_id=summarizer.id,
                output_key="summary",
                depends_on=[],  # Will be set dynamically
            ),
        ],
    )
    # Link step 2 to step 1
    workflow.steps[1].depends_on = [workflow.steps[0].step_id]

    # Execute
    initial_message = AgentMessage(
        sender_id="user",
        recipient_id=researcher.id,
        content="Model Context Protocol",
    )
    context = AgentContext(
        user_id="alice",
        tenant_id="demo-tenant",
        channel="a2a",
    )

    print(f"\n📤 Query: '{initial_message.content}'")
    print("⚙️  Running workflow...")

    execution = await orchestrator.execute_workflow(workflow, initial_message, context)

    print(f"\n✅ Status: {execution.status.value}")
    print("📊 Results:")
    for key, val in execution.step_results.items():
        print(f"  [{key}]: {val}")

    # Cleanup
    await researcher.stop()
    await summarizer.stop()


if __name__ == "__main__":
    asyncio.run(main())
