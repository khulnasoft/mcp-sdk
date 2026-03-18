"""Tests for the Rule Engine."""

from datetime import UTC, datetime, timedelta

import pytest

from mcp_sdk.agents.base import AgentContext, AgentMessage
from mcp_sdk.core.exceptions import RuleValidationError
from mcp_sdk.rules.builder import RuleBuilder
from mcp_sdk.rules.engine import RuleCondition, RuleEngine


class MockAgent:
    AGENT_TYPE = "a2a"
    id = "agent-1"
    name = "test-agent"

    def to_dict(self):
        return {"id": self.id, "name": self.name, "agent_type": self.AGENT_TYPE}


class TestRuleCondition:
    def test_eq_operator(self) -> None:
        cond = RuleCondition(field="context.user_id", operator="eq", value="alice")
        assert cond.evaluate({"context": {"user_id": "alice"}}) is True
        assert cond.evaluate({"context": {"user_id": "bob"}}) is False

    def test_ne_operator(self) -> None:
        cond = RuleCondition(field="context.user_id", operator="ne", value="alice")
        assert cond.evaluate({"context": {"user_id": "bob"}}) is True

    def test_contains_operator(self) -> None:
        cond = RuleCondition(field="message.content", operator="contains", value="spam")
        assert cond.evaluate({"message": {"content": "this is spam"}}) is True
        assert cond.evaluate({"message": {"content": "hello"}}) is False

    def test_in_operator(self) -> None:
        cond = RuleCondition(field="context.channel", operator="in", value=["a2a", "b2c"])
        assert cond.evaluate({"context": {"channel": "a2a"}}) is True
        assert cond.evaluate({"context": {"channel": "grpc"}}) is False

    def test_exists_operator(self) -> None:
        cond = RuleCondition(field="context.user_id", operator="exists", value=None)
        assert cond.evaluate({"context": {"user_id": "alice"}}) is True
        assert cond.evaluate({"context": {}}) is False

    def test_not_exists_operator(self) -> None:
        cond = RuleCondition(field="context.user_id", operator="not_exists", value=None)
        assert cond.evaluate({"context": {}}) is True

    def test_dot_path_extraction(self) -> None:
        cond = RuleCondition(field="a.b.c", operator="eq", value=42)
        assert cond.evaluate({"a": {"b": {"c": 42}}}) is True


class TestRuleBuilder:
    def test_basic_deny_rule(self) -> None:
        rule = (
            RuleBuilder("test-rule")
            .named("Test Rule")
            .with_priority(50)
            .in_phase("pre")
            .when("context.user_id", "not_exists", None)
            .deny(reason="Must be authenticated")
            .build()
        )
        assert rule.id == "test-rule"
        assert rule.priority == 50
        assert rule.phase == "pre"
        assert len(rule.conditions) == 1
        assert len(rule.actions) == 1
        assert rule.actions[0].action_type == "deny"

    def test_allow_rule(self) -> None:
        rule = RuleBuilder("allow-all").allow().build()
        assert rule.actions[0].action_type == "allow"

    def test_no_actions_raises(self) -> None:
        with pytest.raises(RuleValidationError):
            RuleBuilder("empty-rule").build()

    def test_invalid_phase_raises(self) -> None:
        with pytest.raises(RuleValidationError):
            RuleBuilder("bad-phase").in_phase("invalid")

    def test_yaml_loading(self) -> None:
        yaml_content = """
rules:
  - id: block-anon
    name: Block Anonymous
    priority: 100
    phase: pre
    conditions:
      - field: context.user_id
        operator: not_exists
        value: null
    actions:
      - action_type: deny
        reason: "Auth required"
"""
        rules = RuleBuilder.from_yaml(yaml_content)
        assert len(rules) == 1
        assert rules[0].id == "block-anon"

    def test_and_logic(self) -> None:
        rule = (
            RuleBuilder("and-rule")
            .with_logic("AND")
            .when("context.user_id", "exists", None)
            .when("context.tenant_id", "exists", None)
            .allow()
            .build()
        )
        assert rule.logic == "AND"

    def test_or_logic(self) -> None:
        rule = (
            RuleBuilder("or-rule")
            .with_logic("OR")
            .when("context.user_id", "eq", "admin")
            .when("context.tenant_id", "eq", "root")
            .allow()
            .build()
        )
        assert rule.logic == "OR"


class TestRuleEngine:
    @pytest.fixture
    def engine(self):
        return RuleEngine()

    @pytest.fixture
    def agent(self):
        return MockAgent()

    @pytest.fixture
    def message(self):
        return AgentMessage(sender_id="user", recipient_id="agent", content="hello")

    @pytest.fixture
    def context(self):
        return AgentContext(user_id="alice", tenant_id="tenant-1")

    @pytest.mark.asyncio
    async def test_allow_when_no_rules(self, engine, agent, message, context) -> None:
        result = await engine.evaluate_pre(agent, message, context)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_deny_rule_blocks(self, engine, agent, message, context) -> None:
        rule = RuleBuilder("deny-all").with_priority(100).deny(reason="No access").build()
        engine.add_rule(rule)
        result = await engine.evaluate_pre(agent, message, context)
        assert result.allowed is False
        assert result.denied_by == "deny-all"
        assert "No access" in result.reason

    @pytest.mark.asyncio
    async def test_condition_prevents_deny(self, engine, agent, message, context) -> None:
        rule = (
            RuleBuilder("deny-anon")
            .with_priority(100)
            .when("context.user_id", "not_exists", None)
            .deny(reason="Auth required")
            .build()
        )
        engine.add_rule(rule)
        # context has user_id=alice, so condition doesn't match → allow
        result = await engine.evaluate_pre(agent, message, context)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_disabled_rule_ignored(self, engine, agent, message, context) -> None:
        rule = RuleBuilder("disabled-deny").deny(reason="Should be disabled").enabled(False).build()
        engine.add_rule(rule)
        result = await engine.evaluate_pre(agent, message, context)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_time_bounded_rule(self, engine, agent, message, context) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        rule = RuleBuilder("expired-rule").valid_until(past).deny(reason="Expired rule").build()
        engine.add_rule(rule)
        result = await engine.evaluate_pre(agent, message, context)
        assert result.allowed is True  # expired rule should not fire

    def test_remove_rule(self, engine) -> None:
        rule = RuleBuilder("temp-rule").allow().build()
        engine.add_rule(rule)
        assert len(engine.get_rules()) == 1
        engine.remove_rule("temp-rule")
        assert len(engine.get_rules()) == 0

    def test_priority_ordering(self, engine) -> None:
        r1 = RuleBuilder("low").with_priority(1).allow().build()
        r2 = RuleBuilder("high").with_priority(100).allow().build()
        engine.add_rule(r1)
        engine.add_rule(r2)
        rules = engine.get_rules()
        assert rules[0].id == "high"
