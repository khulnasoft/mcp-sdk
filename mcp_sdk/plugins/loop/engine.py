"""
Observation-Action Loop
========================
Replaces isolated stateless tool calls with a continuous, stateful
perception-action cycle — the key architectural shift enabling real-world
environmental awareness in agents.

Components:
- ObservationActionLoop — Long-lived async task running perception→action cycles
- LoopState             — Mutable world-state accumulating across cycles
- BaseObserver          — Abstract sensor / stream source
- BaseActor             — Abstract action executor
- EffectModel           — Lightweight forward model for action prediction
- LoopEvent             — Observable events emitted by the loop

The loop integrates with ActiveInferenceEngine when available, otherwise
uses a simple rule-based action selection fallback.

Usage::

    loop = ObservationActionLoop(config=LoopConfig(tick_hz=2.0, max_cycles=50))

    @loop.on_observe
    async def handle_obs(obs, state):
        print(f"Cycle {state.cycle}: {obs}")

    @loop.on_act
    async def post_act(action, state):
        print(f"  Action taken: {action}")

    await loop.run()
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────────────────────


class LoopEventType(StrEnum):
    STARTED = "started"
    TICK = "tick"
    OBSERVED = "observed"
    ACTION_TAKEN = "action_taken"
    CONVERGED = "converged"
    ERROR = "error"
    STOPPED = "stopped"


class LoopEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: LoopEventType
    cycle: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
# Loop State — mutable world model shared across cycles
# ─────────────────────────────────────────────────────────────────────────────


class LoopState(BaseModel):
    """Mutable world-state snapshot persisted across perception-action cycles."""

    loop_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    cycle: int = 0
    started_at: float = Field(default_factory=time.time)

    # Last observation received
    last_observation: dict[str, Any] | None = None
    # Last action taken
    last_action: str | None = None
    # Accumulated action history (capped at 100)
    action_history: list[dict[str, Any]] = Field(default_factory=list)
    # World state accumulated over time
    world_model: dict[str, Any] = Field(default_factory=dict)
    # Running metrics
    total_observations: int = 0
    total_actions: int = 0
    errors: int = 0
    converged: bool = False

    class Config:
        arbitrary_types_allowed = True

    def record_observation(self, obs: dict[str, Any]) -> None:
        self.last_observation = obs
        self.total_observations += 1
        # Merge into world model (most recent values win)
        self.world_model.update(obs)

    def record_action(self, action: str, metadata: dict[str, Any] | None = None) -> None:
        self.last_action = action
        self.total_actions += 1
        record = {"cycle": self.cycle, "action": action, **(metadata or {})}
        self.action_history.append(record)
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "cycles": self.cycle,
            "observations": self.total_observations,
            "actions": self.total_actions,
            "errors": self.errors,
            "converged": self.converged,
            "elapsed_s": round(self.elapsed_seconds, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Loop Config
# ─────────────────────────────────────────────────────────────────────────────


class LoopConfig(BaseModel):
    tick_hz: float = Field(default=1.0, ge=0.01, le=100.0, description="Cycles per second")
    max_cycles: int = Field(default=0, ge=0, description="0 = run forever until stopped")
    error_strategy: str = Field(default="skip", description="One of: skip, stop, retry")
    max_retries: int = 3
    convergence_check: bool = True
    convergence_patience: int = 5  # Cycles without state change → converged
    log_every_n: int = 10

    @property
    def tick_interval_s(self) -> float:
        return 1.0 / self.tick_hz


# ─────────────────────────────────────────────────────────────────────────────
# Observers
# ─────────────────────────────────────────────────────────────────────────────


class BaseObserver:
    """Abstract base for all observation sources."""

    async def observe(self) -> dict[str, Any] | None:
        """Return a new observation dict, or None if nothing available yet."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release resources."""


class QueueObserver(BaseObserver):
    """Wraps an asyncio.Queue as an observation source."""

    def __init__(self, queue: asyncio.Queue | None = None) -> None:
        self._queue: asyncio.Queue = queue or asyncio.Queue()

    async def observe(self) -> dict[str, Any] | None:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def put(self, observation: dict[str, Any]) -> None:
        await self._queue.put(observation)

    @property
    def pending(self) -> int:
        return self._queue.qsize()


