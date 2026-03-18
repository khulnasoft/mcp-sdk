"""Tests for Active Inference Engine."""

import pytest

from mcp_sdk.plugins.active_inference.active_inference import (
    ActiveInferenceEngine,
    BeliefState,
    GenerativeModel,
    InferenceResult,
)


class TestBeliefState:
    def test_uniform_prior(self) -> None:
        b = BeliefState.uniform(dim=3)
        assert len(b.mean) == 3
        assert all(m == 0.0 for m in b.mean)
        assert all(v == 1.0 for v in b.variance)

    def test_bayesian_update_moves_mean(self) -> None:
        b = BeliefState.uniform(dim=2)
        b2 = b.update([3.0, 4.0])
        # Mean should shift toward observation
        assert b2.mean[0] > 0.0
        assert b2.mean[1] > 0.0

    def test_update_reduces_variance(self) -> None:
        b = BeliefState.uniform(dim=2, initial_variance=2.0)
        b2 = b.update([1.0, 1.0], obs_noise=0.5)
        assert b2.variance[0] < b.variance[0]

    def test_update_count_increments(self) -> None:
        b = BeliefState.uniform(dim=2)
        b2 = b.update([1.0, 2.0])
        assert b2.update_count == 1

    def test_update_wrong_dim_raises(self) -> None:
        b = BeliefState.uniform(dim=3)
        with pytest.raises(ValueError):
            b.update([1.0, 2.0])  # Should be dim=3

    def test_free_energy_zero_for_exact_match(self) -> None:
        b = BeliefState(dim=2, mean=[1.0, 2.0], variance=[0.001, 0.001])
        fe = b.free_energy([1.0, 2.0])
        # Small FE when obs matches mean perfectly (only log term remains)
        assert fe < 1.0

    def test_free_energy_high_for_outlier(self) -> None:
        b = BeliefState(dim=2, mean=[0.0, 0.0], variance=[0.01, 0.01])
        fe_normal = b.free_energy([0.1, 0.1])
        fe_outlier = b.free_energy([100.0, 100.0])
        assert fe_outlier > fe_normal

    def test_surprise_bounds(self) -> None:
        b = BeliefState.uniform(dim=3)
        surprise = b.surprise([1.0, 2.0, 3.0])
        assert 0.0 <= surprise <= 1.0

    def test_predict_increases_variance(self) -> None:
        b = BeliefState(dim=2, mean=[0.0, 0.0], variance=[0.1, 0.1])
        b2 = b.predict(transition_noise=0.05)
        assert b2.variance[0] > b.variance[0]
        assert b2.mean == b.mean


class TestGenerativeModel:
    def test_initial_belief(self) -> None:
        model = GenerativeModel(state_dim=4)
        b = model.initial_belief()
        assert b.dim == 4

    def test_transition_move_shifts_state(self) -> None:
        model = GenerativeModel(state_dim=3)
        b = model.initial_belief()
        b2 = model.transition(b, "move")
        assert b2.mean[0] != b.mean[0]

    def test_transition_hover(self) -> None:
        model = GenerativeModel(state_dim=3)
        b = model.initial_belief()
        b2 = model.transition(b, "hover")
        # hover has a small negative effect
        assert b2.mean[0] <= b.mean[0]


class TestActiveInferenceEngine:
    @pytest.fixture
    def engine(self):
        return ActiveInferenceEngine(
            state_dim=3,
            action_space=["move", "hover", "scan"],
            convergence_threshold=0.1,
        )

    @pytest.mark.asyncio
    async def test_single_infer_returns_result(self, engine) -> None:
        result = await engine.infer([0.5, 0.3, 0.1])
        assert isinstance(result, InferenceResult)
        assert result.action in engine.action_space
        assert 0.0 <= result.surprise <= 1.0
        assert result.cycle == 1

    @pytest.mark.asyncio
    async def test_belief_updates_over_cycles(self, engine) -> None:
        obs = [1.0, 2.0, 3.0]
        for _ in range(5):
            await engine.infer(obs)
        final_belief = engine.belief
        # After consistent observations, belief should converge toward obs
        assert final_belief.update_count > 0

    @pytest.mark.asyncio
    async def test_surprise_decreases_with_consistent_obs(self, engine) -> None:
        obs = [0.5, 0.5, 0.5]
        surprises = []
        for _ in range(8):
            result = await engine.infer(obs)
            surprises.append(result.surprise)
        # Surprise should trend downward with consistent observations
        assert surprises[-1] < surprises[0]

    @pytest.mark.asyncio
    async def test_convergence_flag(self, engine) -> None:
        obs = [0.01, 0.01, 0.01]  # Close to prior mean
        for _ in range(15):
            result = await engine.infer(obs)
            if result.converged:
                break
        # Should converge eventually
        assert any(r.converged for r in engine._history) or engine._history[-1].surprise < 0.2

    @pytest.mark.asyncio
    async def test_on_surprise_handler_called(self) -> None:
        received = []
        engine = ActiveInferenceEngine(
            state_dim=2,
            action_space=["a", "b"],
            on_surprise=lambda r: received.append(r.surprise),
        )
        # Force high surprise: large observation vs zero prior
        await engine.infer([50.0, 50.0])
        assert len(received) > 0

    @pytest.mark.asyncio
    async def test_reset(self, engine) -> None:
        await engine.infer([1.0, 1.0, 1.0])
        engine.reset()
        assert engine.cycle == 0
        assert len(engine._history) == 0

    def test_summary_empty(self, engine) -> None:
        s = engine.summary()
        assert s["cycles"] == 0

    @pytest.mark.asyncio
    async def test_summary_after_cycles(self, engine) -> None:
        for _ in range(3):
            await engine.infer([0.5, 0.5, 0.5])
        s = engine.summary()
        assert s["cycles"] == 3
        assert "mean_surprise" in s

    @pytest.mark.asyncio
    async def test_convergence_history(self, engine) -> None:
        for _ in range(4):
            await engine.infer([0.1, 0.1, 0.1])
        history = engine.convergence_history()
        assert len(history) == 4
