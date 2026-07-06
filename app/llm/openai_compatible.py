"""Provider compatible OpenAI (`/chat/completions`) — base de DeepSeek/Mistral/OpenAI.

Enveloppé par app/core/resilience : timeout par appel, retry sur erreurs transitoires
(5xx, réseau, timeout), circuit breaker (bascule en mode dégradé après N échecs). Les
erreurs 4xx (clé invalide, requête fautive) ne sont PAS rejouées.

Reproductibilité : température basse + `prompt_version` figé côté appelant ; la sortie
brute de chaque passe est stockée dans le `ScoreRun` (rejouable).
"""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.core.resilience import CircuitBreaker, RetryPolicy, with_retry
from app.llm.base import LLMError, LLMResult, TransientLLMError
from app.llm.parsing import extract_json_object

logger = get_logger("llm")


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float = 30.0,
        vision_model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model = model
        # Modèle multimodal (voit les slides). None → le provider ne fait pas de vision.
        self.vision_model = vision_model
        self.supports_vision = vision_model is not None
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        # Un circuit par modèle : 3 échecs consécutifs → ouvert → mode dégradé.
        self._breaker = CircuitBreaker(name=f"llm:{model}", failure_threshold=3)
        # Les erreurs httpx sont traduites en TransientLLMError ci-dessous : le reste du
        # système (retry, fallback) ne manipule que des exceptions LLM, jamais httpx.
        self._retry = RetryPolicy(max_attempts=3, base_delay=0.5, retry_on=(TransientLLMError,))

    async def _chat(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        payload: dict = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"

        async def _operation() -> dict:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                    resp = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise TransientLLMError(f"{self.model} timeout") from exc
            except httpx.TransportError as exc:
                raise TransientLLMError(f"{self.model} réseau : {exc}") from exc
            except httpx.HTTPError as exc:  # autre erreur httpx → non transitoire
                raise LLMError(f"{self.model} http : {exc}") from exc
            if resp.status_code >= 500:
                # Transitoire : on rejoue.
                raise TransientLLMError(f"{self.model} 5xx : {resp.status_code}")
            if resp.status_code >= 400:
                # Permanent (clé, quota, requête) : pas de retry.
                raise LLMError(f"{self.model} {resp.status_code} : {resp.text[:200]}")
            return resp.json()

        # Circuit breaker autour de l'opération retryée.
        return await self._breaker.call(lambda: with_retry(_operation, self._retry, op_name=self.model))

    async def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMResult:
        data = await self._chat([{"role": "user", "content": prompt}])
        message = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        return LLMResult(
            text=message,
            model=self.model,
            usage={k: int(v) for k, v in usage.items() if isinstance(v, int)},
        )

    async def analyze_json(
        self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None
    ) -> dict:
        # Demande une réponse JSON et la parse strictement (sortie malformée → LLMParseError).
        messages = [
            {"role": "system", "content": "Réponds STRICTEMENT en JSON valide, sans texte autour."},
            {"role": "user", "content": prompt},
        ]
        data = await self._chat(messages, json_mode=True, max_tokens=max_tokens)
        content = data["choices"][0]["message"]["content"]
        return extract_json_object(content)

    async def analyze_json_with_images(
        self, prompt: str, *, images: list[str], schema: dict | None = None
    ) -> dict:
        """Comme analyze_json, mais le comité VOIT les slides (vision multimodale).

        `images` : data URLs base64 (`data:image/png;base64,...`). Utilise le modèle vision
        (Pixtral pour Mistral). Si aucun modèle vision n'est configuré, on dégrade en texte seul.
        """
        if not self.vision_model or not images:
            return await self.analyze_json(prompt, schema=schema)
        content: list[dict] = [{"type": "text", "text": prompt}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages: list[dict] = [
            {"role": "system", "content": "Réponds STRICTEMENT en JSON valide, sans texte autour."},
            {"role": "user", "content": content},
        ]
        data = await self._chat(messages, json_mode=True, model=self.vision_model)
        out = data["choices"][0]["message"]["content"]
        return extract_json_object(out)
