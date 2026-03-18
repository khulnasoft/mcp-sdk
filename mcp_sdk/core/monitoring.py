"""
Monitoring and Observability for MCP SDK
========================================
Provides metrics collection, health checks, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .error_handling import handle_errors

logger = structlog.get_logger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    value: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check configuration and result."""
    name: str
    check_func: callable
    timeout: float = 5.0
    interval: float = 60.0
    last_check: datetime | None = None
    status: str = "unknown"  # healthy, unhealthy, unknown
    message: str = ""
    response_time: float = 0.0


class MetricsCollector:
    """Collects and manages application metrics."""

    def __init__(self, max_points: int = 10000) -> None:
        self.max_points = max_points
        self._metrics: dict[str, deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=max_points))
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        self._counters[name] += value
        self._add_metric_point(name, self._counters[name], tags)

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        self._gauges[name] = value
        self._add_metric_point(name, value, tags)

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Add a value to a histogram."""
        self._histograms[name].append(value)
        self._add_metric_point(name, value, tags)

    def timing(self, name: str, duration: float, tags: dict[str, str] | None = None) -> None:
        """Record a timing metric."""
        self.histogram(f"{name}_duration", duration, tags)

    def _add_metric_point(self, name: str, value: float, tags: dict[str, str] | None) -> None:
        """Add a metric point to the time series."""
        point = MetricPoint(value=value, tags=tags or {})
        self._metrics[name].append(point)

    def get_metric(self, name: str, since: datetime | None = None) -> list[MetricPoint]:
        """Get metric points since a given time."""
        points = list(self._metrics[name])
        if since:
            points = [p for p in points if p.timestamp >= since]
        return points

    def get_counter(self, name: str) -> float:
        """Get current counter value."""
        return self._counters[name]

    def get_gauge(self, name: str) -> float:
        """Get current gauge value."""
        return self._gauges[name]

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics."""
        values = list(self._histograms[name])
        if not values:
            return {}

        sorted_values = sorted(values)
        count = len(values)
        return {
            "count": count,
            "sum": sum(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)],
        }


class PerformanceTracker:
    """Tracks performance metrics for operations."""

    def __init__(self, metrics_collector: MetricsCollector) -> None:
        self.metrics = metrics_collector

    @asynccontextmanager
    async def track_operation(self, operation_name: str, tags: dict[str, str] | None = None):
        """Context manager to track operation performance."""
        start_time = time.perf_counter()
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time
            status = "success" if success else "error"

            # Record metrics
            all_tags = {"status": status}
            if tags:
                all_tags.update(tags)

            self.metrics.timing(f"operation_{operation_name}", duration, all_tags)
            self.metrics.increment(f"operation_{operation_name}_calls", 1.0, all_tags)

            logger.debug(
                f"Operation {operation_name} completed",
                operation=operation_name,
                duration=duration,
                status=status,
                tags=all_tags
            )


class HealthMonitor:
    """Monitors application health with configurable checks."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_check(self, health_check: HealthCheck) -> None:
        """Add a health check."""
        self._checks[health_check.name] = health_check
        logger.info("Health check added", check=health_check.name)

    def remove_check(self, name: str) -> None:
        """Remove a health check."""
        if name in self._checks:
            del self._checks[name]
            logger.info("Health check removed", check=name)

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            await asyncio.sleep(1.0)  # Check every second

            current_time = datetime.now(UTC)
            for check in self._checks.values():
                if (check.last_check is None or
                    current_time - check.last_check >= timedelta(seconds=check.interval)):
                    await self._run_check(check)

    @handle_errors("HEALTH_CHECK_ERROR", reraise=False)
    async def _run_check(self, check: HealthCheck) -> None:
        """Run a single health check."""
        start_time = time.perf_counter()

        try:
            async with asyncio.timeout(check.timeout):
                if asyncio.iscoroutinefunction(check.check_func):
                    result = await check.check_func()
                else:
                    result = check.check_func()

                # Consider check healthy if result is truthy or None
                is_healthy = bool(result) if result is not None else True
                check.status = "healthy" if is_healthy else "unhealthy"
                check.message = str(result) if result is not None else "OK"

        except Exception as e:
            check.status = "unhealthy"
            check.message = str(e)
            logger.error("Health check failed", check=check.name, error=str(e))

        finally:
            check.response_time = time.perf_counter() - start_time
            check.last_check = datetime.now(UTC)

    async def check_health(self, name: str | None = None) -> dict[str, Any]:
        """Get current health status."""
        if name:
            if name not in self._checks:
                return {"status": "unknown", "message": f"Check '{name}' not found"}
            check = self._checks[name]
            await self._run_check(check)
            return {
                "status": check.status,
                "message": check.message,
                "response_time": check.response_time,
                "last_check": check.last_check.isoformat() if check.last_check else None,
            }

        # Run all checks
        results = {}
        overall_healthy = True

        for check in self._checks.values():
            await self._run_check(check)
            results[check.name] = {
                "status": check.status,
                "message": check.message,
                "response_time": check.response_time,
                "last_check": check.last_check.isoformat() if check.last_check else None,
            }

            if check.status != "healthy":
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": datetime.now(UTC).isoformat(),
        }


class MonitoringSystem:
    """Main monitoring system that coordinates all monitoring components."""

    def __init__(self) -> None:
        self.metrics = MetricsCollector()
        self.performance = PerformanceTracker(self.metrics)
        self.health = HealthMonitor()
        self._running = False

    async def start(self) -> None:
        """Start the monitoring system."""
        if self._running:
            return

        await self.health.start_monitoring()
        self._running = True
        logger.info("Monitoring system started")

    async def stop(self) -> None:
        """Stop the monitoring system."""
        await self.health.stop_monitoring()
        self._running = False
        logger.info("Monitoring system stopped")

    def get_system_metrics(self) -> dict[str, Any]:
        """Get comprehensive system metrics."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": {
                name: [point.dict() for point in points[-10:]]  # Last 10 points
                for name, points in self.metrics._metrics.items()
            },
            "counters": dict(self.metrics._counters),
            "gauges": dict(self.metrics._gauges),
            "histograms": {
                name: self.metrics.get_histogram_stats(name)
                for name in self.metrics._histograms
            },
        }

    @asynccontextmanager
    async def track_request(self, operation: str, **tags):
        """Track a request with performance metrics."""
        async with self.performance.track_operation(operation, tags):
            yield


# Global monitoring instance
_monitoring_system: MonitoringSystem | None = None


def get_monitoring() -> MonitoringSystem:
    """Get the global monitoring instance."""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem()
    return _monitoring_system


@asynccontextmanager
async def monitor_operation(operation: str, **tags):
    """Context manager for monitoring operations."""
    monitoring = get_monitoring()
    async with monitoring.track_request(operation, **tags):
        yield
