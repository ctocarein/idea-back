"""Rate-limiting Redis (anti brute-force / anti-abus LLM) — fenêtre fixe.

**Disponibilité.** Si Redis est indisponible, on ne bloque PAS tout (fail-closed,
qui pénalise les usagers légitimes) et on ne laisse PAS tout passer (fail-open,
qui rouvre l'abus des endpoints LLM coûteux). On bascule sur un **repli en
mémoire** : un compteur par process, mêmes limites que Redis. La limite tient
donc toujours — dégradée (par process, non partagée) mais sûre — le temps que
Redis revienne. Plus besoin de choisir fail-open/closed par endpoint.

SEC-05 : _client_ip() ne fait confiance à X-Forwarded-For que si le peer est
dans la liste TRUSTED_PROXIES (config). En local la liste est vide → on prend
request.client.host directement, ce qui empêche le spoofing en prod directe.
"""

from __future__ import annotations

from time import monotonic

from fastapi import Request

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.core.logging import get_logger

logger = get_logger("ratelimit")

# Repli en mémoire (par process) quand Redis est indisponible. Fenêtre fixe :
# clé -> (count, window_start monotone). Best-effort ; purge opportuniste si ça grossit.
_MEM_BUCKETS: dict[str, tuple[int, float]] = {}
_MEM_MAX_KEYS = 10_000


class RateLimiter:
    def __init__(self, *, scope: str, limit: int, window_seconds: int) -> None:
        self.scope = scope
        self.limit = limit
        self.window = window_seconds

    async def allow(self, identifier: str) -> bool:
        key = f"rl:{self.scope}:{identifier}"
        try:
            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self.window)
            return count <= self.limit
        except Exception as exc:  # noqa: BLE001 — Redis down / timeout / protocole
            # Redis KO → on continue à limiter en mémoire plutôt que de tout bloquer.
            logger.warning("ratelimit_degraded", scope=self.scope, error=str(exc))
            return self._allow_in_memory(key)

    def _allow_in_memory(self, key: str) -> bool:
        """Repli : fenêtre fixe en mémoire, mêmes limites.

        Pas de verrou : les opérations sont synchrones (aucun `await` entre le get
        et le set), donc atomiques dans un tick de l'event loop.
        """
        now = monotonic()
        count, start = _MEM_BUCKETS.get(key, (0, now))
        if now - start >= self.window:
            count, start = 0, now  # fenêtre expirée → on repart à zéro
        count += 1
        _MEM_BUCKETS[key] = (count, start)
        if len(_MEM_BUCKETS) > _MEM_MAX_KEYS:
            _evict_stale(now)
        return count <= self.limit


def _evict_stale(now: float) -> None:
    # Purge les fenêtres franchement périmées (> 1 h, au-delà de toute fenêtre en usage).
    for key in [k for k, (_, start) in _MEM_BUCKETS.items() if now - start > 3600]:
        _MEM_BUCKETS.pop(key, None)


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = set(get_settings().trusted_proxies)
    if peer in trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer


def rate_limit(scope: str, *, limit: int, window_seconds: int):
    """Dépendance FastAPI : limite par IP sur la route où elle est branchée.

    En cas de panne Redis, le repli en mémoire (cf. `RateLimiter`) prend le relais :
    la limite reste appliquée, il n'y a plus de fail-open/closed à arbitrer.
    """
    limiter = RateLimiter(scope=scope, limit=limit, window_seconds=window_seconds)

    async def _checker(request: Request) -> None:
        if not await limiter.allow(_client_ip(request)):
            raise RateLimitError()

    return _checker
