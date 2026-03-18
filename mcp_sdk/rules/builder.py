"""
Rule Builder — Fluent API
==========================
Build complex rule sets using a fluent, chainable builder pattern.
Rules can be loaded from YAML/JSON or constructed programmatically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import yaml

from mcp_sdk.core.exceptions import RuleValidationError
from mcp_sdk.rules.engine import Rule, RuleAction, RuleCondition, RuleEngine


class RuleBuilder:
    """
    Fluent builder for constructing rules.

    Example::

        rule = (
            RuleBuilder("require-auth")
            .named("Require Authentication")
            .described("Blocks unauthenticated requests")
            .with_priority(100)
            .in_phase("pre")
            .when("context.user_id", "not_exists", None)
            .deny(reason="Authentication required")
            .build()
        )

        engine = RuleEngine()
        engine.add_rule(rule)
    """

    def __init__(self, rule_id: str) -> None:
        self._id = rule_id
        self._name = rule_id
        self._description = ""
        self._priority = 0
        self._phase = "pre"
        self._logic = "AND"
        self._enabled = True
        self._conditions: list[RuleCondition] = []
        self._actions: list[RuleAction] = []
        self._valid_from: datetime | None = None
        self._valid_until: datetime | None = None
        self._rate_limit: tuple[int, int] | None = None
        self._tags: list[str] = []

    # ------------------------------------------------------------------ #
    #  Metadata setters                                                    #
    # ------------------------------------------------------------------ #

    def named(self, name: str) -> RuleBuilder:
        self._name = name
        return self

    def described(self, description: str) -> RuleBuilder:
        self._description = description
        return self

    def with_priority(self, priority: int) -> RuleBuilder:
        self._priority = priority
        return self

    def in_phase(self, phase: str) -> RuleBuilder:
        """Set evaluation phase: 'pre', 'post', or 'both'."""
        if phase not in ("pre", "post", "both"):
            raise RuleValidationError(f"Invalid phase '{phase}'. Must be pre, post, or both.")
        self._phase = phase
        return self

    def with_logic(self, logic: str) -> RuleBuilder:
        """Condition logic: 'AND' or 'OR'."""
        if logic not in ("AND", "OR"):
            raise RuleValidationError(f"Invalid logic '{logic}'. Must be AND or OR.")
        self._logic = logic
        return self

    def enabled(self, value: bool = True) -> RuleBuilder:
        self._enabled = value
        return self

    def valid_from(self, dt: datetime) -> RuleBuilder:
        self._valid_from = dt
        return self

    def valid_until(self, dt: datetime) -> RuleBuilder:
        self._valid_until = dt
        return self

    def with_rate_limit(self, requests: int, window_seconds: int = 60) -> RuleBuilder:
        self._rate_limit = (requests, window_seconds)
        return self

    def tagged(self, *tags: str) -> RuleBuilder:
        self._tags.extend(tags)
        return self

    # ------------------------------------------------------------------ #
    #  Condition builders                                                  #
    # ------------------------------------------------------------------ #

    def when(self, field: str, operator: str, value: Any) -> RuleBuilder:
        """Add a condition. Chainable."""
        self._conditions.append(RuleCondition(field=field, operator=operator, value=value))
        return self

    def when_field_equals(self, field: str, value: Any) -> RuleBuilder:
        return self.when(field, "eq", value)

    def when_field_contains(self, field: str, value: str) -> RuleBuilder:
        return self.when(field, "contains", value)

    def when_field_in(self, field: str, values: list[Any]) -> RuleBuilder:
        return self.when(field, "in", values)

    def when_user_authenticated(self) -> RuleBuilder:
        return self.when("context.user_id", "exists", None)

    def when_tenant_is(self, tenant_id: str) -> RuleBuilder:
        return self.when("context.tenant_id", "eq", tenant_id)

    def when_agent_type_is(self, agent_type: str) -> RuleBuilder:
        return self.when("agent.agent_type", "eq", agent_type)

    def when_channel_is(self, channel: str) -> RuleBuilder:
        return self.when("context.channel", "eq", channel)

    # ------------------------------------------------------------------ #
    #  Action builders                                                     #
    # ------------------------------------------------------------------ #

    def allow(self) -> RuleBuilder:
        self._actions.append(RuleAction(action_type="allow"))
        return self

    def deny(self, reason: str = "Denied by rule") -> RuleBuilder:
        self._actions.append(RuleAction(action_type="deny", params={"reason": reason}))
        return self

    def log(self, message: str = "") -> RuleBuilder:
        self._actions.append(RuleAction(action_type="log", params={"message": message}))
        return self

    def notify(self, channel: str, message: str) -> RuleBuilder:
        self._actions.append(
            RuleAction(action_type="notify", params={"channel": channel, "message": message})
        )
        return self

    def custom(self, action_type: str, **params: Any) -> RuleBuilder:
        self._actions.append(RuleAction(action_type=action_type, params=params))
        return self

    def rate_limit_action(self) -> RuleBuilder:
        if self._rate_limit:
            self._actions.append(
                RuleAction(
                    action_type="rate_limit",
                    params={
                        "requests": self._rate_limit[0],
                        "window_seconds": self._rate_limit[1],
                    },
                )
            )
        return self

    # ------------------------------------------------------------------ #
    #  Build                                                               #
    # ------------------------------------------------------------------ #

    def build(self) -> Rule:
        """Validate and build the Rule object."""
        if not self._actions:
            raise RuleValidationError(f"Rule '{self._id}' has no actions defined.")
        return Rule(
            id=self._id,
            name=self._name,
            description=self._description,
            priority=self._priority,
            enabled=self._enabled,
            phase=self._phase,
            logic=self._logic,
            conditions=self._conditions,
            actions=self._actions,
            valid_from=self._valid_from,
            valid_until=self._valid_until,
            rate_limit_requests=self._rate_limit[0] if self._rate_limit else None,
            rate_limit_window_seconds=self._rate_limit[1] if self._rate_limit else 60,
            tags=self._tags,
        )

    # ------------------------------------------------------------------ #
    #  Bulk loader                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_yaml(cls, content: str) -> list[Rule]:
        """Load a list of rules from a YAML string."""
        data = yaml.safe_load(content)
        rules = []
        for item in data.get("rules", []):
            builder = cls(item["id"])
            builder.named(item.get("name", item["id"]))
            builder.described(item.get("description", ""))
            builder.with_priority(item.get("priority", 0))
            builder.in_phase(item.get("phase", "pre"))
            builder.with_logic(item.get("logic", "AND"))
            for cond in item.get("conditions", []):
                builder.when(cond["field"], cond["operator"], cond["value"])
            for act in item.get("actions", []):
                atype = act["action_type"]
                params = {k: v for k, v in act.items() if k != "action_type"}
                builder.custom(atype, **params)
                # Handle deny shorthand
                if atype == "deny" and "reason" not in params:
                    params["reason"] = "Denied by rule"
            if item.get("tags"):
                builder.tagged(*item["tags"])
            rules.append(builder.build())
        return rules

    @classmethod
    def load_into_engine(cls, engine: RuleEngine, yaml_content: str) -> int:
        """Load rules from YAML into a RuleEngine. Returns count loaded."""
        rules = cls.from_yaml(yaml_content)
        for rule in rules:
            engine.add_rule(rule)
        return len(rules)
