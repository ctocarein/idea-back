"""Health check — agrège l'état des dépendances (DB, Redis, MinIO).

200 si tout répond, 503 si une dépendance critique est down. Les checks sont
best-effort et bornés en temps pour ne jamais faire pendre le endpoint.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.cache import get_redis
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.core.storage import get_storage

router = APIRouter(tags=["platform"])
logger = get_logger("health")


async def _check_db() -> bool:
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health ne doit jamais lever
        logger.warning("health_db_down", error=str(exc))
        return False


async def _check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_redis_down", error=str(exc))
        return False


async def _check_minio() -> bool | None:
    # None = non configuré (pas un échec : le PDF dégrade gracieusement).
    storage = get_storage()
    if storage is None:
        return None
    try:
        return await asyncio.to_thread(storage.health_ok)
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_minio_down", error=str(exc))
        return False


@router.get("/health")
async def health(response: Response) -> dict[str, object]:
    db_ok, redis_ok, minio_ok = await asyncio.gather(_check_db(), _check_redis(), _check_minio())
    checks: dict[str, object] = {"database": db_ok, "redis": redis_ok, "minio": minio_ok}
    # MinIO non configuré (None) n'impacte pas la santé ; configuré-mais-down (False) si.
    healthy = db_ok and redis_ok and minio_ok is not False
    response.status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
