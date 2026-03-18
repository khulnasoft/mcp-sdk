"""Tests for Sequential Thinking Engine."""

import pytest

from mcp_sdk.plugins.thinking.engine import (
    SequentialThinkingEngine,
    StepType,
    ThinkingConfig,
)


class TestThinkingEngine:
    @pytest.fixture
    def engine(self):
        config = ThinkingConfig(max_steps=5, enable_reflection=False, enable_branching=False)
        return SequentialThinkingEngine(config=config)

    @pytest.fixture
    def engine_with_tools(self):
        config = ThinkingConfig(max_steps=5, enable_reflection=False)
        engine = SequentialThinkingEngine(config=config)
        engine.register_tool("calculate", lambda expression: "Result: 42")
        engine.register_tool("search", lambda query: f"Found info about {query}")
        return engine

    @pytest.mark.asyncio
    async def test_basic_react_reasoning(self, engine) -> None:
        chain = await engine.reason("What is the capital of France?", strategy="react")
        assert chain is not None
        assert len(chain.steps) > 0
        assert chain.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_chain_of_thought(self, engine) -> None:
        chain = await engine.reason("Explain quantum entanglement", strategy="cot")
        assert chain is not None
        # CoT should have at least 3 steps (3 sub-questions + conclude)
        assert len(chain.steps) >= 3
        conclude = chain.get_conclude_step()
        assert conclude is not None
        assert conclude.step_type == StepType.CONCLUDE

    @pytest.mark.asyncio
    async def test_tree_of_thought(self, engine) -> None:
        config = ThinkingConfig(max_steps=5, max_branches=2, enable_reflection=False)
        tot_engine = SequentialThinkingEngine(config=config)
        chain = await tot_engine.reason("Best approach to solve P=NP?", strategy="tot")
        assert chain is not None
        types = {s.step_type for s in chain.steps}
        assert StepType.BRANCH in types
        assert StepType.PRUNE in types

    @pytest.mark.asyncio
    async def test_conclusion_detection(self, engine) -> None:
        async def thinker(prompt, history) -> str:
            return "In conclusion, the answer is 42."

        conclusion_engine = SequentialThinkingEngine(
            config=ThinkingConfig(max_steps=5, enable_reflection=False),
            thinker=thinker,
        )
        chain = await conclusion_engine.reason("What is the answer?")
        assert chain.conclusion is not None
        assert "42" in chain.conclusion

    @pytest.mark.asyncio
    async def test_tool_integration(self, engine_with_tools) -> None:
        async def thinker(prompt, history) -> str:
            if not history:
                return "I need to calculate. Action: calculate(expression=2+2)"
            return "In conclusion, the calculation returned 42."

        engine_with_tools._thinker = thinker
        chain = await engine_with_tools.reason("What is 2+2?")
        act_steps = [s for s in chain.steps if s.step_type == StepType.ACT]
        assert len(act_steps) > 0
        assert act_steps[0].action == "calculate"
        assert act_steps[0].observation == "Result: 42"

    @pytest.mark.asyncio
    async def test_reflection_enabled(self) -> None:
        config = ThinkingConfig(max_steps=10, enable_reflection=True)
        engine = SequentialThinkingEngine(config=config)
        chain = await engine.reason("Explain photosynthesis")
        reflect_steps = [s for s in chain.steps if s.step_type == StepType.REFLECT]
        assert len(reflect_steps) > 0

    @pytest.mark.asyncio
    async def test_chain_metadata(self, engine) -> None:
        chain = await engine.reason("Test question", strategy="react")
        assert chain.chain_id != ""
        assert chain.total_elapsed_ms > 0
        assert chain.strategy == "react"

    def test_is_conclusion_detection(self) -> None:
        assert SequentialThinkingEngine._is_conclusion("Therefore, the answer is yes")
        assert SequentialThinkingEngine._is_conclusion("In conclusion, we can see that")
        assert not SequentialThinkingEngine._is_conclusion("Let me think about this more")

    def test_parse_action(self) -> None:
        thought = 'Action: search(query="Python programming")'
        tool, args = SequentialThinkingEngine._parse_action(thought)
        assert tool == "search"
        assert args is not None
        assert "query" in args

    def test_parse_no_action(self) -> None:
        tool, args = SequentialThinkingEngine._parse_action("Just thinking about this")
        assert tool is None
        assert args is None

    @pytest.mark.asyncio
    async def test_to_markdown(self, engine) -> None:
        chain = await engine.reason("Test", strategy="cot")
        md = chain.to_markdown()
        assert "# Thinking Chain" in md
        assert "Strategy" in md
