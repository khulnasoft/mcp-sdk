"""
Example: B2C Conversational Agent
===================================
A customer-facing conversational agent with:
- Personalization via memory
- Rule-based content moderation
- Session management
- Multi-turn conversation tracking
"""

import asyncio

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.agents.types import B2CAgent
from mcp_sdk.memory.store import MemoryStore
from mcp_sdk.rules.builder import RuleBuilder
from mcp_sdk.rules.engine import RuleEngine

# ------------------------------------------------------------------ #
#  Custom B2C Agent                                                    #
# ------------------------------------------------------------------ #


class CustomerSupportAgent(B2CAgent):
    """Customer support agent with product knowledge and escalation."""

    GREETINGS = ["hi", "hello", "hey", "good morning", "good evening"]
    ESCALATION_KEYWORDS = ["lawsuit", "legal", "fraud", "chargeback"]

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        content = str(message.content).lower()
        user_id = context.user_id or "anonymous"

        # Get conversation history
        history = await self.memory.get_user_history(user_id=user_id, limit=5)
        turn_number = len(history) + 1

        # Detect intent
        if any(g in content for g in self.GREETINGS):
            reply = f"Hello! I'm {self.persona}. How can I assist you today? 😊"
        elif any(k in content for k in self.ESCALATION_KEYWORDS):
            reply = (
                "I understand this is a serious matter. "
                "Let me escalate this to our senior support team immediately."
            )
        elif "refund" in content:
            reply = (
                "I can help with refunds! Please provide your order number "
                "and I'll process it within 3-5 business days."
            )
        elif "track" in content and "order" in content:
            reply = "To track your order, please share your order ID and I'll look it up."
        else:
            reply = (
                f"Thank you for reaching out! I've received your message "
                f"(turn {turn_number}). A specialist will review and respond shortly."
            )

        # Save to user history
        await self.memory.save_user_message(
            user_id=user_id,
            record={"turn": turn_number, "user": content, "agent": reply},
        )

        return AgentResponse(
            data={
                "reply": reply,
                "turn": turn_number,
                "persona": self.persona,
                "channels": self.delivery_channels,
            }
        )

    def get_capabilities(self) -> list[str]:
        return super().get_capabilities() + ["support", "refund", "order_tracking", "escalation"]


# ------------------------------------------------------------------ #
#  Rules for moderation                                                #
# ------------------------------------------------------------------ #


def build_content_rules() -> RuleEngine:
    engine = RuleEngine()

    # Rate limit per user
    rate_rule = (
        RuleBuilder("rate-limit-users")
        .named("Rate Limit Users")
        .with_priority(90)
        .with_rate_limit(requests=20, window_seconds=60)
        .rate_limit_action()
        .build()
    )
    engine.add_rule(rate_rule)

    # Block empty messages
    empty_rule = (
        RuleBuilder("block-empty")
        .named("Block Empty Messages")
        .with_priority(80)
        .when("message.content", "eq", "")
        .deny(reason="Message cannot be empty")
        .build()
    )
    engine.add_rule(empty_rule)

    return engine


# ------------------------------------------------------------------ #
#  B2C demo conversation                                               #
# ------------------------------------------------------------------ #


async def simulate_conversation(agent: CustomerSupportAgent) -> None:
    user_id = "customer-42"
    session_id = "sess-abc123"

    conversation = [
        "Hello there!",
        "I need to track my order #12345",
        "Actually, I want a refund for that order",
        "This is taking too long, this feels like fraud!",
    ]

    print(f"\n💬 Simulating conversation for user: {user_id}")
    print("-" * 50)

    for user_msg in conversation:
        context = AgentContext(
            user_id=user_id,
            session_id=session_id,
            channel="chat",
        )
        message = AgentMessage(
            sender_id=user_id,
            recipient_id=agent.id,
            content=user_msg,
            context=context,
        )

        response = await agent.process(message, context)

        print(f"\n👤 Customer: {user_msg}")
        if response.success:
            print(f"🤖 {agent.persona}: {response.data.get('reply', '')}")
        else:
            print(f"❌ Error: {response.error}")

    # Show history
    history = await agent.memory.get_user_history(user_id=user_id)
    print(f"\n📋 Conversation history: {len(history)} turns recorded")


async def main() -> None:
    print("🤖 B2C Customer Support Agent Example")
    print("=" * 50)

    memory = MemoryStore()
    rules = build_content_rules()

    agent = CustomerSupportAgent(
        name="support-bot",
        description="24/7 Customer Support Agent",
        persona="SupportBot Pro",
        channels=["chat", "email", "sms"],
        memory=memory,
        rule_engine=rules,
    )

    await agent.start()
    await simulate_conversation(agent)
    await agent.stop()

    print("\n✅ Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
