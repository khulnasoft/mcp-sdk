"""
Example: Complete Rules Showcase
==================================
Demonstrates the full rule engine capability:
- Authentication rules
- Rate limiting
- Content moderation
- Time-bounded rules
- Custom actions
- YAML rule loading
"""

import asyncio

from mcp_sdk.agents.base import AgentContext, AgentMessage
from mcp_sdk.agents.types import A2AAgent
from mcp_sdk.rules.builder import RuleBuilder
from mcp_sdk.rules.engine import RuleEngine

RULES_YAML = """
rules:
  - id: require-auth
    name: Require Authentication
    description: All requests must include a user ID
    priority: 100
    phase: pre
    logic: AND
    conditions:
      - field: context.user_id
        operator: not_exists
        value: null
    actions:
      - action_type: deny
        reason: "You must be authenticated to use this service"
    tags: [security, auth]

  - id: block-banned-words
    name: Block Banned Words
    description: Filter messages containing banned content
    priority: 90
    phase: pre
    logic: OR
    conditions:
      - field: message.content
        operator: contains
        value: "spam"
      - field: message.content
        operator: contains
        value: "scam"
    actions:
      - action_type: deny
        reason: "Message contains prohibited content"
    tags: [moderation, content]

  - id: admin-bypass
    name: Admin Bypass
    description: Admin users skip moderation rules
    priority: 200
    phase: pre
    logic: AND
    conditions:
      - field: context.user_id
        operator: eq
        value: "admin"
    actions:
      - action_type: allow
    tags: [security, admin]

  - id: audit-all
    name: Audit Log All
    description: Record every interaction for compliance
    priority: 5
    phase: both
    conditions: []
    actions:
      - action_type: log
        message: "Interaction audited"
    tags: [compliance, audit]
"""


async def test_rules() -> None:
    print("📋 Rule Engine Showcase")
    print("=" * 50)

    # Build engine from YAML
    engine = RuleEngine()
    count = RuleBuilder.load_into_engine(engine, RULES_YAML)
    print(f"\n✅ Loaded {count} rules from YAML")

    # Add a custom action
    async def custom_alert(data: dict, params: dict) -> None:
        print(f"  🚨 ALERT: {params.get('message', 'Custom alert triggered')}")

    engine.register_action("alert", custom_alert)

    # Create a simple test agent
    agent = A2AAgent(name="rule-test-agent", rule_engine=engine)
    await agent.start()

    test_cases = [
        ("No auth", AgentContext(), "Hello world"),
        ("Authenticated", AgentContext(user_id="alice"), "Hello world"),
        ("Spam message", AgentContext(user_id="alice"), "This is a spam message!"),
        ("Admin bypasses spam", AgentContext(user_id="admin"), "This is spam but admin"),
    ]

    print("\n🧪 Test Cases:")
    print("-" * 50)

    for case_name, context, content in test_cases:
        message = AgentMessage(
            sender_id=context.user_id or "anonymous",
            recipient_id=agent.id,
            content=content,
        )
        response = await agent.process(message, context)
        status = "✅ ALLOWED" if response.success else f"🚫 DENIED: {response.error}"
        print(f"  [{case_name}]: {status}")

    await agent.stop()

    # Show programmatic builder
    print("\n🔨 Programmatic Rule Builder:")
    print("-" * 50)

    custom_rule = (
        RuleBuilder("vip-only")
        .named("VIP Members Only")
        .described("Restrict endpoint to VIP tier users")
        .with_priority(150)
        .in_phase("pre")
        .with_logic("OR")
        .when("context.user_id", "in", ["vip-1", "vip-2", "vip-3"])
        .when_agent_type_is("b2c")
        .allow()
        .tagged("access-control", "vip")
        .build()
    )

    print(f"  Rule: {custom_rule.name}")
    print(f"  Priority: {custom_rule.priority}")
    print(f"  Conditions: {len(custom_rule.conditions)}")
    print(f"  Tags: {custom_rule.tags}")
    print(f"  Phase: {custom_rule.phase}")

    print("\n✅ Rule showcase complete!")


if __name__ == "__main__":
    asyncio.run(test_rules())
