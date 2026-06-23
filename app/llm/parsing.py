"""Parsing JSON STRICT des sorties LLM (pur, sans réseau).

Robustesse : une sortie malformée lève `LLMParseError` (→ retry/revue), jamais un score
corrompu. Tolère seulement les enrobages bénins (fences ```json), pas le JSON invalide.
"""

from __future__ import annotations

import json
import re

from app.llm.base import LLMParseError

_FENCE_OPEN = re.compile(r"^```[a-zA-Z]*\n?")
_FENCE_CLOSE = re.compile(r"\n?```$")
_FIRST_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(content: str) -> dict:
    # Renvoie l'objet JSON contenu dans `content`, ou lève LLMParseError.
    if not content or not content.strip():
        raise LLMParseError("Réponse LLM vide.")
    text = content.strip()

    # Retire un éventuel bloc de code ```json ... ```.
    if text.startswith("```"):
        text = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", text)).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Dernier recours : isoler le premier objet {...}.
        match = _FIRST_OBJECT.search(text)
        if match is None:
            raise LLMParseError("Aucun objet JSON dans la réponse LLM.") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"JSON invalide : {exc}") from exc

    if not isinstance(data, dict):
        raise LLMParseError("Objet JSON attendu (dict).")
    return data
