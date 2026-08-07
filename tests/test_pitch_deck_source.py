"""Persistance du deck partagé dans le salon : stockage source + URL présignée + gardes."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.errors import BusinessRuleError
from app.pitchsim.models import PitchDeck
from app.pitchsim.service import PitchSessionService, deck_to_out, store_deck_source

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class FakeStorage:
    def __init__(self) -> None:
        self.puts: dict[str, tuple[bytes, str]] = {}

    async def aput_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        self.puts[key] = (data, content_type)
        return key

    async def apresigned_get(self, key: str, *, expires_seconds: int = 86_400) -> str:
        return f"https://signed/{key}"


class _DummyRepo:
    session = None


class _User:
    id = uuid4()


class _Ctx:
    user = _User()


def _deck(**kw) -> PitchDeck:
    return PitchDeck(id=uuid4(), title="Deck", project_id=None, **kw)


@pytest.mark.asyncio
async def test_store_source_pdf_sets_key():
    deck, st = _deck(), FakeStorage()
    await store_deck_source(st, deck, "application/pdf", b"%PDF-1.4 ...")
    assert deck.source_key == f"pitch-decks/{deck.id}/source"
    assert deck.source_content_type == "application/pdf"
    assert deck.source_key in st.puts


@pytest.mark.asyncio
async def test_store_source_image_sets_key():
    deck, st = _deck(), FakeStorage()
    await store_deck_source(st, deck, "image/png", b"\x89PNG")
    assert deck.source_key is not None


@pytest.mark.asyncio
async def test_store_source_pptx_not_presentable():
    # Le PPTX n'est pas rendu par le navigateur → pas de fichier source visuel.
    deck = _deck()
    await store_deck_source(FakeStorage(), deck, PPTX, b"PK...")
    assert deck.source_key is None


@pytest.mark.asyncio
async def test_store_source_without_storage_is_noop():
    deck = _deck()
    await store_deck_source(None, deck, "application/pdf", b"%PDF")
    assert deck.source_key is None


@pytest.mark.asyncio
async def test_deck_to_out_exposes_presigned_url():
    deck = _deck(source_key="pitch-decks/abc/source", source_content_type="application/pdf")
    out = await deck_to_out(deck, [], FakeStorage())
    assert out.file_url == "https://signed/pitch-decks/abc/source"
    assert out.content_type == "application/pdf"


@pytest.mark.asyncio
async def test_deck_to_out_no_source_no_url():
    out = await deck_to_out(_deck(), [], FakeStorage())
    assert out.file_url is None


def _session_svc() -> PitchSessionService:
    # Seules les portes d'entrée sont testées → repos non atteints.
    return PitchSessionService(_DummyRepo(), None, None, None, None, None, None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_attach_deck_rejects_pptx():
    with pytest.raises(BusinessRuleError):
        await _session_svc().attach_deck(_Ctx(), uuid4(), content_type=PPTX, data=b"x")


@pytest.mark.asyncio
async def test_attach_deck_rejects_empty():
    with pytest.raises(BusinessRuleError):
        await _session_svc().attach_deck(_Ctx(), uuid4(), content_type="application/pdf", data=b"")
