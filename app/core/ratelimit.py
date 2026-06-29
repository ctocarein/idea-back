"""Rate-limiting Redis (anti brute-force / anti-abus LLM) — fenêtre fixe.

Deux modes :
- fail_open=True  (défaut) : si Redis est down, on laisse passer et on logge.
  Adapté aux gardes d'auth (mieux disponible que bloquant sur une panne infra).
- fail_open=False : si Redis est down, on bloque avec 429.
  Obligatoire pour les endpoints publics coûteux (LLM, parsing fichier).

SEC-05 : _client_ip() ne fait confiance à X-Forwarded-For que si le peer est
dans la liste TRUSTED_PROXIES (config). En local la liste est vide → on prend
request.client.host directement, ce qui empêche le spoofing en prod directe.
"""

from __future__ import annotations

from fastapi import Request

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.core.logging import get_logger

logger = get_logger("ratelimit")


class RateLimiter:
    def __init__(self, *, scope: str, limit: int, window_seconds: int, fail_open: bool = True) -> None:
        self.scope = scope
        self.limit = limit
        self.window = window_seconds
        self.fail_open = fail_open

    async def allow(self, identifier: str) -> bool:
        key = f"rl:{self.scope}:{identifier}"
        try:
            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self.window)
            return count <= self.limit
        except Exception as exc:  # noqa: BLE001
            logger.warning("ratelimit_unavailable", scope=self.scope, error=str(exc))
            # SEC-05 : endpoints coûteux → fail-closed (bloquer) ; auth → fail-open (laisser passer).
            return self.fail_open


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = set(get_settings().trusted_proxies)
    if peer in trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer


def rate_limit(scope: str, *, limit: int, window_seconds: int, fail_open: bool = True):
    """Dépendance FastAPI : limite par IP sur la route où elle est branchée.

    fail_open=False pour les endpoints qui déclenchent un appel LLM ou du parsing
    de fichier (ex. /diagnostics/extract, /diagnostics/extract-file).
    """
    limiter = RateLimiter(scope=scope, limit=limit, window_seconds=window_seconds, fail_open=fail_open)

    async def _checker(request: Request) -> None:
        if not await limiter.allow(_client_ip(request)):
            raise RateLimitError()

    return _checker