class CallbackObserver(BaseObserver):
    """Calls a user-provided async function to get each observation."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        self._fn = fn

    async def observe(self) -> dict[str, Any] | None:
        result = self._fn()
        if asyncio.iscoroutine(result):
            result = await result
        if result is None:
            return None
        return result if isinstance(result, dict) else {"value": result}


class CompositeObserver(BaseObserver):
    """Merges observations from multiple sources into a single stream."""

    def __init__(self, observers: list[BaseObserver]) -> None:
        self._observers = observers

    async def observe(self) -> dict[str, Any] | None:
        all_obs: dict[str, Any] = {}
        for obs in self._observers:
            result = await obs.observe()
            if result:
                all_obs.update(result)
        return all_obs if all_obs else None

    async def close(self) -> None:
        for obs in self._observers:
            await obs.close()


# ─────────────────────────────────────────────────────────────────────────────
# Actors
# ─────────────────────────────────────────────────────────────────────────────


class BaseActor:
    """Abstract base for all action executors."""

    async def act(self, action: str, state: LoopState, **kwargs: Any) -> dict[str, Any]:
        """Execute action, return effect dict."""
        raise NotImplementedError


class CallbackActor(BaseActor):
    """Dispatches actions to a registry of async callback functions."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._default: Callable[..., Any] | None = None

    def register(self, action: str, fn: Callable[..., Any]) -> None:
        self._handlers[action] = fn

    def set_default(self, fn: Callable[..., Any]) -> None:
        self._default = fn

    async def act(self, action: str, state: LoopState, **kwargs: Any) -> dict[str, Any]:
        handler = self._handlers.get(action, self._default)
        if handler is None:
            return {"action": action, "status": "no_handler"}
        result = handler(action, state, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result if isinstance(result, dict) else {"result": result}


class EffectModel:
    """
    Lightweight forward model: given current state + action → predicted next-state delta.

    Used by Active Inference for action selection (EFE minimisation).
    Override `predict` to implement domain-specific transition dynamics.
    """

    def predict(self, state: LoopState, action: str) -> dict[str, Any]:
        """Return predicted world-model delta after taking `action`."""
        # Default: actions that contain "move" shift a nominal position
        delta: dict[str, Any] = {"last_action": action}
        if "move" in action.lower():
            pos = state.world_model.get("position", [0.0, 0.0])
            direction = action.split("_")[-1] if "_" in action else "north"
            offsets = {
                "north": (0.01, 0),
                "south": (-0.01, 0),
                "east": (0, 0.01),
                "west": (0, -0.01),
            }
            dlat, dlon = offsets.get(direction, (0, 0))
            delta["position"] = [pos[0] + dlat, pos[1] + dlon]
        return delta


# ─────────────────────────────────────────────────────────────────────────────
# Main Loop Engine
# ─────────────────────────────────────────────────────────────────────────────


class ObservationActionLoop:
    """
    Stateful continuous perception-action cycle.

    Replaces one-shot stateless tool calls with a long-lived async task
    that maintains a running world model and selects actions based on
    accumulated state — matching the architecture of modern autonomous systems.

    Example::

        loop = ObservationActionLoop(
            observer=QueueObserver(),
            actor=CallbackActor(),
            config=LoopConfig(tick_hz=2.0, max_cycles=20),
        )

        @loop.on_observe
        async def handle(obs, state):
            ...

        await loop.run()
        print(loop.state.summary())
    """

    def __init__(
        self,
        observer: BaseObserver | None = None,
        actor: BaseActor | None = None,
        config: LoopConfig | None = None,
        action_selector: Callable[[LoopState], str] | None = None,
        inference_engine: Any | None = None,  # ActiveInferenceEngine
        effect_model: EffectModel | None = None,
    ) -> None:
        self.observer = observer or QueueObserver()
        self.actor = actor or CallbackActor()
        self.config = config or LoopConfig()
        self._action_selector = action_selector
        self._inference_engine = inference_engine
        self._effect_model = effect_model or EffectModel()
        self.state = LoopState()

        self._observe_handlers: list[Callable[[dict[str, Any], LoopState], Any]] = []
        self._act_handlers: list[Callable[[str, LoopState], Any]] = []
        self._event_handlers: list[Callable[[LoopEvent], Any]] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._no_change_cycles = 0

    def on_observe(self, fn: Callable) -> Callable:
        """Decorator: register a handler called after each observation."""
        self._observe_handlers.append(fn)
        return fn

    def on_act(self, fn: Callable) -> Callable:
        """Decorator: register a handler called after each action."""
        self._act_handlers.append(fn)
        return fn

    def on_event(self, fn: Callable) -> Callable:
        """Decorator: register a handler for all loop events."""
        self._event_handlers.append(fn)
        return fn

    async def run(self) -> LoopState:
        """Start the loop and run until complete or stopped."""
        self._running = True
        await self._emit(LoopEvent(event_type=LoopEventType.STARTED))
        logger.info(
            "O-A loop started",
            loop_id=self.state.loop_id,
            tick_hz=self.config.tick_hz,
            max_cycles=self.config.max_cycles,
        )
        try:
            while self._running:
                cycle_start = time.time()
                self.state.cycle += 1

                await self._tick()

                # Check termination conditions
                if self.config.max_cycles and self.state.cycle >= self.config.max_cycles:
                    break
                if self.state.converged:
                    await self._emit(
                        LoopEvent(event_type=LoopEventType.CONVERGED, cycle=self.state.cycle)
                    )
                    break

                # Throttle to tick_hz
                elapsed = time.time() - cycle_start
                sleep_time = max(0.0, self.config.tick_interval_s - elapsed)
                if sleep_time:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("O-A loop cancelled", loop_id=self.state.loop_id)
        finally:
            self._running = False
            await self._emit(
                LoopEvent(
                    event_type=LoopEventType.STOPPED,
                    cycle=self.state.cycle,
                    payload=self.state.summary(),
                )
            )
            await self.observer.close()

        logger.info("O-A loop finished", **self.state.summary())
        return self.state

    async def start_background(self) -> None:
        """Start the loop as a background asyncio task."""
        self._task = asyncio.create_task(self.run(), name=f"oa-loop-{self.state.loop_id}")

    async def stop(self) -> None:
        """Gracefully stop the loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _tick(self) -> None:
        """Execute one perception-action cycle."""
        await self._emit(LoopEvent(event_type=LoopEventType.TICK, cycle=self.state.cycle))

        # ── Perception ────────────────────────────────────────────────
        retries = 0
        observation: dict[str, Any] | None = None
        while retries <= self.config.max_retries:
            try:
                observation = await self.observer.observe()
                break
            except Exception as exc:
                self.state.errors += 1
                logger.warning("Observer error", error=str(exc), cycle=self.state.cycle)
                retries += 1
                if self.config.error_strategy == "stop":
                    self._running = False
                    return

        if observation:
            prev_model = dict(self.state.world_model)
            self.state.record_observation(observation)
            await self._emit(
                LoopEvent(
                    event_type=LoopEventType.OBSERVED, cycle=self.state.cycle, payload=observation
                )
            )
            for h in self._observe_handlers:
                await _maybe_await(h(observation, self.state))

            # Convergence check: no world-model change for N cycles
            if self.config.convergence_check and prev_model == self.state.world_model:
                self._no_change_cycles += 1
                if self._no_change_cycles >= self.config.convergence_patience:
                    self.state.converged = True
            else:
                self._no_change_cycles = 0

        # ── Action selection ──────────────────────────────────────────
        action = await self._select_action()

        # ── Action execution ──────────────────────────────────────────
        try:
            effect = await self.actor.act(action, self.state)
            self.state.record_action(action, effect)
            await self._emit(
                LoopEvent(
                    event_type=LoopEventType.ACTION_TAKEN,
                    cycle=self.state.cycle,
                    payload={"action": action, "effect": effect},
                )
            )
            for h in self._act_handlers:
                await _maybe_await(h(action, self.state))
        except Exception as exc:
            self.state.errors += 1
            logger.error("Actor error", error=str(exc), action=action)
            if self.config.error_strategy == "stop":
                self._running = False

        if self.config.log_every_n and self.state.cycle % self.config.log_every_n == 0:
            logger.info("O-A loop tick", **self.state.summary())

    async def _select_action(self) -> str:
        """Select the next action using inference engine or selector fn."""
        # Priority 1: Active Inference Engine
        if self._inference_engine and self.state.last_observation:
            obs_vec = list(self.state.last_observation.values())
            numeric = [float(v) for v in obs_vec if isinstance(v, (int, float))]
            if numeric:
                # Mock result for simple select if infer is not fully mocked
                try:
                    result = await self._inference_engine.infer(numeric)
                    return result.action
                except:
                    pass

        # Priority 2: Custom selector
        if self._action_selector:
            action = self._action_selector(self.state)
            if asyncio.iscoroutine(action):
                action = await action
            return action

        return "noop"

    async def _emit(self, event: LoopEvent) -> None:
        for h in self._event_handlers:
            await _maybe_await(h(event))


async def _maybe_await(obj: Any) -> Any:
    if asyncio.iscoroutine(obj):
        return await obj
    return obj
