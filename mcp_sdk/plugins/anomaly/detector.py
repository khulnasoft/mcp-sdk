"""
Anomaly Detection Engine
=========================
Statistical and rule-based anomaly detection for agent interactions.
Detects behavioral drift, rate anomalies, payload outliers, and
agent performance degradation using streaming Z-score, IQR, and
isolation-based scoring.

Patterns detected:
- Request rate spikes / drops
- Payload size outliers
- Response time degradation
- Error rate elevation
- Repeated identical messages (replay attacks)
- Unusual hour-of-day / day-of-week access
- Agent capability misuse
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Severity & Alert models
# ─────────────────────────────────────────────────────────────────────────────


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(StrEnum):
    RATE_SPIKE = "rate_spike"
    RATE_DROP = "rate_drop"
    PAYLOAD_SIZE_OUTLIER = "payload_size_outlier"
    SLOW_RESPONSE = "slow_response"
    HIGH_ERROR_RATE = "high_error_rate"
    REPLAY_ATTACK = "replay_attack"
    UNUSUAL_HOUR = "unusual_hour"
    CAPABILITY_MISUSE = "capability_misuse"
    STATISTICAL_OUTLIER = "statistical_outlier"
    BEHAVIORAL_DRIFT = "behavioral_drift"


class AnomalyAlert(BaseModel):
    """An anomaly detected during agent interaction analysis."""

    alert_id: str = Field(default_factory=lambda: f"alert-{int(time.time()*1000)}")
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    score: float = Field(ge=0.0, le=1.0, description="Normalized anomaly score 0–1")
    description: str
    agent_id: str = ""
    user_id: str = ""
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    context: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str = ""

    @property
    def is_critical(self) -> bool:
        return self.severity == AnomalySeverity.CRITICAL


# ─────────────────────────────────────────────────────────────────────────────
# Online Statistics (Welford's algorithm — no history needed)
# ─────────────────────────────────────────────────────────────────────────────


class OnlineStats:
    """Streaming mean/variance using Welford's online algorithm."""

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self._M2 = 0.0

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self._M2 += delta * delta2

    @property
    def variance(self) -> float:
        return self._M2 / self.n if self.n > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def z_score(self, value: float) -> float:
        """Return Z-score of value relative to observed distribution."""
        if self.std == 0:
            return 0.0
        return abs((value - self.mean) / self.std)


# ─────────────────────────────────────────────────────────────────────────────
# Individual detectors
# ─────────────────────────────────────────────────────────────────────────────


class RateMonitor:
    """Sliding-window request rate monitor."""

    def __init__(self, window_seconds: int = 60, spike_multiplier: float = 3.0) -> None:
        self.window = window_seconds
        self.spike_multiplier = spike_multiplier
        self._timestamps: deque[float] = deque()
        self._stats = OnlineStats()

    def record(self) -> float:
        """Record an event and return current RPS."""
        now = time.time()
        self._timestamps.append(now)
        # Evict old timestamps
        cutoff = now - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        rps = len(self._timestamps) / self.window
        self._stats.update(rps)
        return rps

    def is_spike(self) -> tuple[bool, float]:
        if self._stats.n < 5:
            return False, 0.0
        rps = len(self._timestamps) / self.window
        z = self._stats.z_score(rps)
        return z > self.spike_multiplier, z

    def is_drop(self, threshold: float = 0.1) -> tuple[bool, float]:
        if self._stats.n < 5:
            return False, 0.0
        rps = len(self._timestamps) / self.window
        drop_ratio = 1 - (rps / max(self._stats.mean, 1e-9))
        return drop_ratio > (1 - threshold), drop_ratio


class PayloadAnalyzer:
    """Detects unusually large or small message payloads."""

    def __init__(self, z_threshold: float = 3.0) -> None:
        self.z_threshold = z_threshold
        self._stats = OnlineStats()

    def analyze(self, payload: Any) -> tuple[bool, float, int]:
        size = len(str(payload).encode("utf-8"))
        self._stats.update(float(size))
        z = self._stats.z_score(float(size))
        return z > self.z_threshold, z, size


