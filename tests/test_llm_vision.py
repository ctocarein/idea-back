"""Vision multimodale (provider compatible OpenAI / Mistral-Pixtral) : le comité voit les slides."""

from __future__ import annotations

import pytest

from app.llm.fallback import FallbackProvider
from app.llm.openai_compatible import OpenAICompatibleProvider


def _provider(vision_model: str | None = None) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="k", base_url="https://x/v1", model="text-model", vision_model=vision_model
    )


@pytest.mark.asyncio
async def test_vision_sends_image_parts_with_vision_model():
    p = _provider(vision_model="pixtral-12b-2409")
    assert p.supports_vision is True
    captured: dict = {}

    async def fake_chat(messages, *, json_mode=False, model=None):
        captured.update(messages=messages, json_mode=json_mode, model=model)
        return {"choices": [{"message": {"content": '{"axes": {"d1": 7}}'}}]}

    p._chat = fake_chat  # type: ignore[method-assign]
    out = await p.analyze_json_with_images(
        "Juge le deck.", images=["data:image/png;base64,AAA"]
    )
    assert out == {"axes": {"d1": 7}}
    # On a bien basculé sur le modèle vision + JSON mode.
    assert captured["model"] == "pixtral-12b-2409"
    assert captured["json_mode"] is True
    # Le message user porte une part image + une part texte.
    parts = captured["messages"][-1]["content"]
    assert any(part.get("type") == "image_url" for part in parts)
    assert any(part.get("type") == "text" for part in parts)


@pytest.mark.asyncio
async def test_vision_degrades_to_text_without_vision_model():
    p = _provider(vision_model=None)
    assert p.supports_vision is False
    captured: dict = {}

    async def fake_chat(messages, *, json_mode=False, model=None):
        captured.update(messages=messages, model=model)
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    p._chat = fake_chat  # type: ignore[method-assign]
    out = await p.analyze_json_with_images("x", images=["data:image/png;base64,AAA"])
    assert out == {"ok": True}
    # Texte seul : pas d'override de modèle, content est une chaîne (pas de parts image).
    assert captured["model"] is None
    assert isinstance(captured["messages"][-1]["content"], str)


class _FakeVision:
    model = "pixtral"
    supports_vision = True

    async def analyze_json_with_images(self, prompt, *, images, schema=None):
        return {"saw": len(images)}

    async def analyze_json(self, prompt, *, schema=None):
        return {"text_only": True}


class _FakeText:
    model = "text"
    supports_vision = False

    async def analyze_json(self, prompt, *, schema=None):
        return {"text_only": True}


@pytest.mark.asyncio
async def test_fallback_exposes_vision_and_delegates_to_capable_provider():
    fb = FallbackProvider([_FakeVision(), _FakeText()])
    assert fb.supports_vision is True
    out = await fb.analyze_json_with_images("x", images=["a", "b"])
    assert out == {"saw": 2}


@pytest.mark.asyncio
async def test_fallback_without_vision_degrades_to_text():
    fb = FallbackProvider([_FakeText()])
    assert fb.supports_vision is False
    out = await fb.analyze_json_with_images("x", images=["a"])
    assert out == {"text_only": True}
