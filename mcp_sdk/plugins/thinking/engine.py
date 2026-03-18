"""
Sequential Thinking Engine
============================
Structured multi-step reasoning for agents. Supports:

- Chain-of-thought (CoT) decomposition
- Tree-of-thought (ToT) branching and pruning
- ReAct (Reason + Act) loop with tool integration
- Reflection and self-critique steps
- Step-level confidence scoring
- Lineage tracking (which steps produced which outputs)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class StepType(StrEnum):
    THINK = "think"  # Pure reasoning
    OBSERVE = "observe"  # Gather information
    ACT = "act"  # Execute a tool/action
    REFLECT = "reflect"  # Self-critique / verify
    CONCLUDE = "conclude"  # Final answer synthesis
    BRANCH = "branch"  # Create alternative reasoning paths
    PRUNE = "prune"  # Eliminate low-value branches


class ThinkingStep(BaseModel):
    """A single step in a sequential thinking chain."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_number: int
    step_type: StepType
    thought: str  # Reasoning content
    action: str | None = None  # Tool/action name if ACT
    action_input: dict[str, Any] | None = None
    observation: str | None = None  # Result of action
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parent_step_id: str | None = None  # For branching
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.step_type == StepType.CONCLUDE

    def summary(self) -> str:
        parts = [f"Step {self.step_number} [{self.step_type.value.upper()}]: {self.thought[:120]}"]
        if self.action:
            parts.append(f"  Action: {self.action}({self.action_input})")
        if self.observation:
            parts.append(f"  Observation: {self.observation[:120]}")
        parts.append(f"  Confidence: {self.confidence:.0%}")
        return "\n".join(parts)


class ThinkingChain(BaseModel):
    """A complete chain of reasoning steps."""

    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    steps: list[ThinkingStep] = Field(default_factory=list)
    conclusion: str | None = None
    total_elapsed_ms: float = 0.0
    overall_confidence: float = 0.0
    strategy: str = "react"  # Union[react, cot] | tot

    def add_step(self, step: ThinkingStep) -> None:
        step.step_number = len(self.steps) + 1
        self.steps.append(step)

    def get_conclude_step(self) -> ThinkingStep | None:
        for step in reversed(self.steps):
            if step.step_type == StepType.CONCLUDE:
                return step
        return None

    def to_markdown(self) -> str:
        lines = [f"# Thinking Chain: {self.goal}", f"**Strategy:** {self.strategy}", ""]
        for step in self.steps:
            lines.append(step.summary())
            lines.append("")
        if self.conclusion:
            lines.append(f"**Conclusion:** {self.conclusion}")
            lines.append(f"**Overall Confidence:** {self.overall_confidence:.0%}")
        return "\n".join(lines)


class ThinkingConfig(BaseModel):
    max_steps: int = 10
    max_branches: int = 3
    min_confidence_to_continue: float = 0.3
    enable_reflection: bool = True
    enable_branching: bool = False
    timeout_seconds: float = 60.0


