"""Résilience et façade async du stockage MinIO."""

from __future__ import annotations

import time

import pytest
from minio.error import S3Error

from app.core.resilience import CircuitOpenError
from app.core.storage import (
    ObjectStorage,
    StorageError,
    StorageObjectNotFound,
    StorageTransientError,
    _translate_error,
)


class _FlakyClient:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def list_buckets(self) -> list:
        self.calls += 1
        if self.calls <= self.failures:
            raise OSError("réseau indisponible")
        return []


@pytest.mark.asyncio
async def test_transient_failure_is_retried_with_a_bound() -> None:
    client = _FlakyClient(failures=2)
    storage = ObjectStorage(client, "test", max_attempts=3, retry_base_delay=0)

    assert await storage.ahealth_ok() is True
    assert client.calls == 3


@pytest.mark.asyncio
async def test_permanent_failure_is_not_retried() -> None:
    class Client:
        calls = 0

        def list_buckets(self) -> list:
            self.calls += 1
            raise ValueError("configuration invalide")

    client = Client()
    storage = ObjectStorage(client, "test", max_attempts=3, retry_base_delay=0)

    with pytest.raises(StorageError):
        await storage.ahealth_ok()
    assert client.calls == 1


@pytest.mark.asyncio
async def test_operation_timeout_is_typed() -> None:
    class SlowClient:
        def list_buckets(self) -> list:
            time.sleep(0.05)
            return []

    storage = ObjectStorage(SlowClient(), "test", timeout_seconds=0.01, max_attempts=1)
    with pytest.raises(StorageTransientError, match="n'a pas répondu"):
        await storage.ahealth_ok()


@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_failures() -> None:
    storage = ObjectStorage(
        _FlakyClient(failures=100),
        "test",
        max_attempts=1,
        circuit_failure_threshold=2,
        retry_base_delay=0,
    )
    for _ in range(2):
        with pytest.raises(StorageTransientError):
            await storage.ahealth_ok()
    with pytest.raises(CircuitOpenError):
        await storage.ahealth_ok()


def test_missing_s3_object_has_stable_error_type() -> None:
    error = S3Error(None, "NoSuchKey", "absent", "resource", "request", "host")  # type: ignore[arg-type]
    assert isinstance(_translate_error(error), StorageObjectNotFound)
