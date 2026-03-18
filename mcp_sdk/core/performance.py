"""
Performance Optimization and Scaling for MCP SDK
================================================
Provides caching, connection pooling, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

import structlog

from .error_handling import handle_errors

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    value: Any
    expires_at: datetime | None = None
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))


class CacheManager:
    """High-performance cache manager with LRU eviction."""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: timedelta | None = None,
        cleanup_interval: float = 300.0,  # 5 minutes
    ) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl or timedelta(hours=1)
        self.cleanup_interval = cleanup_interval

        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

        # Metrics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def start(self) -> None:
        """Start the cache cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cache cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    @handle_errors("CACHE_GET_ERROR", reraise=False)
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Check expiration
            if entry.expires_at and entry.expires_at < datetime.now(UTC):
                del self._cache[key]
                self._access_order.remove(key)
                self._misses += 1
                return None

            # Update access tracking
            entry.access_count += 1
            entry.last_accessed = datetime.now(UTC)

            # Move to end of access order (LRU)
            self._access_order.remove(key)
            self._access_order.append(key)

            self._hits += 1
            return entry.value

    @handle_errors("CACHE_SET_ERROR")
    async def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta | None = None,
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            expires_at = None
            if ttl or self.default_ttl:
                expires_at = datetime.now(UTC) + (ttl or self.default_ttl)

            entry = CacheEntry(
                value=value,
                expires_at=expires_at,
            )

            # If key already exists, update it
            if key in self._cache:
                self._cache[key] = entry
                # Move to end of access order
                self._access_order.remove(key)
                self._access_order.append(key)
            else:
                # Add new entry
                self._cache[key] = entry
                self._access_order.append(key)

                # Evict if necessary
                await self._evict_if_needed()

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_order.remove(key)
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()

    async def _evict_if_needed(self) -> None:
        """Evict entries if cache is full."""
        while len(self._cache) > self.max_size:
            # Remove least recently used item
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]
            self._evictions += 1

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cache cleanup error", error=str(e))

    async def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        async with self._lock:
            now = datetime.now(UTC)
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and entry.expires_at < now
            ]

            for key in expired_keys:
                del self._cache[key]
                self._access_order.remove(key)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": hit_rate,
        }