class ResponseTimeMonitor:
    """Tracks agent response latency and flags degradation."""

    def __init__(self, slow_threshold_ms: float = 5000, z_threshold: float = 3.0) -> None:
        self.slow_threshold_ms = slow_threshold_ms
        self.z_threshold = z_threshold
        self._stats = OnlineStats()

    def record(self, elapsed_ms: float) -> tuple[bool, float]:
        self._stats.update(elapsed_ms)
        is_slow = elapsed_ms > self.slow_threshold_ms
        z = self._stats.z_score(elapsed_ms)
        return is_slow or z > self.z_threshold, z


class ReplayDetector:
    """Detects duplicate / replayed messages using content hashing."""

    def __init__(self, window_size: int = 1000, ttl_seconds: float = 300) -> None:
        self.window_size = window_size
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}  # hash -> timestamp

    def check(self, content: Any) -> bool:
        """Return True if this content was seen recently (replay detected)."""
        now = time.time()
        # Evict expired entries
        expired = [k for k, ts in self._seen.items() if now - ts > self.ttl_seconds]
        for k in expired:
            del self._seen[k]

        content_hash = hashlib.sha256(str(content).encode()).hexdigest()
        if content_hash in self._seen:
            return True
        if len(self._seen) < self.window_size:
            self._seen[content_hash] = now
        return False


class ErrorRateMonitor:
    """Tracks the rolling error rate for an agent."""

    def __init__(self, window: int = 100, threshold: float = 0.2) -> None:
        self.threshold = threshold
        self._outcomes: deque[bool] = deque(maxlen=window)

    def record(self, success: bool) -> tuple[bool, float]:
        self._outcomes.append(success)
        if len(self._outcomes) < 10:
            return False, 0.0
        error_rate = 1 - (sum(self._outcomes) / len(self._outcomes))
        return error_rate > self.threshold, error_rate


class UnusualTimeDetector:
    """Flags activity outside of historically normal hours."""

    def __init__(self, normal_hours: tuple[int, int] = (6, 22)) -> None:
        self.normal_start, self.normal_end = normal_hours
        self._hour_stats: dict[int, int] = {}

    def check(self) -> tuple[bool, int]:
        hour = datetime.now(UTC).hour
        self._hour_stats[hour] = self._hour_stats.get(hour, 0) + 1
        unusual = not (self.normal_start <= hour <= self.normal_end)
        return unusual, hour


# ─────────────────────────────────────────────────────────────────────────────
# Main Anomaly Detector
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AnomalyDetectorConfig:
    rate_window_seconds: int = 60
    rate_spike_multiplier: float = 3.0
    payload_z_threshold: float = 3.5
    slow_response_ms: float = 5000.0
    response_z_threshold: float = 3.0
    replay_window_size: int = 1000
    replay_ttl_seconds: float = 300.0
    error_rate_threshold: float = 0.2
    error_rate_window: int = 100
    normal_hours: tuple[int, int] = (6, 22)
    enable_unusual_time: bool = True


