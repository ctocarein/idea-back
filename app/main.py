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

_KNOWN_WEAK_SECRETS = {
    # Valeurs de démo/dev qu'on ne doit JAMAIS retrouver en production.
    "changeme", "secret", "ideaxion", "devsecret", "devjwt",
    "3f9c1d7a4b8e2f6c0a5d9e3b7c1f4a8d2e6b0c9f5a3d7e1b",  # JWT du .env local
}


def _assert_production_config(settings) -> None:  # noqa: ANN001
    """SEC-08 / SEC-14 : refuse de démarrer en production avec une config non sécurisée."""
    if not settings.is_production:
        return
    errors: list[str] = []

    # JWT_SECRET faible ou valeur de démo connue.
    jwt = settings.jwt_secret.get_secret_value()
    if len(jwt) < 32 or jwt.lower() in _KNOWN_WEAK_SECRETS:
        errors.append("JWT_SECRET trop court ou valeur de démo connue — rotation requise.")

    # CORS wildcard incompatible avec allow_credentials=True.
    if "*" in settings.cors_origins:
        errors.append("CORS wildcard '*' interdit en production avec credentials actifs.")

    # Pas d'origine CORS configurée du tout.
    if not settings.cors_origins:
        errors.append("CORS_ORIGINS vide — aucune origine autorisée en production.")

    if errors:
        bullet_list = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(f"Démarrage refusé — configuration production invalide :\n{bullet_list}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("startup")
    settings = get_settings()
    _assert_production_config(settings)  # SEC-08/14 : fail-fast si config prod invalide
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
