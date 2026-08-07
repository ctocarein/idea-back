"""Stockage objet MinIO avec timeout, retry, circuit breaker et façade async."""

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

import certifi
import urllib3
from minio.error import S3Error

from app.core.config import get_settings
from app.core.resilience import CircuitBreaker, RetryPolicy, with_retry

T = TypeVar("T")

_TRANSIENT_S3_CODES = {"InternalError", "RequestTimeout", "ServiceUnavailable", "SlowDown"}
_NOT_FOUND_S3_CODES = {"NoSuchBucket", "NoSuchKey", "NoSuchObject", "XMinioInvalidObjectName"}


class StorageError(Exception):
    """Erreur stable exposée aux services, indépendante du SDK MinIO."""


class StorageTransientError(StorageError):
    """Erreur réseau ou serveur éligible à une nouvelle tentative."""


class StorageObjectNotFound(StorageError):
    """Objet ou bucket absent ; une nouvelle tentative immédiate serait inutile."""


def _translate_error(exc: Exception) -> StorageError:
    if isinstance(exc, StorageError):
        return exc
    if isinstance(exc, S3Error):
        if exc.code in _NOT_FOUND_S3_CODES:
            return StorageObjectNotFound(str(exc))
        if exc.code in _TRANSIENT_S3_CODES:
            return StorageTransientError(str(exc))
        return StorageError(str(exc))
    if isinstance(exc, (TimeoutError, OSError, urllib3.exceptions.HTTPError)):
        return StorageTransientError(str(exc))
    return StorageError(str(exc))


class ObjectStorage:
    """Client sync MinIO encapsulé derrière des méthodes async non bloquantes."""

    def __init__(
        self,
        client: object,
        bucket: str,
        *,
        timeout_seconds: float = 5.0,
        max_attempts: int = 3,
        circuit_failure_threshold: int = 3,
        circuit_reset_seconds: int = 30,
        retry_base_delay: float = 0.2,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._timeout_seconds = timeout_seconds
        self._retry = RetryPolicy(
            max_attempts=max_attempts,
            base_delay=retry_base_delay,
            retry_on=(StorageTransientError,),
        )
        self._breaker = CircuitBreaker(
            name="minio",
            failure_threshold=circuit_failure_threshold,
            reset_timeout=timedelta(seconds=circuit_reset_seconds),
        )

    async def _call(self, op_name: str, operation: Callable[[], T]) -> T:
        async def once() -> T:
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    return await asyncio.to_thread(operation)
            except TimeoutError as exc:
                raise StorageTransientError(
                    f"MinIO n'a pas répondu en {self._timeout_seconds:g}s ({op_name})."
                ) from exc
            except Exception as exc:
                raise _translate_error(exc) from exc

        return await self._breaker.call(lambda: with_retry(once, self._retry, op_name=f"minio:{op_name}"))

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):  # type: ignore[attr-defined]
            self._client.make_bucket(self._bucket)  # type: ignore[attr-defined]

    def _put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        self._ensure_bucket()
        self._client.put_object(  # type: ignore[attr-defined]
            self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )
        return key

    def _get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)  # type: ignore[attr-defined]
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def _health_ok(self) -> bool:
        self._client.list_buckets()  # type: ignore[attr-defined]
        return True

    def _presigned_get(self, key: str, expires_seconds: int) -> str:
        return self._client.presigned_get_object(  # type: ignore[attr-defined]
            self._bucket, key, expires=timedelta(seconds=expires_seconds)
        )

    def _presigned_put(self, key: str, expires_seconds: int) -> str:
        self._ensure_bucket()
        return self._client.presigned_put_object(  # type: ignore[attr-defined]
            self._bucket, key, expires=timedelta(seconds=expires_seconds)
        )

    def _stat_object(self, key: str) -> tuple[int, str]:
        stat = self._client.stat_object(self._bucket, key)  # type: ignore[attr-defined]
        return (stat.size, stat.content_type or "")

    def _remove_object(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)  # type: ignore[attr-defined]

    async def aput_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        return await self._call("put", lambda: self._put_bytes(key=key, data=data, content_type=content_type))

    async def aget_bytes(self, key: str) -> bytes:
        return await self._call("get", lambda: self._get_bytes(key))

    async def ahealth_ok(self) -> bool:
        return await self._call("health", self._health_ok)

    async def apresigned_get(self, key: str, *, expires_seconds: int = 86_400) -> str:
        return await self._call("presigned_get", lambda: self._presigned_get(key, expires_seconds))

    async def apresigned_put(self, key: str, *, expires_seconds: int = 300) -> str:
        return await self._call("presigned_put", lambda: self._presigned_put(key, expires_seconds))

    async def astat_object(self, key: str) -> tuple[int, str]:
        return await self._call("stat", lambda: self._stat_object(key))

    async def aremove_object(self, key: str) -> None:
        await self._call("remove", lambda: self._remove_object(key))


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage | None:
    global _storage
    if _storage is not None:
        return _storage
    settings = get_settings()
    access, secret = settings.minio_access_key, settings.minio_secret_key
    if access is None or secret is None:
        return None
    if not access.get_secret_value() or not secret.get_secret_value():
        return None

    from minio import Minio

    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(
            connect=settings.minio_timeout_seconds,
            read=settings.minio_timeout_seconds,
        ),
        maxsize=10,
        cert_reqs="CERT_REQUIRED",
        ca_certs=os.environ.get("SSL_CERT_FILE") or certifi.where(),
        retries=False,
    )
    client = Minio(
        settings.minio_endpoint,
        access_key=access.get_secret_value(),
        secret_key=secret.get_secret_value(),
        secure=settings.minio_secure,
        region=settings.minio_region,
        http_client=http_client,
    )
    _storage = ObjectStorage(
        client,
        settings.minio_bucket,
        timeout_seconds=settings.minio_timeout_seconds,
        max_attempts=settings.minio_max_attempts,
        circuit_failure_threshold=settings.minio_circuit_failure_threshold,
        circuit_reset_seconds=settings.minio_circuit_reset_seconds,
    )
    return _storage
