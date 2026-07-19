"""Orchestration de la détection — robustesse du lot et ancrage des constats.

Tests hors-ligne : le provider est un double. On ne mesure pas ici la qualité de détection
(c'est le rôle du banc et du corpus), mais le COMPORTEMENT de l'orchestration.
"""

from __future__ import annotations

import asyncio

import pytest

from app.inconsistencies.dedup import InconsistencyType
from app.inconsistencies.service import Dossier, InconsistencyService, summarize

NARRATIVE = (
    "AgriLink. Nous avons lancé il y a un an. Aujourd'hui, 1 200 producteurs sont abonnés à "
    "5 000 FCFA par mois, ce qui nous fait environ 400 000 FCFA de chiffre d'affaires mensuel. "
    "L'équipe, c'est mon associé et moi."
)

QUOTE_A = "1 200 producteurs sont abonnés à 5 000 FCFA par mois"
QUOTE_B = "environ 400 000 FCFA de chiffre d'affaires mensuel"


def _analysis_payload(type_: str = "arithmetic", quote_a: str = QUOTE_A, quote_b: str = QUOTE_B) -> dict:
    return {
        "analysis": [
            {
                "type": type_,
                "found": True,
                "contradictions": [
                    {
                        "quote_a": quote_a,
                        "quote_b": quote_b,
                        "explanation": "1200 × 5000 = 6 000 000, pas 400 000.",
                        "severity": "high",
                    }
                ],
            }
        ]
    }


