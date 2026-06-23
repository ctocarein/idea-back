"""Client Redis async — cache, rate-limit, miroir de sessions.

Une seule connexion partagée (pool interne du client redis). Le métier passe par
des méthodes minces et mockables, jamais par le client brut.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    # Appelé au shutdown (lifespan).
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
