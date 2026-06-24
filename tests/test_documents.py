"""Garde-fous du service documents — testés avant tout accès DB/MinIO.

`request_upload_url` valide le type PUIS exige le storage AVANT de toucher le dépôt :
on peut donc vérifier ces deux portes avec un dépôt factice et `storage=None`.
"""

from __future__ import annotations

import pytest

from app.core.errors import BusinessRuleError
from app.documents.schemas import MAX_SIZE_BYTES, UploadUrlIn
from app.documents.service import DocumentService


class _DummyRepo:
    session = None  # jamais atteint : les deux portes lèvent avant repo.create


def _service(storage=None) -> DocumentService:
    return DocumentService(_DummyRepo(), storage)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rejects_disallowed_content_type():
    svc = _service(storage=None)
    data = UploadUrlIn(filename="malware.exe", content_type="application/x-msdownload", size=10)
    with pytest.raises(BusinessRuleError):
        await svc.request_upload_url(_ctx(), data)


@pytest.mark.asyncio
async def test_requires_storage_configured():
    svc = _service(storage=None)
    data = UploadUrlIn(filename="bp.pdf", content_type="application/pdf", size=1024)
    with pytest.raises(BusinessRuleError):
        await svc.request_upload_url(_ctx(), data)


def test_size_limit_enforced_by_schema():
    with pytest.raises(ValueError):
        UploadUrlIn(filename="big.pdf", content_type="application/pdf", size=MAX_SIZE_BYTES + 1)


class _User:
    id = "00000000-0000-0000-0000-000000000001"


class _Ctx:
    user = _User()


def _ctx() -> _Ctx:
    return _Ctx()