class FakeProvider:
    """Provider scriptable : on décide ce que renvoie chaque appel, ou s'il échoue."""

    model = "fake"

    def __init__(self, *, context: dict | None = None, responses: list | None = None) -> None:
        self._context = context if context is not None else {"country": "Côte d'Ivoire", "currency": "XOF"}
        self._responses = responses
        self.prompts: list[str] = []

    async def complete(self, prompt: str, *, max_tokens: int = 1024):  # pragma: no cover
        raise NotImplementedError

    async def analyze_json(self, prompt: str, *, schema: dict | None = None, max_tokens: int | None = None) -> dict:
        self.prompts.append(prompt)
        if "FORMAT=context." in prompt:
            if isinstance(self._context, Exception):
                raise self._context
            return self._context
        if self._responses is None:
            return _analysis_payload()
        index = len([p for p in self.prompts if "FORMAT=context." not in p]) - 1
        response = self._responses[min(index, len(self._responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


def _service(provider: FakeProvider, **kwargs) -> InconsistencyService:
    return InconsistencyService(provider, **kwargs)


class TestAnalyse:
    def test_un_dossier_produit_des_constats_dedupliques(self) -> None:
        provider = FakeProvider()
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        # Les deux passes renvoient le MÊME constat : la déduplication n'en garde qu'un.
        assert len(result.findings) == 1
        assert result.findings[0].type is InconsistencyType.ARITHMETIC
        assert result.error is None

    def test_trois_appels_par_dossier(self) -> None:
        # 1 contexte + 2 groupes. C'est la base du coût par dossier (cf. marge, H2.3).
        provider = FakeProvider()
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.llm_calls == 3

    def test_le_contexte_peut_etre_desactive(self) -> None:
        provider = FakeProvider()
        result = asyncio.run(_service(provider, detect_context=False).analyze(Dossier("D-01", NARRATIVE)))
        assert result.llm_calls == 2
        assert result.context is None

    def test_contexte_en_echec_nempeche_pas_lanalyse(self) -> None:
        # Sans juridiction, le prompt sait qu'il ne doit pas juger le pouvoir d'achat.
        provider = FakeProvider(context=RuntimeError("provider down"))
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.context is None
        assert result.error is None
        assert len(result.findings) == 1

    def test_contexte_sans_pays_est_traite_comme_absent(self) -> None:
        provider = FakeProvider(context={"country": None, "currency": None})
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.context is None

    def test_une_passe_en_echec_laisse_lautre_produire(self) -> None:
        provider = FakeProvider(responses=[RuntimeError("timeout"), _analysis_payload()])
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.failed_passes == 1
        assert result.error is None
        assert len(result.findings) == 1

    def test_toutes_les_passes_en_echec_marque_le_dossier(self) -> None:
        provider = FakeProvider(responses=[RuntimeError("boom"), RuntimeError("boom")])
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.error is not None
        assert result.findings == []
        assert not result.is_clean  # un échec n'est PAS un dossier propre

    def test_constat_aux_citations_introuvables_est_ecarte(self) -> None:
        # Citation du bloc de contexte ou fabriquée : invérifiable par le client.
        payload = _analysis_payload(quote_a="Le revenu d'un ménage modeste ≈ 100 000 XOF")
        provider = FakeProvider(responses=[payload, payload])
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.findings == []
        assert result.dropped == 2
        assert result.error is None  # écarter n'est pas échouer

    def test_dossier_sans_incoherence_est_propre(self) -> None:
        empty = {"analysis": [{"type": "arithmetic", "found": False, "contradictions": []}]}
        provider = FakeProvider(responses=[empty, empty])
        result = asyncio.run(_service(provider).analyze(Dossier("D-01", NARRATIVE)))
        assert result.is_clean


class TestLot:
    def test_un_dossier_en_echec_ninterrompt_pas_le_lot(self) -> None:
        # Exigence de la DoD : un audit qui s'arrête au 47ᵉ dossier sur 300 n'est pas livrable.
        class Flaky(FakeProvider):
            async def analyze_json(self, prompt, *, schema=None, max_tokens=None):
                if "AgriLink-KO" in prompt:
                    raise RuntimeError("provider down")
                return await super().analyze_json(prompt, schema=schema, max_tokens=max_tokens)

        dossiers = [
            Dossier("D-01", NARRATIVE),
            Dossier("D-02", NARRATIVE.replace("AgriLink", "AgriLink-KO")),
            Dossier("D-03", NARRATIVE),
        ]
        results = asyncio.run(_service(Flaky()).analyze_batch(dossiers))
        assert len(results) == 3
        assert [r.reference for r in results] == ["D-01", "D-02", "D-03"]
        assert results[1].error is not None
        assert results[0].error is None and results[2].error is None

    def test_la_concurrence_est_bornee(self) -> None:
        peak = 0
        current = 0

        class Counting(FakeProvider):
            async def analyze_json(self, prompt, *, schema=None, max_tokens=None):
                nonlocal peak, current
                current += 1
                peak = max(peak, current)
                await asyncio.sleep(0)
                current -= 1
                return await super().analyze_json(prompt, schema=schema, max_tokens=max_tokens)

        dossiers = [Dossier(f"D-{i:02d}", NARRATIVE) for i in range(10)]
        asyncio.run(_service(Counting(), concurrency=2).analyze_batch(dossiers))
        # 2 dossiers en vol, chacun jusqu'à 2 passes simultanées.
        assert peak <= 4

    def test_concurrence_invalide_est_refusee(self) -> None:
        with pytest.raises(ValueError):
            InconsistencyService(FakeProvider(), concurrency=0)

    def test_lot_vide(self) -> None:
        assert asyncio.run(_service(FakeProvider()).analyze_batch([])) == []


class TestSynthese:
    def test_compte_les_propres_les_signales_et_les_echecs(self) -> None:
        empty = {"analysis": [{"type": "market", "found": False, "contradictions": []}]}

        class Mixed(FakeProvider):
            async def analyze_json(self, prompt, *, schema=None, max_tokens=None):
                self.prompts.append(prompt)
                if "FORMAT=context." in prompt:
                    return {"country": "France", "currency": "EUR"}
                if "D-CLEAN" in prompt:
                    return empty
                if "D-KO" in prompt:
                    raise RuntimeError("down")
                return _analysis_payload()

        dossiers = [
            Dossier("D-01", NARRATIVE),
            Dossier("D-02", NARRATIVE.replace("AgriLink", "D-CLEAN")),
            Dossier("D-03", NARRATIVE.replace("AgriLink", "D-KO")),
        ]
        summary = summarize(asyncio.run(_service(Mixed()).analyze_batch(dossiers)))
        assert summary.analyzed == 2
        assert summary.with_findings == 1
        assert summary.clean == 1  # la phrase « N dossiers ne présentent aucune incohérence »
        assert summary.failed == 1
        assert summary.by_type == {"arithmetic": 1}

    def test_synthese_dun_lot_vide(self) -> None:
        summary = summarize([])
        assert summary.analyzed == 0
        assert summary.by_type == {}
