"""Résilience des appels externes — timeout, retry/backoff, circuit breaker.

Tout I/O sortant (LLM, MinIO, mailer) est faillible : c'est un invariant, pas une option.
Ces helpers transverses enveloppent les clients de `app/*` (llm, documents, notifications).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from app.core.logging import get_logger

logger = get_logger("resilience")

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Levée quand le circuit est ouvert : on bascule en mode dégradé sans tenter l'appel."""


@dataclass
class RetryPolicy:
    # Politique de retry sur erreurs transitoires. Délais croissants (backoff).
    max_attempts: int = 3
    base_delay: float = 0.5  # secondes
    backoff_factor: float = 2.0
    retry_on: tuple[type[Exception], ...] = (Exception,)


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy | None = None,
    *,
    op_name: str = "external_call",
) -> T:
    # Rejoue `operation` jusqu'à max_attempts sur les exceptions retryables.
    policy = policy or RetryPolicy()
    delay = policy.base_delay
    last_exc: Exception | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except policy.retry_on as exc:  # noqa: B902 — on filtre par retry_on
            last_exc = exc
            if attempt == policy.max_attempts:
                break
            logger.warning(
                "retrying_external_call",
                op=op_name,
                attempt=attempt,
                error=str(exc),
            )
            await asyncio.sleep(delay)
            delay *= policy.backoff_factor

    assert last_exc is not None
    raise last_exc


@dataclass
class CircuitBreaker:
    """Circuit breaker simple : N échecs consécutifs → circuit ouvert pour un délai donné.

    Ouvert → CircuitOpenError immédiate (mode dégradé). Après `reset_timeout`, on
    laisse passer un essai (half-open) ; un succès referme le circuit.
    """

    name: str
    failure_threshold: int = 3
    reset_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))

    _failures: int = 0
    _opened_at: datetime | None = None

    def _now(self) -> datetime:
        return datetime.now(UTC)

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        # Passé le délai de reset, on repasse en half-open (un essai autorisé).
        if self._now() - self._opened_at >= self.reset_timeout:
            return False
        return True

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        if self.is_open:
            raise CircuitOpenError(f"circuit '{self.name}' ouvert")
        try:
            result = await operation()
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._now()
            logger.error("circuit_opened", name=self.name, failures=self._failures)

    def _record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