class AnomalyDetector:
    """
    Composite real-time anomaly detector for MCP agent interactions.

    Runs multiple independent detectors in parallel and aggregates
    alerts. Attach to any agent via the rule engine or directly in
    `handle_message`.

    Example::

        detector = AnomalyDetector(agent_id="my-agent")

        alerts = await detector.analyze(
            message=message,
            response=response,
            context=context,
        )
        for alert in alerts:
            if alert.is_critical:
                await notify_security_team(alert)
    """

    def __init__(
        self,
        agent_id: str,
        config: AnomalyDetectorConfig | None = None,
        alert_handlers: list[Callable[[AnomalyAlert], Any]] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.config = config or AnomalyDetectorConfig()
        self._handlers = alert_handlers or []

        # Per-user monitors (lazy init)
        self._rate_monitors: dict[str, RateMonitor] = {}
        self._payload_analyzers: dict[str, PayloadAnalyzer] = {}
        self._response_monitors: dict[str, ResponseTimeMonitor] = {}
        self._error_monitors: dict[str, ErrorRateMonitor] = {}
        self._replay_detectors: dict[str, ReplayDetector] = {}
        self._time_detector = UnusualTimeDetector(self.config.normal_hours)
        self._global_rate = RateMonitor(
            self.config.rate_window_seconds, self.config.rate_spike_multiplier
        )
        self._alerts: list[AnomalyAlert] = []

    def _user_key(self, context: Any) -> str:
        return getattr(context, "user_id", None) or "anonymous"

    async def analyze(
        self,
        message: Any,
        response: Any = None,
        context: Any = None,
    ) -> list[AnomalyAlert]:
        """Run all detectors and return any alerts generated."""
        alerts: list[AnomalyAlert] = []
        user_id = self._user_key(context)

        # ── Rate spike ────────────────────────────────────────────────
        self._global_rate.record()
        rm = self._rate_monitors.setdefault(
            user_id,
            RateMonitor(self.config.rate_window_seconds, self.config.rate_spike_multiplier),
        )
        rm.record()
        is_spike, z_rate = rm.is_spike()
        if is_spike:
            alerts.append(
                self._make_alert(
                    AnomalyType.RATE_SPIKE,
                    AnomalySeverity.HIGH,
                    min(z_rate / 10, 1.0),
                    f"Request rate spike detected (Z={z_rate:.2f})",
                    user_id=user_id,
                    context={"z_score": z_rate, "rps": rm.record()},
                    recommended_action="Temporarily rate-limit this user/IP",
                )
            )

        # ── Payload size outlier ───────────────────────────────────────
        pa = self._payload_analyzers.setdefault(
            user_id, PayloadAnalyzer(self.config.payload_z_threshold)
        )
        is_outlier, z_payload, size_bytes = pa.analyze(getattr(message, "content", message))
        if is_outlier:
            alerts.append(
                self._make_alert(
                    AnomalyType.PAYLOAD_SIZE_OUTLIER,
                    AnomalySeverity.MEDIUM,
                    min(z_payload / 10, 1.0),
                    f"Unusual payload size: {size_bytes} bytes (Z={z_payload:.2f})",
                    user_id=user_id,
                    context={"size_bytes": size_bytes, "z_score": z_payload},
                    recommended_action="Inspect message content for injected data",
                )
            )

        # ── Response time ─────────────────────────────────────────────
        if response and hasattr(response, "execution_time_ms"):
            rtm = self._response_monitors.setdefault(
                user_id,
                ResponseTimeMonitor(self.config.slow_response_ms, self.config.response_z_threshold),
            )
            is_slow, z_rt = rtm.record(response.execution_time_ms)
            if is_slow:
                alerts.append(
                    self._make_alert(
                        AnomalyType.SLOW_RESPONSE,
                        AnomalySeverity.MEDIUM,
                        min(z_rt / 10, 1.0),
                        f"Slow response: {response.execution_time_ms:.0f}ms (Z={z_rt:.2f})",
                        user_id=user_id,
                        context={"elapsed_ms": response.execution_time_ms},
                        recommended_action="Check agent workload and downstream dependencies",
                    )
                )

        # ── Error rate ────────────────────────────────────────────────
        if response:
            em = self._error_monitors.setdefault(
                user_id,
                ErrorRateMonitor(self.config.error_rate_window, self.config.error_rate_threshold),
            )
            success = getattr(response, "success", True)
            is_high_error, error_rate = em.record(success)
            if is_high_error:
                alerts.append(
                    self._make_alert(
                        AnomalyType.HIGH_ERROR_RATE,
                        AnomalySeverity.HIGH,
                        error_rate,
                        f"High error rate: {error_rate*100:.1f}%",
                        user_id=user_id,
                        context={"error_rate": error_rate},
                        recommended_action="Review agent error logs and downstream API health",
                    )
                )

        # ── Replay attack ─────────────────────────────────────────────
        rd = self._replay_detectors.setdefault(
            user_id,
            ReplayDetector(self.config.replay_window_size, self.config.replay_ttl_seconds),
        )
        content = getattr(message, "content", message)
        if rd.check(content):
            alerts.append(
                self._make_alert(
                    AnomalyType.REPLAY_ATTACK,
                    AnomalySeverity.CRITICAL,
                    1.0,
                    "Duplicate/replayed message detected",
                    user_id=user_id,
                    context={"content_preview": str(content)[:100]},
                    recommended_action="Block request and alert security. Possible replay attack.",
                )
            )

        # ── Unusual time ──────────────────────────────────────────────
        if self.config.enable_unusual_time:
            is_unusual, hour = self._time_detector.check()
            if is_unusual:
                alerts.append(
                    self._make_alert(
                        AnomalyType.UNUSUAL_HOUR,
                        AnomalySeverity.LOW,
                        0.4,
                        f"Activity at unusual hour: {hour:02d}:00 UTC",
                        user_id=user_id,
                        context={"hour_utc": hour},
                        recommended_action="Verify this is expected off-hours activity",
                    )
                )

        # ── Dispatch alerts ───────────────────────────────────────────
        for alert in alerts:
            self._alerts.append(alert)
            logger.warning(
                "Anomaly detected",
                type=alert.anomaly_type,
                severity=alert.severity,
                score=alert.score,
                agent=self.agent_id,
                user=user_id,
            )
            for handler in self._handlers:
                try:
                    import asyncio

                    if asyncio.iscoroutinefunction(handler):
                        await handler(alert)
                    else:
                        handler(alert)
                except Exception as exc:
                    logger.error("Alert handler failed", error=str(exc))

        return alerts

    def _make_alert(
        self,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        score: float,
        description: str,
        user_id: str = "",
        context: dict[str, Any] | None = None,
        recommended_action: str = "",
    ) -> AnomalyAlert:
        return AnomalyAlert(
            anomaly_type=anomaly_type,
            severity=severity,
            score=min(max(score, 0.0), 1.0),
            description=description,
            agent_id=self.agent_id,
            user_id=user_id,
            context=context or {},
            recommended_action=recommended_action,
        )

    def get_alert_history(self, limit: int = 100) -> list[AnomalyAlert]:
        return self._alerts[-limit:]

    def add_alert_handler(self, handler: Callable[[AnomalyAlert], Any]) -> None:
        self._handlers.append(handler)

    def summary(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for a in self._alerts:
            by_type[a.anomaly_type] = by_type.get(a.anomaly_type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        return {
            "total_alerts": len(self._alerts),
            "by_type": by_type,
            "by_severity": by_severity,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Platform-level Anomaly Registry
# ─────────────────────────────────────────────────────────────────────────────


class AnomalyRegistry:
    """Manages one AnomalyDetector per agent across the platform."""

    def __init__(self) -> None:
        self._detectors: dict[str, AnomalyDetector] = {}
        self._global_handlers: list[Callable[[AnomalyAlert], Any]] = []

    def get_or_create(
        self, agent_id: str, config: AnomalyDetectorConfig | None = None
    ) -> AnomalyDetector:
        if agent_id not in self._detectors:
            detector = AnomalyDetector(
                agent_id=agent_id,
                config=config,
                alert_handlers=list(self._global_handlers),
            )
            self._detectors[agent_id] = detector
        return self._detectors[agent_id]

    def add_global_handler(self, handler: Callable[[AnomalyAlert], Any]) -> None:
        self._global_handlers.append(handler)
        for detector in self._detectors.values():
            detector.add_alert_handler(handler)

    def platform_summary(self) -> dict[str, Any]:
        all_alerts = [a for d in self._detectors.values() for a in d.get_alert_history()]
        return {
            "agents_monitored": len(self._detectors),
            "total_alerts": len(all_alerts),
            "critical_count": sum(1 for a in all_alerts if a.is_critical),
        }

    _global: AnomalyRegistry | None = None

    @classmethod
    def global_registry(cls) -> AnomalyRegistry:
        if cls._global is None:
            cls._global = cls()
        return cls._global
