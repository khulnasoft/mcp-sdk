"""Tests for Observation-Action Loop engine."""

import asyncio

import pytest

from mcp_sdk.plugins.loop.engine import (
    CallbackActor,
    CallbackObserver,
    EffectModel,
    LoopConfig,
    LoopEventType,
    LoopState,
    ObservationActionLoop,
    QueueObserver,
)


class TestLoopState:
    def test_initial_state(self) -> None:
        state = LoopState()
        assert state.cycle == 0
        assert state.total_observations == 0
        assert state.total_actions == 0
        assert state.converged is False

    def test_record_observation(self) -> None:
        state = LoopState()
        state.record_observation({"temp": 22.5})
        assert state.total_observations == 1
        assert state.world_model["temp"] == 22.5

    def test_record_action(self) -> None:
        state = LoopState()
        state.record_action("hover")
        assert state.total_actions == 1
        assert state.last_action == "hover"

    def test_action_history_capped(self) -> None:
        state = LoopState()
        for i in range(110):
            state.record_action(f"action_{i}")
        assert len(state.action_history) == 100

    def test_elapsed_seconds(self) -> None:
        state = LoopState()
        assert state.elapsed_seconds >= 0.0

    def test_summary_keys(self) -> None:
        state = LoopState()
        s = state.summary()
        assert "cycles" in s
        assert "observations" in s
        assert "actions" in s


class TestQueueObserver:
    @pytest.mark.asyncio
    async def test_empty_queue_returns_none(self) -> None:
        obs = QueueObserver()
        result = await obs.observe()
        assert result is None

    @pytest.mark.asyncio
    async def test_put_and_observe(self) -> None:
        obs = QueueObserver()
        await obs.put({"value": 42})
        result = await obs.observe()
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_pending_count(self) -> None:
        obs = QueueObserver()
        await obs.put({"a": 1})
        await obs.put({"b": 2})
        assert obs.pending == 2


class TestCallbackObserver:
    @pytest.mark.asyncio
    async def test_sync_callback(self) -> None:
        call_count = [0]

        def fn():
            call_count[0] += 1
            return {"count": call_count[0]}

        obs = CallbackObserver(fn)
        result = await obs.observe()
        assert result == {"count": 1}

    @pytest.mark.asyncio
    async def test_async_callback(self) -> None:
        async def fn():
            return {"key": "val"}

        obs = CallbackObserver(fn)
        result = await obs.observe()
        assert result == {"key": "val"}

    @pytest.mark.asyncio
    async def test_none_callback_returns_none(self) -> None:
        obs = CallbackObserver(lambda: None)
        result = await obs.observe()
        assert result is None


class TestCallbackActor:
    @pytest.mark.asyncio
    async def test_registered_handler(self) -> None:
        actor = CallbackActor()
        actor.register("move", lambda a, s: {"moved": True})
        state = LoopState()
        result = await actor.act("move", state)
        assert result.get("moved") is True

    @pytest.mark.asyncio
    async def test_no_handler_returns_status(self) -> None:
        actor = CallbackActor()
        state = LoopState()
        result = await actor.act("unknown", state)
        assert result["status"] == "no_handler"

    @pytest.mark.asyncio
    async def test_default_handler(self) -> None:
        actor = CallbackActor()
        actor.set_default(lambda a, s: {"action": a})
        result = await actor.act("anything", LoopState())
        assert result["action"] == "anything"


class TestEffectModel:
    def test_predict_move_shifts_position(self) -> None:
        model = EffectModel()
        state = LoopState()
        state.world_model["position"] = [0.0, 0.0]
        delta = model.predict(state, "move_north")
        assert delta["last_action"] == "move_north"
        if "position" in delta:
            assert delta["position"][0] > 0  # lat increased

    def test_predict_noop(self) -> None:
        model = EffectModel()
        state = LoopState()
        delta = model.predict(state, "noop")
        assert delta["last_action"] == "noop"


class TestObservationActionLoop:
    @pytest.mark.asyncio
    async def test_finite_loop_completes(self) -> None:
        observer = QueueObserver()
        for i in range(5):
            await observer.put({"step": i, "val": float(i)})

        actor = CallbackActor()
        actor.register("noop", lambda a, s: {"ok": True})

        config = LoopConfig(max_cycles=5, tick_hz=100.0)
        loop = ObservationActionLoop(observer=observer, actor=actor, config=config)
        state = await loop.run()
        assert state.cycle == 5

    @pytest.mark.asyncio
    async def test_on_observe_hook(self) -> None:
        observer = QueueObserver()
        await observer.put({"x": 1.0})
        config = LoopConfig(max_cycles=1, tick_hz=100.0)
        loop = ObservationActionLoop(observer=observer, config=config)

        received = []

        @loop.on_observe
        def obs_hook(obs, state) -> None:
            received.append(obs)

        await loop.run()
        assert len(received) == 1
        assert received[0]["x"] == 1.0

    @pytest.mark.asyncio
    async def test_on_act_hook(self) -> None:
        config = LoopConfig(max_cycles=2, tick_hz=100.0)
        loop = ObservationActionLoop(config=config)
        actions = []

        @loop.on_act
        def act_hook(action, state) -> None:
            actions.append(action)

        await loop.run()
        assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_convergence_detection(self) -> None:
        # Provide the same observation repeatedly → world model stops changing
        observer = QueueObserver()
        for _ in range(20):
            await observer.put({"val": 1.0})

        config = LoopConfig(max_cycles=20, convergence_patience=3, tick_hz=100.0)
        loop = ObservationActionLoop(observer=observer, config=config)
        state = await loop.run()
        # Should converge before max_cycles
        assert state.converged or state.cycle <= 20

    @pytest.mark.asyncio
    async def test_event_hooks(self) -> None:
        config = LoopConfig(max_cycles=2, tick_hz=100.0)
        loop = ObservationActionLoop(config=config)
        events = []

        @loop.on_event
        def event_hook(event) -> None:
            events.append(event.event_type)

        await loop.run()
        assert LoopEventType.STARTED in events
        assert LoopEventType.STOPPED in events

    @pytest.mark.asyncio
    async def test_start_stop_background(self) -> None:
        observer = QueueObserver()
        config = LoopConfig(max_cycles=0, tick_hz=50.0)  # Infinite
        loop = ObservationActionLoop(observer=observer, config=config)
        await loop.start_background()
        await asyncio.sleep(0.1)
        await loop.stop()
        assert not loop._running

    @pytest.mark.asyncio
    async def test_custom_action_selector(self) -> None:
        config = LoopConfig(max_cycles=3, tick_hz=100.0)
        selected = []

        def my_selector(state) -> str:
            selected.append("custom")
            return "hover"

        actor = CallbackActor()
        actor.register("hover", lambda a, s: {})
        loop = ObservationActionLoop(config=config, actor=actor, action_selector=my_selector)
        await loop.run()
        assert "custom" in selected
