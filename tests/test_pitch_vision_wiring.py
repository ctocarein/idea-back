"""Wiring vision : _deck_images ne rend les slides QUE si le provider voit les images."""

from __future__ import annotations

import pytest

from app.pitchsim.service import PitchSessionService

_MIN_PDF = (
    b"%PDF-1.1\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


class _Repo:
    session = None


class _Deck:
    source_key = "decks/x/source"
    source_content_type = "application/pdf"


class _Decks:
    def __init__(self, deck):
        self._deck = deck

    async def get_deck(self, _):
        return self._deck


class _Storage:
    def __init__(self, data):
        self._data = data

    async def aget_bytes(self, _key):
        return self._data


class _VisionProvider:
    supports_vision = True


class _TextProvider:
    supports_vision = False


class _PS:
    deck_id = "00000000-0000-0000-0000-0000000000aa"


def _svc(provider, storage, deck=_Deck()) -> PitchSessionService:
    return PitchSessionService(
        _Repo(),
        None,
        None,
        _Decks(deck),
        None,
        provider,
        storage,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_no_images_when_provider_has_no_vision():
    svc = _svc(_TextProvider(), _Storage(_MIN_PDF))
    assert await svc._deck_images(_PS()) == []


@pytest.mark.asyncio
async def test_renders_pdf_to_images_for_vision_provider():
    svc = _svc(_VisionProvider(), _Storage(_MIN_PDF))
    imgs = await svc._deck_images(_PS())
    assert len(imgs) == 1
    assert imgs[0].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_no_images_without_storage():
    svc = _svc(_VisionProvider(), None)
    assert await svc._deck_images(_PS()) == []
