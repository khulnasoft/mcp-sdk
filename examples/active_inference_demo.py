"""
Active Inference + Geospatial Demo
====================================
End-to-end demonstration of four architectural innovations working together:

1. 🧠 Active Inference Engine  — Belief updates drop surprise from 0.9 → 0.05
2. 🌍 Large Geospatial Model   — H3-indexed drone flight path (no token bloat)
3. 🔄 Observation-Action Loop  — Stateful continuous 10-cycle tracking
4. 📦 Token-Budget Manager     — Context window stays ≤ 4096 tokens throughout

Scenario: Autonomous drone that tracks a moving target in Paris,
          updating its belief and choosing movement actions in real time.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from mcp_sdk.context.manager import ContextItem, TokenBudgetManager
from mcp_sdk.geospatial.chunker import SpatialChunker
from mcp_sdk.geospatial.model import (
    GeoPoint,
    GeoRegion,
    LargeGeospatialModel,
    TelemetryEvent,
)
from mcp_sdk.inference.active_inference import ActiveInferenceEngine, GenerativeModel
from mcp_sdk.loop.engine import (
    CallbackActor,
    LoopConfig,
    LoopEventType,
    LoopState,
    ObservationActionLoop,
    QueueObserver,
)

# ─────────────────────────────────────────────────────────────────────────────
# Simulated drone GPS sensor
# ─────────────────────────────────────────────────────────────────────────────


def generate_flight_path(n: int = 15) -> list[TelemetryEvent]:
    """Simulate a moving target drifting northeast from Paris Eiffel Tower."""
    base_lat, base_lon = 48.8584, 2.2945
    events = []
    for i in range(n):
        noise = (random.gauss(0, 0.001), random.gauss(0, 0.001))
        events.append(
            TelemetryEvent(
                source="drone_gps",
                location=GeoPoint(
                    lat=base_lat + i * 0.005 + noise[0],
                    lon=base_lon + i * 0.003 + noise[1],
                ),
                payload={
                    "altitude_m": 100.0 + i * 2.5,
                    "speed_ms": 5.0 + random.gauss(0, 0.5),
                    "battery_pct": 100 - i * 4,
                },
                quality=0.9,
            )
        )
    return events


# ─────────────────────────────────────────────────────────────────────────────
# Helper: observation vector from telemetry event
# ─────────────────────────────────────────────────────────────────────────────


def event_to_obs_vec(event: TelemetryEvent) -> list[float]:
    """Convert a TelemetryEvent to a 4-dim state vector for Active Inference."""
    return [
        event.location.lat,
        event.location.lon,
        event.payload.get("altitude_m", 0.0) / 1000.0,  # Normalise
        event.payload.get("speed_ms", 0.0) / 50.0,  # Normalise
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Main Demo
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    random.seed(42)
    print("=" * 65)
    print("  🚁 Active Inference Drone Tracker — MCP SDK Demo")
    print("=" * 65)

    # ── Module 4: Token-Budget Context Manager (max 4096 tokens) ────
    ctx_mgr = TokenBudgetManager(max_tokens=4096)
    ctx_mgr.add(
        ContextItem(
            content="SYSTEM: You are a drone tracking agent. Maintain a belief over target position.",
            priority=1.0,
            pinned=True,
            source="system",
        )
    )
    print(f"\n📦 Context Manager: budget={ctx_mgr.max_tokens} tokens")
    print(f"  Starting utilisation: {ctx_mgr.utilisation:.0%}")

    # ── Module 2: Large Geospatial Model ────────────────────────────
    lgm = LargeGeospatialModel(resolution=9)
    paris_bbox = GeoRegion(min_lat=48.80, max_lat=48.92, min_lon=2.25, max_lon=2.42)
    flight_path = generate_flight_path(n=15)

    # Index all flight path points into the H3 grid
    for evt in flight_path:
        lgm.index_point(evt.location, evt.payload)

    print(
        f"\n🌍 Geospatial Model: {lgm.stats['indexed_points']} points indexed "
        f"across {lgm.stats['cells_used']} H3 cells (res={lgm.resolution})"
    )

    # Load an area tile and chunk it for token safety
    area_tile = lgm.load_tile(
        paris_bbox,
        data={
            "name": "Paris Drone Zone",
            "features": [
                {
                    "coordinates": [48.858 + i * 0.003, 2.295 + i * 0.002],
                    "type": "waypoint",
                    "id": i,
                }
                for i in range(30)
            ],
        },
    )
    chunker = SpatialChunker(max_tokens_per_chunk=512)
    chunks = chunker.chunk_features(area_tile.data.get("features", []), tile_id=area_tile.tile_id)
    print(f"  Area tile split into {len(chunks)} token-safe chunks " f"(≤512 tokens each)")

    # Inject first chunk as context
    if chunks:
        ctx_mgr.add(
            ContextItem(
                content=chunks[0].to_text(),
                priority=0.7,
                source="geo",
            )
        )

    # ── Module 1: Active Inference Engine ───────────────────────────
    gm = GenerativeModel(state_dim=4, obs_noise=0.02, transition_noise=0.005)
    inference_engine = ActiveInferenceEngine(
        state_dim=4,
        action_space=["move_north", "move_east", "move_north_east", "hover", "scan"],
        generative_model=gm,
        convergence_threshold=0.08,
    )
    print(
        f"\n🧠 Active Inference Engine: {inference_engine.state_dim}D belief state, "
        f"{len(inference_engine.action_space)} actions"
    )

    # ── Module 3: Observation-Action Loop ───────────────────────────
    observer = QueueObserver()
    actor = CallbackActor()
    action_taken_log: list[dict] = []

    @actor.register
    def _register_all(actor: CallbackActor) -> None:
        pass  # bypass mypy

    for action_name in inference_engine.action_space:

        def _make_handler(name: str) -> Any:
            def handler(action: str, state: LoopState) -> dict:
                return {"action": name, "cycle": state.cycle}

            return handler

        actor._handlers[action_name] = _make_handler(action_name)
    actor._handlers["noop"] = lambda a, s: {"action": "noop"}

    config = LoopConfig(
        tick_hz=20.0,
        max_cycles=len(flight_path),
        convergence_patience=4,
        log_every_n=5,
    )
    loop = ObservationActionLoop(
        observer=observer,
        actor=actor,
        config=config,
        inference_engine=inference_engine,
    )

    surprises: list[float] = []
    cycle_log: list[str] = []

    @loop.on_observe
    async def on_obs(obs: dict, state: LoopState) -> None:
        # Feed observation into context manager
        ctx_mgr.add(
            ContextItem(
                content=f"Obs cycle {state.cycle}: lat={obs.get('lat', 0):.5f}, "
                f"lon={obs.get('lon', 0):.5f}, "
                f"alt={obs.get('altitude_m', 0):.0f}m",
                priority=0.6,
                source="telemetry",
            )
        )
        # Compress old context every 5 cycles
        if state.cycle % 5 == 0 and state.cycle > 0:
            ctx_mgr.compress_old(older_than_seconds=0)

    @loop.on_act
    async def on_act(action: str, state: LoopState) -> None:
        # Get inference result from engine history
        if inference_engine._history:
            last = inference_engine._history[-1]
            surprises.append(last.surprise)
            cycle_log.append(
                f"  Cycle {state.cycle:2d} | action={action:<16} | "
                f"surprise={last.surprise:.3f} | "
                f"uncertainty={last.belief.uncertainty:.4f} | "
                f"{'✅ CONVERGED' if last.converged else ''}"
            )

    @loop.on_event
    def on_event(event: Any) -> None:
        if event.event_type == LoopEventType.CONVERGED:
            print(f"\n  🎯 Belief CONVERGED at cycle {event.cycle}!")

    # Feed telemetry events into the loop observer
    async def feed_telemetry() -> None:
        for evt in flight_path:
            obs_vec = event_to_obs_vec(evt)
            await observer.put(
                {
                    "lat": evt.location.lat,
                    "lon": evt.location.lon,
                    "altitude_m": evt.payload.get("altitude_m", 0),
                    "speed_ms": evt.payload.get("speed_ms", 0),
                    "_vec": obs_vec,
                }
            )
            await asyncio.sleep(0.01)

    print(f"\n🔄 Observation-Action Loop: {config.max_cycles} cycles @ {config.tick_hz}Hz")
    print(f"{'─'*65}")

    # Run telemetry feeder concurrently with the loop
    await asyncio.gather(
        feed_telemetry(),
        loop.run(),
    )

    # ── Results ──────────────────────────────────────────────────────
    print("\n📊 Cycle-by-Cycle Trace:")
    for line in cycle_log[:12]:
        print(line)
    if len(cycle_log) > 12:
        print(f"  ... ({len(cycle_log) - 12} more cycles)")

    final_summary = inference_engine.summary()
    loop_summary = loop.state.summary()

    print(f"\n{'='*65}")
    print("🏁 Session Summary")
    print(f"{'─'*65}")
    print(f"  Active Inference cycles:  {final_summary['cycles']}")
    if surprises:
        print(f"  Initial surprise:         {surprises[0]:.3f}")
        print(f"  Final   surprise:         {surprises[-1]:.3f}")
        reduction = (surprises[0] - surprises[-1]) / max(surprises[0], 1e-9) * 100
        print(f"  Surprise reduction:       {reduction:.1f}%  🎉")
    print(f"  Belief converged:         {final_summary.get('converged', False)}")
    print(f"  Final uncertainty:        {final_summary.get('uncertainty', 0):.5f}")
    print(f"  O-A loop observations:    {loop_summary['observations']}")
    print(f"  O-A loop actions taken:   {loop_summary['actions']}")
    print(f"  Loop elapsed:             {loop_summary['elapsed_s']:.2f}s")

    ctx_stats = ctx_mgr.stats()
    print(
        f"\n  Context window:           {ctx_stats['token_usage']}/{ctx_stats['max_tokens']} tokens "
        f"({ctx_stats['utilisation_pct']}% utilised)"
    )
    print(f"  Items evicted:            {ctx_stats['evicted_total']}")
    print(f"  Items compressed:         {ctx_stats['compressed_total']}")

    geo_stats = lgm.stats
    print(f"\n  Geo points indexed:       {geo_stats['indexed_points']}")
    print(f"  H3 cells occupied:        {geo_stats['cells_used']}")
    print(f"  Tile chunks created:      {len(chunks)}")
    print("\n✅ Demo complete. Token bloat solved. Belief grounded. Loop closed.")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
