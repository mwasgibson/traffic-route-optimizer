"""Unified async cache: Redis when available, in-memory fallback otherwise.

This replaces the per-process dict caches that lived inside the weather and
traffic services (they were lost on restart and invisible across workers).
The in-memory fallback keeps the app fully functional in dev without Redis.
"""
import json
import logging
import time
from typing import Any, Optional, Dict, Tuple

from ..core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Async JSON cache with TTL. Uses Redis if reachable, else a local dict."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._redis_available: bool = False
        # In-memory fallback: key -> (expires_at, payload)
        self._memory: Dict[str, Tuple[float, str]] = {}

    async def connect(self) -> None:
        """Try to establish the Redis connection. Never raises."""
        try:
            from redis.asyncio.client import Redis

            self._redis = Redis.from_url(  # type: ignore[reportUnknownMemberType]
                settings.redis_url,
                decode_responses=True,
                max_connections=settings.redis_max_connections,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await self._redis.ping()
            self._redis_available = True
            logger.info("Redis cache connected")
        except Exception as exc:  # pragma: no cover - depends on environment
            self._redis = None
            self._redis_available = False
            logger.warning(
                "Redis unavailable (%s) — falling back to in-memory cache", exc
            )

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover
                pass
        self._redis = None
        self._redis_available = False

    @property
    def backend(self) -> str:
        return "redis" if self._redis_available else "memory"

    async def get_json(self, key: str) -> Optional[Any]:
        """Return the cached JSON value, or None if missing/expired."""
        if self._redis_available and self._redis is not None:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception:  # pragma: no cover
                pass
        entry = self._memory.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            self._memory.pop(key, None)
            return None
        return json.loads(payload)

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        """Store a JSON-serializable value with a TTL in seconds."""
        payload = json.dumps(value, default=str)
        if self._redis_available and self._redis is not None:
            try:
                await self._redis.set(key, payload, ex=ttl)
                return
            except Exception:  # pragma: no cover
                pass
        self._memory[key] = (time.monotonic() + ttl, payload)
        # Bound memory growth (~10k entries)
        if len(self._memory) > 10_000:
            now = time.monotonic()
            stale = [k for k, (exp, _) in self._memory.items() if exp < now]
            for k in stale[: len(stale) // 2 or 1]:
                self._memory.pop(k, None)


# Module-level singleton shared by all services.
cache = CacheService()