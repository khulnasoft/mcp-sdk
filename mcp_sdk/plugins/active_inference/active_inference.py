"""
Active Inference Engine
========================
Implements the Free Energy Principle (Friston, 2010) as a practical
agent belief-update mechanism.

Core loop:
  1. PERCEIVE  — convert raw observation into a percept vector
  2. UPDATE    — update belief state (mean + variance) via Bayesian update
  3. PREDICT   — generate expected next observation from current belief
  4. ACT       — select action that minimises expected free energy (EFE)
  5. EVALUATE  — compute surprise (negative log-likelihood of observation)

Key properties:
- Beliefs are incremental (Kalman-style), never recomputed from scratch
- Action selection is EFE-minimising, not reward-maximising
- Surprise log drives anomaly detection integration
- No LLM required — works purely with numerical belief vectors

Usage::

    engine = ActiveInferenceEngine(state_dim=4, action_space=["move", "hover", "scan"])

    for obs in sensor_stream:
        result = await engine.infer(obs)
        print(result.action, result.surprise, result.belief.mean)
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, Field

from mcp_sdk.memory.scaffold import ScaffoldManager

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Belief State — Gaussian distribution over world states
# ─────────────────────────────────────────────────────────────────────────────


class BeliefState(BaseModel):
    """
    A Gaussian belief over a D-dimensional world state.

    `mean` is the agent's best estimate of the current state.
    `variance` tracks uncertainty (high → less confident).
    `precision` = 1/variance, used in free energy computations.
    """

    dim: int = Field(ge=1)
    mean: list[float]
    variance: list[float]
    timestamp: float = Field(default_factory=time.time)
    update_count: int = 0

    @classmethod
    def uniform(cls, dim: int, initial_variance: float = 1.0) -> BeliefState:
        """Create a uniform (uninformed) prior."""
        return cls(
            dim=dim,
            mean=[0.0] * dim,
            variance=[initial_variance] * dim,
        )

    @property
    def precision(self) -> list[float]:
        return [1.0 / max(v, 1e-9) for v in self.variance]

    @property
    def uncertainty(self) -> float:
        """Mean variance across all dimensions."""
        return sum(self.variance) / self.dim

    def update(self, observation: list[float], obs_noise: float = 0.5) -> BeliefState:
        """
        Bayesian (Kalman) belief update.

        posterior_mean = (prior_precision * prior_mean + obs_precision * obs) /
                         (prior_precision + obs_precision)
        """
        if len(observation) != self.dim:
            raise ValueError(f"Observation dim {len(observation)} ≠ belief dim {self.dim}")

        new_mean: list[float] = []
        new_var: list[float] = []
        obs_noise = max(obs_noise, 1e-9)

        for i in range(self.dim):
            prior_prec = 1.0 / max(self.variance[i], 1e-9)
            obs_prec = 1.0 / obs_noise
            post_prec = prior_prec + obs_prec
            post_mean = (prior_prec * self.mean[i] + obs_prec * observation[i]) / post_prec
            post_var = 1.0 / post_prec
            new_mean.append(post_mean)
            new_var.append(post_var)

        return BeliefState(
            dim=self.dim,
            mean=new_mean,
            variance=new_var,
            update_count=self.update_count + 1,
        )

    def predict(self, transition_noise: float = 0.1) -> BeliefState:
        """
        Prediction step: propagate belief forward in time.
        Adds transition noise (uncertainty grows without observations).
        """
        return BeliefState(
            dim=self.dim,
            mean=list(self.mean),
            variance=[v + transition_noise for v in self.variance],
            update_count=self.update_count,
        )

    def free_energy(self, observation: list[float]) -> float:
        """
        Variational Free Energy ≈ prediction error + complexity cost.
        F = 0.5 * sum_i [ prec_i * (obs_i - mean_i)^2 + log(2π * var_i) ]
        Lower F → observation fits the model better.
        """
        total = 0.0
        for i in range(self.dim):
            diff = observation[i] - self.mean[i]
            prec = self.precision[i]
            total += prec * diff * diff + math.log(2 * math.pi * max(self.variance[i], 1e-9))
        return total * 0.5

    def surprise(self, observation: list[float]) -> float:
        """
        Surprise (Shannon information) for this observation.
        Normalised to [0, 1] via sigmoid-like squash.
        High surprise → unexpected observation → possible anomaly.
        """
        fe = self.free_energy(observation)
        res = 2.0 / (1.0 + math.exp(-fe / self.dim)) - 1.0  # maps (0,∞) → (0,1)
        return max(0.0, res)


# ─────────────────────────────────────────────────────────────────────────────
# Generative Model — prior + likelihood over world states
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class GenerativeModel:
    """
    Lightweight generative model defining:
    - A prior belief over initial world states
    - A transition model P(s_t+1 | s_t, a_t) — linear + noise
    - An observation likelihood P(o | s) — identity by default
    - An action prior (preferred actions in given state)
    """

    state_dim: int
    obs_noise: float = 0.3
    transition_noise: float = 0.05
    prior_variance: float = 1.0

    def initial_belief(self) -> BeliefState:
        return BeliefState.uniform(self.state_dim, self.prior_variance)

    def transition(self, belief: BeliefState, action: str) -> BeliefState:
        """Propagate belief through the transition model given an action."""
        # Simple linear model: action shifts first dimension slightly
        action_effect = {"move": 0.1, "scan": 0.0, "hover": -0.05}.get(action, 0.0)
        shifted_mean = list(belief.mean)
        if shifted_mean:
            shifted_mean[0] += action_effect
        return BeliefState(
            dim=belief.dim,
            mean=shifted_mean,
            variance=[v + self.transition_noise for v in belief.variance],
            update_count=belief.update_count,
        )

    def observation_likelihood(self, state: list[float]) -> list[float]:
        """O = S (identity observation model with noise)."""
        # In more complex models, this would be a learned emission matrix
        return state


# ─────────────────────────────────────────────────────────────────────────────
# Inference result
# ─────────────────────────────────────────────────────────────────────────────


class InferenceResult(BaseModel):
    """Output of one active inference cycle."""

    cycle: int
    action: str
    belief: BeliefState
    surprise: float = Field(ge=0.0, le=1.0)
    free_energy: float
    observation: list[float]
    elapsed_ms: float = 0.0
    converged: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Active Inference Engine
# ─────────────────────────────────────────────────────────────────────────────


class ActiveInferenceEngine:
    """
    Stateful active inference engine for MCP agents.

    Replaces stateless tool-call guessing with a continuous belief-update
    loop grounded in Friston's Free Energy Principle.

    Example::

        engine = ActiveInferenceEngine(
            state_dim=4,
            action_space=["move_north", "move_south", "hover", "scan"],
        )

        # Wire to an observation stream
        async for obs in sensor_stream:
            result = await engine.infer(obs)
            print(f"Action: {result.action} | Surprise: {result.surprise:.2f}")
            if result.converged:
                print("Belief converged — agent is oriented")
                break
    """

    def __init__(
        self,
        state_dim: int,
        action_space: list[str],
        generative_model: GenerativeModel | None = None,
        convergence_threshold: float = 0.05,
        obs_noise: float = 0.3,
        on_surprise: Callable[[InferenceResult], Any] | None = None,
        scaffold: ScaffoldManager | None = None,
    ) -> None:
        self.state_dim = state_dim
        self.action_space = action_space
        self.model = generative_model or GenerativeModel(state_dim=state_dim, obs_noise=obs_noise)
        self.convergence_threshold = convergence_threshold
        self._on_surprise = on_surprise
        self.scaffold = scaffold

        self._belief = self.model.initial_belief()
        self._cycle = 0
        self._last_action = action_space[0] if action_space else "noop"
        self._history: list[InferenceResult] = []

    @property
    def belief(self) -> BeliefState:
        return self._belief

    @property
    def cycle(self) -> int:
        return self._cycle

    async def infer(self, observation: list[float]) -> InferenceResult:
        """
        Run one active inference cycle:
        1. Compute surprise against current belief
        2. Update belief with new observation (Bayesian update)
        3. Select the action that minimises EFE across all candidates
        4. Transition belief forward under chosen action
        """
        t0 = time.time()
        self._cycle += 1

        # Step 1: Compute surprise BEFORE update (how unexpected was this obs?)
        surprise = self._belief.surprise(observation)
        fe = self._belief.free_energy(observation)

        # Step 2: Bayesian belief update
        updated_belief = self._belief.update(observation, obs_noise=self.model.obs_noise)

        # Update Scaffold if present
        if self.scaffold:
            self.scaffold.update_belief(
                entity="ego_state",
                description=f"Mean state: {[round(m, 2) for m in updated_belief.mean]}",
                confidence=1.0 - updated_belief.uncertainty,
                source="inference_cycle",
            )
            if surprise > 0.6:
                self.scaffold.record_anomaly(
                    f"High surprise ({surprise:.2f}) at cycle {self._cycle}"
                )

        # Step 3: Action selection — minimise Expected Free Energy (EFE)
        # EFE(a) ≈ free_energy after transition under action a + epistemic value
        best_action = self._select_action(updated_belief)

        # Step 4: Transition belief forward under chosen action
        next_belief = self.model.transition(updated_belief, best_action)
        self._belief = next_belief
        self._last_action = best_action

        converged = surprise < self.convergence_threshold

        result = InferenceResult(
            cycle=self._cycle,
            action=best_action,
            belief=updated_belief,
            surprise=surprise,
            free_energy=fe,
            observation=observation,
            elapsed_ms=(time.time() - t0) * 1000,
            converged=converged,
            metadata={"uncertainty": updated_belief.uncertainty},
        )
        self._history.append(result)

        if surprise > 0.7 and self._on_surprise:
            try:
                coro = self._on_surprise(result)
                if asyncio.iscoroutine(coro):
                    await coro
            except Exception as exc:
                logger.warning("on_surprise handler failed", error=str(exc))

        logger.debug(
            "Inference cycle",
            cycle=self._cycle,
            action=best_action,
            surprise=f"{surprise:.3f}",
            converged=converged,
        )
        return result

    def _select_action(self, belief: BeliefState) -> str:
        """
        Select action that minimises expected free energy.
        EFE(a) = -epistemic_value(a) + instrumental_value(a)

        For each candidate action, we simulate the transition and compare
        the predicted uncertainty reduction (epistemic) to state alignment.
        """
        best_action = self._last_action
        best_efe = float("inf")

        for action in self.action_space:
            candidate_belief = self.model.transition(belief, action)
            # Epistemic value: uncertainty reduction
            epistemic = belief.uncertainty - candidate_belief.uncertainty
            # Instrumental: how close to target (zero-mean prior = desired state)
            instrumental = sum(abs(m) for m in candidate_belief.mean) / self.state_dim
            efe = instrumental - epistemic * 2.0  # weight epistemic more

            if efe < best_efe:
                best_efe = efe
                best_action = action

        return best_action

    def reset(self) -> None:
        """Reset to initial prior belief and cycle counter."""
        self._belief = self.model.initial_belief()
        self._cycle = 0
        self._history.clear()

    def convergence_history(self) -> list[float]:
        """Return surprise values over time — should trend toward 0."""
        return [r.surprise for r in self._history]

    def summary(self) -> dict[str, Any]:
        if not self._history:
            return {"cycles": 0}
        surprises = self.convergence_history()
        return {
            "cycles": self._cycle,
            "final_surprise": surprises[-1] if surprises else 0,
            "mean_surprise": sum(surprises) / len(surprises),
            "converged": self._history[-1].converged if self._history else False,
            "uncertainty": self._belief.uncertainty,
        }