class ConnectionPool:
    """Generic connection pool for database and HTTP connections."""

    def __init__(
        self,
        create_connection: Callable[[], Any],
        max_connections: int = 10,
        max_idle_time: float = 300.0,
        health_check: Callable[[Any], bool] | None = None,
    ) -> None:
        self.create_connection = create_connection
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.health_check = health_check

        self._pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_connections)
        self._created_connections = 0
        self._lock = asyncio.Lock()

        # Metrics
        self._total_created = 0
        self._total_reused = 0
        self._total_failed = 0

    async def get_connection(self) -> Any:
        """Get a connection from the pool."""
        try:
            # Try to get existing connection
            conn = self._pool.get_nowait()

            # Check if connection is still valid
            if self._is_connection_valid(conn):
                self._total_reused += 1
                return conn
            else:
                # Connection is invalid, discard it
                await self._close_connection(conn)
                self._total_failed += 1
        except asyncio.QueueEmpty:
            pass

        # Create new connection
        async with self._lock:
            if self._created_connections < self.max_connections:
                conn = await self._create_new_connection()
                self._created_connections += 1
                self._total_created += 1
                return conn

        # Pool is full, wait for a connection
        conn = await self._pool.get()
        if self._is_connection_valid(conn):
            self._total_reused += 1
            return conn
        else:
            await self._close_connection(conn)
            self._total_failed += 1
            # Retry
            return await self.get_connection()

    async def return_connection(self, conn: Any) -> None:
        """Return a connection to the pool."""
        if self._is_connection_valid(conn):
            try:
                self._pool.put_nowait(conn)
            except asyncio.QueueFull:
                # Pool is full, close the connection
                await self._close_connection(conn)
        else:
            await self._close_connection(conn)

    async def _create_new_connection(self) -> Any:
        """Create a new connection."""
        try:
            return await self.create_connection()
        except Exception as e:
            logger.error("Failed to create connection", error=str(e))
            raise

    def _is_connection_valid(self, conn: Any) -> bool:
        """Check if connection is still valid."""
        if self.health_check:
            try:
                return self.health_check(conn)
            except Exception:
                return False
        return True

    async def _close_connection(self, conn: Any) -> None:
        """Close a connection."""
        try:
            if hasattr(conn, 'close'):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
            elif hasattr(conn, 'aclose'):
                await conn.aclose()
        except Exception as e:
            logger.error("Error closing connection", error=str(e))

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        while not self._pool.empty():
            conn = self._pool.get_nowait()
            await self._close_connection(conn)

        async with self._lock:
            self._created_connections = 0

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        return {
            "created_connections": self._created_connections,
            "available_connections": self._pool.qsize(),
            "total_created": self._total_created,
            "total_reused": self._total_reused,
            "total_failed": self._total_failed,
            "reuse_rate": self._total_reused / (self._total_created + self._total_reused) if (self._total_created + self._total_reused) > 0 else 0,
        }


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        rate: float,  # tokens per second
        burst: int,   # maximum burst size
    ) -> None:
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from the bucket."""
        async with self._lock:
            now = time.time()

            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            # Calculate wait time
            async with self._lock:
                needed = tokens - self.tokens
                wait_time = needed / self.rate

            await asyncio.sleep(wait_time)


class LoadBalancer:
    """Simple load balancer for distributing requests."""

    def __init__(self, strategy: str = "round_robin") -> None:
        self.strategy = strategy
        self._targets: list[str] = []
        self._current_index = 0
        self._target_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "requests": 0,
            "failures": 0,
            "last_used": 0,
            "response_times": [],
        })
        self._lock = asyncio.Lock()

    def add_target(self, target: str) -> None:
        """Add a target to the load balancer."""
        if target not in self._targets:
            self._targets.append(target)

    def remove_target(self, target: str) -> None:
        """Remove a target from the load balancer."""
        if target in self._targets:
            self._targets.remove(target)
            del self._target_stats[target]

    async def get_target(self) -> str | None:
        """Get the best target based on strategy."""
        if not self._targets:
            return None

        async with self._lock:
            if self.strategy == "round_robin":
                target = self._targets[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._targets)
                return target

            elif self.strategy == "least_connections":
                # Choose target with fewest active requests
                best_target = min(
                    self._targets,
                    key=lambda t: self._target_stats[t]["requests"]
                )
                return best_target

            elif self.strategy == "weighted_response_time":
                # Choose target with best average response time
                best_target = min(
                    self._targets,
                    key=lambda t: self._calculate_weighted_score(t)
                )
                return best_target

        return self._targets[0]

    def _calculate_weighted_score(self, target: str) -> float:
        """Calculate weighted score for a target."""
        stats = self._target_stats[target]
        if not stats["response_times"]:
            return float('inf')

        avg_response_time = sum(stats["response_times"]) / len(stats["response_times"])
        failure_rate = stats["failures"] / max(stats["requests"], 1)

        # Higher score is worse
        return avg_response_time * (1 + failure_rate * 10)

    async def record_request(self, target: str, success: bool, response_time: float) -> None:
        """Record request statistics."""
        async with self._lock:
            stats = self._target_stats[target]
            stats["requests"] += 1
            stats["last_used"] = time.time()

            if not success:
                stats["failures"] += 1

            # Keep only last 100 response times
            stats["response_times"].append(response_time)
            if len(stats["response_times"]) > 100:
                stats["response_times"] = stats["response_times"][-100:]

    def get_stats(self) -> dict[str, Any]:
        """Get load balancer statistics."""
        return {
            "targets": self._targets.copy(),
            "strategy": self.strategy,
            "target_stats": dict(self._target_stats),
        }


class PerformanceOptimizer:
    """Main performance optimization coordinator."""

    def __init__(self) -> None:
        self.cache = CacheManager()
        self.connection_pools: dict[str, ConnectionPool] = {}
        self.rate_limiters: dict[str, RateLimiter] = {}
        self.load_balancers: dict[str, LoadBalancer] = {}
        self._started = False

    async def start(self) -> None:
        """Start all performance components."""
        if not self._started:
            await self.cache.start()
            self._started = True
            logger.info("Performance optimizer started")

    async def stop(self) -> None:
        """Stop all performance components."""
        if self._started:
            await self.cache.stop()

            # Close all connection pools
            for pool in self.connection_pools.values():
                await pool.close_all()

            self._started = False
            logger.info("Performance optimizer stopped")

    def register_cache(self, name: str, **kwargs) -> CacheManager:
        """Register a named cache."""
        cache = CacheManager(**kwargs)
        setattr(self, f"cache_{name}", cache)
        return cache

    def register_connection_pool(
        self,
        name: str,
        create_connection: Callable[[], Any],
        **kwargs
    ) -> ConnectionPool:
        """Register a named connection pool."""
        pool = ConnectionPool(create_connection, **kwargs)
        self.connection_pools[name] = pool
        return pool

    def register_rate_limiter(
        self,
        name: str,
        rate: float,
        burst: int
    ) -> RateLimiter:
        """Register a named rate limiter."""
        limiter = RateLimiter(rate, burst)
        self.rate_limiters[name] = limiter
        return limiter

    def register_load_balancer(
        self,
        name: str,
        strategy: str = "round_robin"
    ) -> LoadBalancer:
        """Register a named load balancer."""
        balancer = LoadBalancer(strategy)
        self.load_balancers[name] = balancer
        return balancer

    @asynccontextmanager
    async def cached_operation(self, cache_name: str, key: str, ttl: timedelta | None = None):
        """Context manager for cached operations."""
        cache = getattr(self, f"cache_{cache_name}", self.cache)

        # Try to get from cache
        cached_result = await cache.get(key)
        if cached_result is not None:
            yield cached_result
            return

        # Execute operation and cache result
        result = yield
        await cache.set(key, result, ttl)

    @asynccontextmanager
    async def rate_limited(self, limiter_name: str, tokens: int = 1):
        """Context manager for rate-limited operations."""
        limiter = self.rate_limiters.get(limiter_name)
        if limiter:
            await limiter.wait_for_token(tokens)

        yield

    @asynccontextmanager
    async def connection(self, pool_name: str):
        """Context manager for pooled connections."""
        pool = self.connection_pools.get(pool_name)
        if not pool:
            raise ValueError(f"Connection pool '{pool_name}' not found")

        conn = await pool.get_connection()
        try:
            yield conn
        finally:
            await pool.return_connection(conn)

    def get_performance_stats(self) -> dict[str, Any]:
        """Get comprehensive performance statistics."""
        stats = {
            "cache": self.cache.get_stats(),
            "connection_pools": {
                name: pool.get_stats()
                for name, pool in self.connection_pools.items()
            },
            "load_balancers": {
                name: balancer.get_stats()
                for name, balancer in self.load_balancers.items()
            },
        }

        return stats


# Global performance optimizer instance
_performance_optimizer: PerformanceOptimizer | None = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get the global performance optimizer instance."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer


# Decorators for performance optimization
def cached(cache_name: str, key_func: Callable | None = None, ttl: timedelta | None = None):
    """Decorator for caching function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()

            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            async with optimizer.cached_operation(cache_name, key, ttl) as result:
                if result is None:
                    # Execute function
                    result = await func(*args, **kwargs)

                return result

        return wrapper
    return decorator


def rate_limited(limiter_name: str, tokens: int = 1):
    """Decorator for rate limiting function calls."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()

            async with optimizer.rate_limited(limiter_name, tokens):
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def pooled_connection(pool_name: str):
    """Decorator for using pooled connections."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()

            async with optimizer.connection(pool_name) as conn:
                return await func(conn, *args, **kwargs)

        return wrapper
    return decorator
