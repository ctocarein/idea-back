"""Garde-fous du service deck — validés avant tout parsing/DB."""

from __future__ import annotations

import pytest

from app.core.errors import BusinessRuleError
from app.pitchsim.models import SlideKind
from app.pitchsim.service import PitchDeckService


class _DummyRepo:
    session = None  # jamais atteint : les portes lèvent avant


def _svc() -> PitchDeckService:
    return PitchDeckService(_DummyRepo(), None)  # type: ignore[arg-type]


class _User:
    id = "00000000-0000-0000-0000-000000000001"


class _Ctx:
    user = _User()


@pytest.mark.asyncio
async def test_rejects_unsupported_type():
    with pytest.raises(BusinessRuleError):
        await _svc().create_deck(_Ctx(), title="x", project_id=None, content_type="text/plain", data=b"abc")


@pytest.mark.asyncio
async def test_rejects_empty_file():
    with pytest.raises(BusinessRuleError):
        await _svc().create_deck(_Ctx(), title="x", project_id=None, content_type="application/pdf", data=b"")


@pytest.mark.asyncio
async def test_main_kind_not_allowed_on_add_slides():
    # Le deck principal se crée via create_deck, pas via add_slides.
    with pytest.raises(BusinessRuleError):
        await _svc().add_slides(
            _Ctx(),
            "00000000-0000-0000-0000-0000000000aa",  # type: ignore[arg-type]
            kind=SlideKind.MAIN,
            content_type="application/pdf",
            data=b"x",
        )
