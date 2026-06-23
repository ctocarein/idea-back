"""App factory FastAPI — lifespan, middlewares, montage des routers, handlers d'erreur.

Point d'entrée HTTP (uvicorn/gunicorn). Répond vite, délègue le lourd au worker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api import api_router
from app.core.cache import close_redis
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Démarrage : config (fail-fast) + logging. Arrêt : libération des pools.
    configure_logging()
    logger = get_logger("startup")
    settings = get_settings()
    logger.info("app_starting", env=settings.app_env, name=settings.app_name)
    yield
    await dispose_engine()
    await close_redis()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ideaxion API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # CORS : liste blanche d'origines (front Next.js).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # En-têtes de sécurité sur toutes les réponses. CSP/HSTS uniquement en production
    # (la doc Swagger en dev charge des assets CDN qu'une CSP stricte bloquerait).
    @app.middleware("http")
    async def _security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.is_production:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    install_error_handlers(app)
    app.include_router(api_router)
    return app


# Instance ASGI consommée par uvicorn (`app.main:app`).
app = create_app()
