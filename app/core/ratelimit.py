"""Rate-limiting Redis (anti brute-force) — fenêtre fixe, fail-open si Redis indisponible.

Choix : si Redis est down, on **laisse passer** (disponibilité > durcissement sur ce point) —
on logge pour ne pas masquer le problème. Le rate-limit reste une défense, pas un SPOF d'auth.
"""

from __future__ import annotations

from fastapi import Request

from app.core.cache import get_redis
from app.core.errors import RateLimitError
from app.core.logging import get_logger

logger = get_logger("ratelimit")


class RateLimiter:
    def __init__(self, *, scope: str, limit: int, window_seconds: int) -> None:
        self.scope = scope
        self.limit = limit
        self.window = window_seconds

    async def allow(self, identifier: str) -> bool:
        # Fenêtre fixe : INCR + EXPIRE au premier hit. Vrai si sous la limite.
        key = f"rl:{self.scope}:{identifier}"
        try:
            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self.window)
            return count <= self.limit
        except Exception as exc:  # noqa: BLE001 — Redis down → fail-open
            logger.warning("ratelimit_unavailable", scope=self.scope, error=str(exc))
            return True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, *, limit: int, window_seconds: int):
    # Dépendance FastAPI : limite par IP cliente sur la route où elle est branchée.
    limiter = RateLimiter(scope=scope, limit=limit, window_seconds=window_seconds)

    async def _checker(request: Request) -> None:
        if not await limiter.allow(_client_ip(request)):
            raise RateLimitError()

    return _checker
