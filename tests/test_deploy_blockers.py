"""Les deux pannes qui empêchent un inconnu d'utiliser le produit de bout en bout.

Aucune des deux ne se voit dans les logs du serveur : l'URL présignée est renvoyée
avec un 200, et l'email « best-effort » n'échoue jamais bruyamment. D'où ces tests.
"""

from __future__ import annotations

import pytest

from app.core.email import _tls_mode
from app.core.storage import ObjectStorage


class _RecordingClient:
    """Client MinIO minimal : retient l'hôte pour lequel il aurait signé."""

    def __init__(self, host: str) -> None:
        self.host = host
        self.ensured = 0

    def bucket_exists(self, bucket: str) -> bool:
        self.ensured += 1
        return True

    def presigned_get_object(self, bucket: str, key: str, expires: object) -> str:
        return f"http://{self.host}/{bucket}/{key}"

    def presigned_put_object(self, bucket: str, key: str, expires: object) -> str:
        return f"http://{self.host}/{bucket}/{key}"


@pytest.mark.asyncio
async def test_presigned_url_carries_the_public_host() -> None:
    """Sans client public, l'URL porte l'hôte interne — inutilisable par un navigateur."""
    internal = _RecordingClient("minio:9000")
    public = _RecordingClient("files.ideaxion.app")
    storage = ObjectStorage(internal, "ideaxion", presign_client=public, max_attempts=1)

    url = await storage.apresigned_get("reports/bilan.pdf")

    assert url.startswith("http://files.ideaxion.app/")
    assert "minio:9000" not in url


@pytest.mark.asyncio
async def test_presigned_put_checks_the_bucket_on_the_internal_client() -> None:
    """La vérification du bucket est une vraie requête : elle reste sur l'endpoint interne."""
    internal = _RecordingClient("minio:9000")
    public = _RecordingClient("files.ideaxion.app")
    storage = ObjectStorage(internal, "ideaxion", presign_client=public, max_attempts=1)

    url = await storage.apresigned_put("documents/plan.pdf")

    assert internal.ensured == 1
    assert public.ensured == 0
    assert url.startswith("http://files.ideaxion.app/")


@pytest.mark.asyncio
async def test_without_public_endpoint_the_single_client_signs() -> None:
    """Cas local : interne et public coïncident, aucun client dédié n'est requis."""
    internal = _RecordingClient("localhost:9000")
    storage = ObjectStorage(internal, "ideaxion", max_attempts=1)

    assert (await storage.apresigned_get("k")).startswith("http://localhost:9000/")


@pytest.mark.parametrize(
    ("port", "configured", "expected"),
    [
        (587, None, "starttls"),
        (465, None, "implicit"),  # starttls() sur 465 échoue toujours
        (25, None, "starttls"),
        (465, "starttls", "starttls"),  # la config explicite gagne
        (587, "implicit", "implicit"),
        (587, "none", "none"),
        (587, "n'importe quoi", "starttls"),  # valeur invalide → déduction du port
    ],
)
def test_tls_mode_follows_the_port_then_the_config(port: int, configured: str | None, expected: str) -> None:
    assert _tls_mode(port, configured) == expected
