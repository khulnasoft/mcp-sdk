"""Tests for Anomaly Detector."""

import pytest

from mcp_sdk.agents.base import AgentContext, AgentMessage, AgentResponse
from mcp_sdk.plugins.anomaly.detector import (
    AnomalyDetector,
    AnomalyDetectorConfig,
    AnomalyRegistry,
    AnomalyType,
    ErrorRateMonitor,
    OnlineStats,
    PayloadAnalyzer,
    ReplayDetector,
)


class TestOnlineStats:
    def test_single_update(self) -> None:
        stats = OnlineStats()
        stats.update(10.0)
        assert stats.mean == 10.0
        assert stats.n == 1

    def test_mean_convergence(self) -> None:
        stats = OnlineStats()
        for v in [2.0, 4.0, 6.0, 8.0]:
            stats.update(v)
        assert abs(stats.mean - 5.0) < 0.001

    def test_z_score_zero_std(self) -> None:
        stats = OnlineStats()
        stats.update(5.0)
        assert stats.z_score(5.0) == 0.0

    def test_z_score_outlier(self) -> None:
        stats = OnlineStats()
        for _ in range(20):
            stats.update(1.0)
        z = stats.z_score(100.0)
        assert z > 3.0


class TestReplayDetector:
    def test_first_message_not_replay(self) -> None:
        rd = ReplayDetector()
        assert rd.check("hello world") is False

    def test_duplicate_is_replay(self) -> None:
        rd = ReplayDetector()
        rd.check("same message")
        assert rd.check("same message") is True

    def test_different_messages_not_replay(self) -> None:
        rd = ReplayDetector()
        rd.check("message 1")
        assert rd.check("message 2") is False


class TestErrorRateMonitor:
    def test_no_alert_low_errors(self) -> None:
        em = ErrorRateMonitor(window=20, threshold=0.2)
        for _ in range(20):
            is_high, _ = em.record(True)
        assert not is_high

    def test_alert_on_high_error_rate(self) -> None:
        em = ErrorRateMonitor(window=20, threshold=0.2)
        for _ in range(10):
            em.record(True)
        for _ in range(10):
            em.record(False)
        is_high, rate = em.record(False)
        assert is_high
        assert rate > 0.2


class TestPayloadAnalyzer:
    def test_normal_payload_no_alert(self) -> None:
        pa = PayloadAnalyzer(z_threshold=3.0)
        for _ in range(20):
            is_outlier, _, _ = pa.analyze("normal sized message")
        assert not is_outlier

    def test_extremely_large_payload_detected(self) -> None:
        pa = PayloadAnalyzer(z_threshold=2.0)
        for _ in range(50):
            pa.analyze("small")
        is_outlier, z, size = pa.analyze("X" * 100_000)
        assert is_outlier
        assert z > 2.0


class TestAnomalyDetector:
    @pytest.fixture
    def detector(self):
        config = AnomalyDetectorConfig(
            enable_unusual_time=False,  # Disable time-based for deterministic tests
            rate_spike_multiplier=2.0,
        )
        return AnomalyDetector(agent_id="test-agent", config=config)

    @pytest.fixture
    def message(self):
        return AgentMessage(sender_id="user", recipient_id="agent", content="hello")

    @pytest.fixture
    def context(self):
        return AgentContext(user_id="alice")

    @pytest.mark.asyncio
    async def test_clean_interaction_no_alerts(self, detector, message, context) -> None:
        response = AgentResponse(data="ok", execution_time_ms=50)
        alerts = await detector.analyze(message, response, context)
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_replay_detected(self, detector, message, context) -> None:
        response = AgentResponse(data="ok")
        await detector.analyze(message, response, context)
        alerts = await detector.analyze(message, response, context)
        replay_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.REPLAY_ATTACK]
        assert len(replay_alerts) == 1
        assert replay_alerts[0].is_critical

    @pytest.mark.asyncio
    async def test_alert_handler_called(self, detector, message, context) -> None:
        received: list = []
        detector.add_alert_handler(lambda a: received.append(a))
        # Force replay
        await detector.analyze(message, AgentResponse(data="ok"), context)
        await detector.analyze(message, AgentResponse(data="ok"), context)
        assert len(received) >= 1

    def test_summary(self, detector) -> None:
        summary = detector.summary()
        assert "total_alerts" in summary
        assert summary["total_alerts"] == 0


class TestAnomalyRegistry:
    def test_get_or_create(self) -> None:
        registry = AnomalyRegistry()
        d1 = registry.get_or_create("agent-1")
        d2 = registry.get_or_create("agent-1")
        assert d1 is d2

    def test_global_handler(self) -> None:
        registry = AnomalyRegistry()
        received = []
        registry.add_global_handler(lambda a: received.append(a))
        d = registry.get_or_create("agent-x")
        assert len(d._handlers) == 1
