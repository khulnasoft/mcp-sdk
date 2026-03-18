"""
Rule Engine
============
Evaluates declarative rules against agents, messages, and contexts.
Rules are evaluated in priority order; first match wins (configurable).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel

from mcp_sdk.core.exceptions import RuleExecutionError

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------ #
#  Rule Model                                                          #
# ------------------------------------------------------------------ #


class RuleCondition(BaseModel):
    """A single evaluable condition."""

    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, contains, matches, in, not_in
    value: Any

    def evaluate(self, data: dict[str, Any]) -> bool:
        """Evaluate this condition against a flat data dict."""
        actual = self._extract(data, self.field)
        op = self.operator.lower()

        if op == "eq":
            return actual == self.value
        elif op == "ne":
            return actual != self.value
        elif op == "gt":
            return actual > self.value
        elif op == "lt":
            return actual < self.value
        elif op == "gte":
            return actual >= self.value
        elif op == "lte":
            return actual <= self.value
        elif op == "contains":
            return self.value in str(actual)
        elif op == "matches":
            return bool(re.fullmatch(self.value, str(actual)))
        elif op == "in":
            return actual in self.value
        elif op == "not_in":
            return actual not in self.value
        elif op == "exists":
            return actual is not None
        elif op == "not_exists":
            return actual is None
        else:
            raise RuleExecutionError("condition", f"Unknown operator: {op}")

    @staticmethod
    def _extract(data: dict[str, Any], field: str) -> Any:
        """Support dot-path field extraction: 'context.user_id'"""
        parts = field.split(".")
        val: Any = data
        for part in parts:
            val = val.get(part) if isinstance(val, dict) else getattr(val, part, None)
        return val


class RuleAction(BaseModel):
    """An action to execute when a rule matches."""

    action_type: str  # allow, deny, log, transform, notify, redirect, rate_limit
    params: dict[str, Any] = {}


class Rule(BaseModel):
    """A complete declarative rule definition."""

    id: str
    name: str
    description: str = ""
    priority: int = 0  # higher number = higher priority
    enabled: bool = True
    phase: str = "pre"  # Union[pre, post] | both
    logic: str = "AND"  # Union[AND, OR]

    conditions: list[RuleCondition] = []
    actions: list[RuleAction] = []

    # Time-based constraints
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    # Rate limiting
    rate_limit_requests: int | None = None
    rate_limit_window_seconds: int = 60

    tags: list[str] = []

    def is_valid_now(self) -> bool:
        now = datetime.now(UTC)
        if self.valid_from and now < self.valid_from:
            return False
        return not (self.valid_until and now > self.valid_until)

    def evaluate_conditions(self, data: dict[str, Any]) -> bool:
        if not self.conditions:
            return True
        results = [c.evaluate(data) for c in self.conditions]
        if self.logic == "AND":
            return all(results)
        else:  # OR
            return any(results)


# ------------------------------------------------------------------ #
#  Rule Evaluation Result                                              #
# ------------------------------------------------------------------ #


class RuleEvalResult(BaseModel):
    """Result of a rule evaluation pass."""

    allowed: bool = True
    matched_rules: list[str] = []
    denied_by: str | None = None
    reason: str = ""
    actions_taken: list[str] = []


# ------------------------------------------------------------------ #
#  Rule Engine                                                         #
# ------------------------------------------------------------------ #


class RuleEngine:
    """
    Evaluates ordered rule sets against agent interactions.

    Rules are evaluated in descending priority order.
    The engine supports pre- and post-processing phases.

    Example::

        engine = RuleEngine()
        engine.add_rule(Rule(
            id="block-anon",
            name="Block Anonymous Users",
            priority=100,
            conditions=[RuleCondition(field="context.user_id", operator="not_exists", value=None)],
            actions=[RuleAction(action_type="deny", params={"reason": "Must be authenticated"})],
        ))

        result = await engine.evaluate_pre(agent, message, context)
        if not result.allowed:
            return AgentResponse(success=False, error=result.reason)
    """

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._custom_actions: dict[str, Callable[..., Any]] = {}
        self._rate_limit_counters: dict[str, list[float]] = {}

    # ------------------------------------------------------------------ #
    #  Rule Management                                                     #
    # ------------------------------------------------------------------ #

    def add_rule(self, rule: Rule) -> None:
        self._rules[rule.id] = rule
        logger.debug("Rule added", rule_id=rule.id, priority=rule.priority)

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def enable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False

    def register_action(self, name: str, handler: Callable[..., Any]) -> None:
        """Register a custom action handler."""
        self._custom_actions[name] = handler

    def get_rules(self, phase: str | None = None) -> list[Rule]:
        rules = [r for r in self._rules.values() if r.enabled]
        if phase:
            rules = [r for r in rules if r.phase in (phase, "both")]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    # ------------------------------------------------------------------ #
    #  Evaluation                                                          #
    # ------------------------------------------------------------------ #

    async def evaluate_pre(
        self,
        agent: Any,
        message: Any,
        context: Any,
    ) -> RuleEvalResult:
        """Evaluate pre-processing rules. Returns allow/deny decision."""
        return await self._evaluate("pre", agent, message, context)

    async def evaluate_post(
        self,
        agent: Any,
        message: Any,
        response: Any,
        context: Any,
    ) -> RuleEvalResult:
        """Evaluate post-processing rules (logging, transformation, etc.)."""
        return await self._evaluate("post", agent, message, context, response)

    async def _evaluate(
        self,
        phase: str,
        agent: Any,
        message: Any,
        context: Any,
        response: Any = None,
    ) -> RuleEvalResult:
        result = RuleEvalResult()
        data = self._build_data(agent, message, context, response)

        for rule in self.get_rules(phase):
            if not rule.is_valid_now():
                continue
            if not rule.evaluate_conditions(data):
                continue

            result.matched_rules.append(rule.id)
            logger.debug("Rule matched", rule_id=rule.id, phase=phase)

            for action in rule.actions:
                await self._execute_action(action, data, rule)
                result.actions_taken.append(f"{rule.id}:{action.action_type}")

                if action.action_type == "deny":
                    result.allowed = False
                    result.denied_by = rule.id
                    result.reason = action.params.get("reason", f"Denied by rule '{rule.name}'")
                    return result  # Short-circuit on deny

        return result

    async def _execute_action(self, action: RuleAction, data: dict[str, Any], rule: Rule) -> Any:
        action_type = action.action_type

        if action_type in ("allow", "deny"):
            return  # handled by caller

        if action_type == "log":
            logger.info(
                "Rule action: log",
                rule_id=rule.id,
                message=action.params.get("message", ""),
            )
        elif action_type == "rate_limit":
            key = f"{rule.id}:{data.get('context', {}).get('user_id', 'anon')}"
            self._check_rate_limit(key, rule)
        elif action_type in self._custom_actions:
            handler = self._custom_actions[action_type]
            if asyncio.iscoroutinefunction(handler):
                await handler(data, action.params)
            else:
                handler(data, action.params)
        else:
            logger.warning("Unknown action type", action=action_type)

    def _check_rate_limit(self, key: str, rule: Rule) -> None:
        import time

        now = time.time()
        window = rule.rate_limit_window_seconds
        limit = rule.rate_limit_requests or 100

        timestamps = [t for t in self._rate_limit_counters.get(key, []) if now - t < window]
        if len(timestamps) >= limit:
            raise RuleExecutionError(rule.id, f"Rate limit exceeded ({limit}/{window}s)")
        timestamps.append(now)
        self._rate_limit_counters[key] = timestamps

    @staticmethod
    def _build_data(agent: Any, message: Any, context: Any, response: Any = None) -> dict[str, Any]:
        return {
            "agent": agent.to_dict() if hasattr(agent, "to_dict") else {},
            "message": message.model_dump() if hasattr(message, "model_dump") else {},
            "context": context.model_dump() if hasattr(context, "model_dump") else {},
            "response": (
                response.model_dump() if response and hasattr(response, "model_dump") else {}
            ),
        }
