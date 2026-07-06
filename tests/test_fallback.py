"""Tests du fallback multi-provider — bascule à l'échec, primaire prioritaire."""

from __future__ import annotations

import asyncio

import pytest

from app.core.resilience import CircuitOpenError
from app.llm.base import LLMError, LLMResult, TransientLLMError
from app.llm.fallback import FallbackProvider


class _Failing:
    model = "failing"

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        self.calls += 1
        raise self.exc

    async def analyze_json(self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None) -> dict:
        self.calls += 1
        raise self.exc


class _Working:
    model = "working"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        self.calls += 1
        return LLMResult(text="ok", model=self.model)

    async def analyze_json(self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None) -> dict:
        self.calls += 1
        return {"axes": {"x": 1}}


def test_falls_over_on_llm_error() -> None:
    bad, good = _Failing(LLMError("boom")), _Working()
    out = asyncio.run(FallbackProvider([bad, good]).analyze_json("p"))
    assert out == {"axes": {"x": 1}}
    assert bad.calls == 1 and good.calls == 1


def test_falls_over_on_open_circuit() -> None:
    bad, good = _Failing(CircuitOpenError("open")), _Working()
    assert asyncio.run(FallbackProvider([bad, good]).analyze_json("p")) == {"axes": {"x": 1}}


def test_transient_error_triggers_failover() -> None:
    bad, good = _Failing(TransientLLMError("5xx")), _Working()
    assert asyncio.run(FallbackProvider([bad, good]).analyze_json("p")) == {"axes": {"x": 1}}


def test_primary_used_when_healthy() -> None:
    good, never = _Working(), _Failing(LLMError("x"))
    asyncio.run(FallbackProvider([good, never]).complete("p"))
    assert good.calls == 1 and never.calls == 0


def test_all_failing_raises_last_error() -> None:
    a, b = _Failing(LLMError("a")), _Failing(LLMError("b"))
    with pytest.raises(LLMError):
        asyncio.run(FallbackProvider([a, b]).analyze_json("p"))