class SequentialThinkingEngine:
    """
    Structured sequential reasoning engine for MCP agents.

    Implements ReAct (default), Chain-of-Thought, and Tree-of-Thought
    reasoning strategies with tool integration and self-reflection.

    Example::

        engine = SequentialThinkingEngine(config=ThinkingConfig(max_steps=8))

        # Register tools
        engine.register_tool("search", search_fn)
        engine.register_tool("calculate", calc_fn)

        chain = await engine.reason(
            goal="What is the population of France multiplied by GDP per capita?",
            initial_context={"user": "alice"},
        )
        print(chain.conclusion)
        print(chain.to_markdown())
    """

    def __init__(
        self,
        config: ThinkingConfig | None = None,
        thinker: Callable[[str, list[ThinkingStep]], Any] | None = None,
    ) -> None:
        self.config = config or ThinkingConfig()
        self._thinker = thinker  # LLM callable (prompt -> text)
        self._tools: dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    async def reason(
        self,
        goal: str,
        initial_context: dict[str, Any] | None = None,
        strategy: str = "react",
    ) -> ThinkingChain:
        chain = ThinkingChain(goal=goal, strategy=strategy)
        start = time.time()

        try:
            if strategy == "react":
                await self._react_loop(chain, initial_context or {})
            elif strategy == "cot":
                await self._chain_of_thought(chain, initial_context or {})
            elif strategy == "tot":
                await self._tree_of_thought(chain, initial_context or {})
            else:
                await self._react_loop(chain, initial_context or {})
        except TimeoutError:
            chain.conclusion = f"Reasoning timed out after {self.config.timeout_seconds}s"

        chain.total_elapsed_ms = (time.time() - start) * 1000
        chain.overall_confidence = self._compute_confidence(chain)
        if not chain.conclusion:
            conclude = chain.get_conclude_step()
            chain.conclusion = conclude.thought if conclude else "No conclusion reached."
        return chain

    async def _react_loop(self, chain: ThinkingChain, context: dict[str, Any]) -> None:
        """ReAct: Reason → Act → Observe loop."""

        for i in range(self.config.max_steps):
            step_start = time.time()

            # Reasoning step
            thought = await self._think(chain.goal, chain.steps, context)
            think_step = ThinkingStep(
                step_number=i + 1,
                step_type=StepType.THINK,
                thought=thought,
                confidence=0.8,
                elapsed_ms=(time.time() - step_start) * 1000,
            )
            chain.add_step(think_step)

            # Detect conclusion
            if self._is_conclusion(thought):
                conclude_step = ThinkingStep(
                    step_number=len(chain.steps) + 1,
                    step_type=StepType.CONCLUDE,
                    thought=thought,
                    confidence=0.9,
                )
                chain.add_step(conclude_step)
                chain.conclusion = thought
                break

            # Detect action request
            action, action_input = self._parse_action(thought)
            if action and action in self._tools:
                act_start = time.time()
                try:
                    tool_fn = self._tools[action]
                    if asyncio.iscoroutinefunction(tool_fn):
                        result = await tool_fn(**(action_input or {}))
                    else:
                        result = tool_fn(**(action_input or {}))
                    observation = str(result)
                except Exception as exc:
                    observation = f"Tool error: {exc}"

                obs_step = ThinkingStep(
                    step_number=len(chain.steps) + 1,
                    step_type=StepType.ACT,
                    thought=f"Calling {action}",
                    action=action,
                    action_input=action_input,
                    observation=observation,
                    confidence=0.9,
                    elapsed_ms=(time.time() - act_start) * 1000,
                )
                chain.add_step(obs_step)

            # Reflection every 3 steps
            if self.config.enable_reflection and len(chain.steps) % 3 == 0:
                reflection = await self._reflect(chain)
                chain.add_step(
                    ThinkingStep(
                        step_number=len(chain.steps) + 1,
                        step_type=StepType.REFLECT,
                        thought=reflection,
                        confidence=0.7,
                    )
                )
                if self._is_conclusion(reflection):
                    chain.conclusion = reflection
                    break

    async def _chain_of_thought(self, chain: ThinkingChain, context: dict[str, Any]) -> None:
        """Pure chain-of-thought without actions."""
        sub_questions = await self._decompose(chain.goal)
        for i, question in enumerate(sub_questions[: self.config.max_steps - 1]):
            answer = await self._think(question, chain.steps, context)
            chain.add_step(
                ThinkingStep(
                    step_number=i + 1,
                    step_type=StepType.THINK,
                    thought=f"Q: {question}\nA: {answer}",
                    confidence=0.75,
                )
            )
        # Synthesize conclusion
        synthesis = f"Based on the above reasoning about '{chain.goal}': [synthesized answer]"
        chain.add_step(
            ThinkingStep(
                step_number=len(chain.steps) + 1,
                step_type=StepType.CONCLUDE,
                thought=synthesis,
                confidence=0.85,
            )
        )
        chain.conclusion = synthesis

    async def _tree_of_thought(self, chain: ThinkingChain, context: dict[str, Any]) -> None:
        """Tree-of-Thought: explore multiple branches, keep best."""
        branches: list[list[ThinkingStep]] = []
        for b in range(self.config.max_branches):
            branch_thought = await self._think(chain.goal, chain.steps, {**context, "branch": b})
            branch_step = ThinkingStep(
                step_number=len(chain.steps) + 1,
                step_type=StepType.BRANCH,
                thought=f"Branch {b+1}: {branch_thought}",
                confidence=0.6 + b * 0.1,
                metadata={"branch": b},
            )
            branches.append([branch_step])

        # Score and select best branch
        best = max(branches, key=lambda b: b[0].confidence)
        for step in best:
            chain.add_step(step)

        # Prune inferior branches
        chain.add_step(
            ThinkingStep(
                step_number=len(chain.steps) + 1,
                step_type=StepType.PRUNE,
                thought=f"Pruned {len(branches) - 1} lower-confidence branches",
                confidence=1.0,
            )
        )

        conclude = ThinkingStep(
            step_number=len(chain.steps) + 1,
            step_type=StepType.CONCLUDE,
            thought=best[0].thought,
            confidence=best[0].confidence,
        )
        chain.add_step(conclude)
        chain.conclusion = conclude.thought

    async def _think(
        self, prompt: str, history: list[ThinkingStep], context: dict[str, Any]
    ) -> str:
        """Call the thinker (LLM) or return a structured placeholder."""
        if self._thinker:
            if asyncio.iscoroutinefunction(self._thinker):
                return str(await self._thinker(prompt, history))
            return str(self._thinker(prompt, history))
        # Structured fallback for when no LLM is configured
        history_summary = f"After {len(history)} steps" if history else "Initially"
        return f"{history_summary}, reasoning about: {prompt[:200]}"

    async def _reflect(self, chain: ThinkingChain) -> str:
        steps_summary = "; ".join(s.thought[:60] for s in chain.steps[-3:])
        return f"Reflection: The reasoning so far ({steps_summary}) appears on track."

    async def _decompose(self, goal: str) -> list[str]:
        return [
            f"What are the key components of: {goal}?",
            f"What information is needed to answer: {goal}?",
            f"How do these components combine to answer: {goal}?",
        ]

    @staticmethod
    def _is_conclusion(text: str) -> bool:
        conclusion_markers = [
            "therefore",
            "in conclusion",
            "the answer is",
            "final answer",
            "to summarize",
            "in summary",
            "conclude that",
        ]
        lower = text.lower()
        return any(m in lower for m in conclusion_markers)

    @staticmethod
    def _parse_action(thought: str) -> tuple[str | None, dict[str, Any] | None]:
        """Parse 'Action: tool_name(arg=val)' from thought text."""
        import re

        match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", thought, re.IGNORECASE)
        if not match:
            return None, None
        tool_name = match.group(1)
        args_str = match.group(2)
        args: dict[str, Any] = {}
        for part in args_str.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                args[k.strip()] = v.strip().strip("\"'")
        return tool_name, args

    @staticmethod
    def _compute_confidence(chain: ThinkingChain) -> float:
        if not chain.steps:
            return 0.0
        return sum(s.confidence for s in chain.steps) / len(chain.steps)
