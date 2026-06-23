"""Tests du parsing JSON strict des sorties LLM (pur, hors-ligne)."""

from __future__ import annotations

import pytest

from app.llm.base import LLMParseError
from app.llm.parsing import extract_json_object


def test_plain_json() -> None:
    assert extract_json_object('{"axes": {"probleme": 70}}') == {"axes": {"probleme": 70}}


def test_strips_code_fence() -> None:
    raw = '```json\n{"axes": {"marche": 60}}\n```'
    assert extract_json_object(raw) == {"axes": {"marche": 60}}


def test_extracts_object_from_surrounding_text() -> None:
    raw = 'Voici le résultat : {"axes": {"modele": 40}} — fin.'
    assert extract_json_object(raw) == {"axes": {"modele": 40}}


def test_empty_raises() -> None:
    with pytest.raises(LLMParseError):
        extract_json_object("   ")


def test_invalid_json_raises() -> None:
    with pytest.raises(LLMParseError):
        extract_json_object("pas du tout du json")


def test_non_object_raises() -> None:
    with pytest.raises(LLMParseError):
        extract_json_object("[1, 2, 3]")
