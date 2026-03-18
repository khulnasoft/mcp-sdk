"""
Specialized Agent Types
========================
Concrete agent implementations for each interaction pattern.
"""

from __future__ import annotations

from typing import Any

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse, BaseAgent


class A2AAgent(BaseAgent):
    """
    Agent-to-Agent agent.

    Designed for direct agent communication, delegation, and collaboration.
    Supports peer discovery via the AgentRegistry and spawning sub-agents.

    Use cases:
    - Task delegation chains
    - Agent collaboration networks
    - Specialist sub-agent spawning
    """

    AGENT_TYPE = "a2a"

    def get_capabilities(self) -> list[str]:
        return ["delegate", "collaborate", "spawn_subagent", "peer_discovery"]

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        """Default handler — subclass to implement domain logic."""
        return AgentResponse(
            data={"echo": message.content, "agent": self.name},
            metadata={"type": "a2a"},
        )

    async def delegate_to(
        self,
        target_agent_id: str,
        message: AgentMessage,
        context: AgentContext,
    ) -> AgentResponse:
        """Delegate a task to another agent by ID."""
        from mcp_sdk.agents.registry import AgentRegistry

        registry = AgentRegistry.global_registry()
        target = registry.get(target_agent_id)
        return await target.process(message, context)


class A2BAgent(BaseAgent):
    """
    Agent-to-Business agent.

    Bridges AI agents with business APIs, ERPs, CRMs, and SaaS platforms.
    Handles API auth, retry logic, and schema transformation.

    Use cases:
    - CRM automation (Salesforce, HubSpot)
    - ERP integration (SAP, NetSuite)
    - SaaS workflow automation
    """

    AGENT_TYPE = "a2b"

    def __init__(self, *args: Any, api_base_url: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.api_base_url = api_base_url

    def get_capabilities(self) -> list[str]:
        return ["api_call", "webhook_handler", "data_transform", "erp_integration"]

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        return AgentResponse(
            data={"status": "handled", "business_api": self.api_base_url},
            metadata={"type": "a2b"},
        )

    async def call_api(
        self,
        endpoint: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated HTTP call to a business API."""
        import httpx

        url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                json=payload,
                headers=headers or {},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


class B2BAgent(BaseAgent):
    """
    Business-to-Business agent.

    Facilitates multi-tenant, cross-organization agent workflows.
    Enforces tenant isolation, cross-org auth, and SLA policies.

    Use cases:
    - Partner integration networks
    - Cross-company data exchange
    - Multi-tenant SaaS backends
    """

    AGENT_TYPE = "b2b"

    def __init__(self, *args: Any, tenant_id: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tenant_id = tenant_id

    def get_capabilities(self) -> list[str]:
        return ["tenant_routing", "cross_org_auth", "sla_enforcement", "data_isolation"]

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        # Enforce tenant context
        if context.tenant_id and context.tenant_id != self.tenant_id:
            return AgentResponse(
                success=False,
                error=f"Tenant mismatch: {context.tenant_id} != {self.tenant_id}",
            )
        return AgentResponse(
            data={"tenant": self.tenant_id, "message_id": message.id},
            metadata={"type": "b2b"},
        )


class B2CAgent(BaseAgent):
    """
    Business-to-Customer agent.

    Customer-facing conversational agents with personalization,
    session management, and multi-channel delivery (chat, email, SMS).

    Use cases:
    - Customer support bots
    - Sales assistants
    - Onboarding flows
    - Personalized recommendation engines
    """

    AGENT_TYPE = "b2c"

    def __init__(
        self,
        *args: Any,
        persona: str = "helpful assistant",
        channels: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.persona = persona
        self.delivery_channels = channels or ["chat"]

    def get_capabilities(self) -> list[str]:
        return [
            "conversational",
            "personalization",
            "multi_channel",
            "session_management",
            "recommendation",
        ]

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        # Retrieve user context from memory
        user_history = await self.memory.get_user_history(
            user_id=context.user_id or "anonymous",
            limit=10,
        )
        return AgentResponse(
            data={
                "reply": f"[{self.persona}]: Received your message.",
                "history_length": len(user_history),
            },
            metadata={"type": "b2c", "channels": self.delivery_channels},
        )
