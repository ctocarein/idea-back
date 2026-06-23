"""Stockage objet (MinIO, S3-compatible) — seam minimal pour PDF/documents.

Optionnel : si les credentials MinIO sont absents, `get_storage()` renvoie None et les
appelants dégradent proprement (ex. bilan `ready` sans PDF). Le client `minio` est
synchrone — les appelants async doivent l'invoquer via `asyncio.to_thread`.
"""

from __future__ import annotations

import io
from datetime import timedelta

from app.core.config import get_settings

_storage: ObjectStorage | None = None


class ObjectStorage:
    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):  # type: ignore[attr-defined]
            self._client.make_bucket(self._bucket)  # type: ignore[attr-defined]

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        self.ensure_bucket()
        self._client.put_object(  # type: ignore[attr-defined]
            self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )
        return key

    def health_ok(self) -> bool:
        # Ping léger : lister les buckets valide la connexion + les credentials.
        self._client.list_buckets()  # type: ignore[attr-defined]
        return True

    def presigned_get(self, key: str, *, expires_seconds: int = 86_400) -> str:
        # URL de téléchargement signée (24h par défaut), servie directement par MinIO.
        return self._client.presigned_get_object(  # type: ignore[attr-defined]
            self._bucket, key, expires=timedelta(seconds=expires_seconds)
        )


def get_storage() -> ObjectStorage | None:
    global _storage
    if _storage is not None:
        return _storage
    settings = get_settings()
    access, secret = settings.minio_access_key, settings.minio_secret_key
    # Non configuré (clé absente ou vide) → dégradation gracieuse (pas de stockage).
    if access is None or secret is None:
        return None
    if not access.get_secret_value() or not secret.get_secret_value():
        return None
    from minio import Minio

    client = Minio(
        settings.minio_endpoint,
        access_key=access.get_secret_value(),
        secret_key=secret.get_secret_value(),
        secure=settings.minio_secure,
    )
    _storage = ObjectStorage(client, settings.minio_bucket)
    return _storage
