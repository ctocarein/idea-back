"""Enveloppe d'erreur uniforme + exception handlers FastAPI.

Une SEULE forme de réponse d'erreur dans toute l'API (miroir exact du contrat front) :

    { "error": { "code": "ILLEGAL_TRANSITION", "message": "...", "details": [] } }

Le métier lève des exceptions typées (AppError) ; les handlers les traduisent en HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("errors")


class AppError(Exception):
    """Exception métier de base. Chaque sous-classe porte un code et un statut HTTP."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "Une erreur interne est survenue."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details or []


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 400
    message = "Données invalides."


class UnauthenticatedError(AppError):
    code = "UNAUTHENTICATED"
    status_code = 401
    message = "Authentification requise."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = 403
    message = "Action non autorisée."


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Ressource introuvable."


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409
    message = "Conflit avec l'état actuel de la ressource."


class BusinessRuleError(AppError):
    # Règle métier violée (ex. transition de statut illégale) → 422.
    code = "BUSINESS_RULE"
    status_code = 422
    message = "Règle métier non respectée."


class RateLimitError(AppError):
    # Trop de requêtes (anti brute-force) → 429.
    code = "RATE_LIMITED"
    status_code = 429
    message = "Trop de tentatives. Réessaie plus tard."


def _error_body(code: str, message: str, details: list[Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Erreurs de forme Pydantic → 400 avec le détail des champs fautifs.
        return JSONResponse(
            status_code=400,
            content=_error_body("VALIDATION_ERROR", "Données invalides.", list(exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("HTTP_ERROR", str(exc.detail), []),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Tout le reste : loggé en détail, jamais exposé au client (pas de fuite interne).
        logger.error("unhandled_exception", error=str(exc), exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "Une erreur interne est survenue.", []),
        )
