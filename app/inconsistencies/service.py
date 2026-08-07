"""Orchestration de la détection d'incohérences — IDX-INCOH-03.

Un dossier entre, des constats vérifiés sortent. La chaîne complète est :

    contexte (pays, devise, repère de pouvoir d'achat)
      → 2 passes de détection en parallèle (quantitative, textuelle)
      → ancrage des citations dans le récit  (`verification`)
      → déduplication déterministe            (`dedup`)

Les deux dernières étapes sont en CODE et non dans le prompt : la mesure a montré trois fois
qu'une consigne échoue là où une règle déterministe tient (doublons, citation du bloc de
contexte, citation fabriquée).

Robustesse : un dossier ne doit JAMAIS faire tomber un lot. Un audit qui s'arrête au 47ᵉ
dossier sur 300 n'est pas livrable, alors qu'un audit où 3 dossiers sont signalés en échec
l'est parfaitement — à condition de le dire. Les échecs sont donc portés dans le résultat,
jamais avalés.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.inconsistencies.dedup import Finding, InconsistencyType, deduplicate, parse_analysis
from app.inconsistencies.verification import keep_grounded
from app.llm.base import LLMProvider
from app.llm.prompt import (
    INCONSISTENCY_GROUPS,
    INCONSISTENCY_PROMPT_VERSION,
    build_context_prompt,
    build_inconsistency_prompt,
)

logger = get_logger("inconsistencies")

# Dossiers traités simultanément. Chacun consomme jusqu'à 2 appels concurrents : le nombre
# d'appels en vol vaut donc 2 × cette valeur. À ajuster selon les quotas du provider.
DEFAULT_CONCURRENCY = 4

# L'analyse d'un groupe peut lister plusieurs constats avec deux citations chacun : une
# limite trop basse tronque le JSON et fait échouer la passe entière.
_MAX_TOKENS = 1800


@dataclass(frozen=True)
class Dossier:
    """Un dossier à analyser. `reference` est l'identifiant anonymisé qui ira au rapport."""

    reference: str
    narrative: str
    category: str = "?"
    archetype: str = "?"


@dataclass(frozen=True)
class DossierAnalysis:
    reference: str
    findings: list[Finding] = field(default_factory=list)
    context: dict | None = None
    # Constats écartés faute de citations retrouvables dans le récit. Un taux qui grimpe
    # signale une dérive du prompt ou du modèle : à surveiller, jamais à ignorer.
    dropped: int = 0
    failed_passes: int = 0
    llm_calls: int = 0
    error: str | None = None

    @property
    def is_clean(self) -> bool:
        """Vrai si le dossier a été analysé sans qu'aucune incohérence ne soit relevée."""
        return self.error is None and not self.findings


@dataclass(frozen=True)
class BatchSummary:
    analyzed: int
    with_findings: int
    clean: int
    failed: int
    total_findings: int
    by_type: dict[str, int]
    llm_calls: int


class InconsistencyService:
    """Détecte les incohérences internes d'un dossier, ou d'un lot de dossiers."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        concurrency: int = DEFAULT_CONCURRENCY,
        detect_context: bool = True,
    ) -> None:
        if concurrency < 1:
            raise ValueError("La concurrence doit être au moins de 1.")
        self._provider = provider
        self._concurrency = concurrency
        self._detect_context = detect_context

    async def _ask(self, prompt: str) -> dict | None:
        try:
            return await self._provider.analyze_json(prompt, max_tokens=_MAX_TOKENS)
        except Exception as exc:  # provider indisponible, quota, JSON illisible…
            logger.warning("inconsistency_pass_failed", error=f"{type(exc).__name__}: {exc}")
            return None

    async def _detect_dossier_context(self, dossier: Dossier) -> dict | None:
        if not self._detect_context:
            return None
        raw = await self._ask(build_context_prompt(narrative=dossier.narrative))
        # Un contexte absent n'est pas une erreur : le prompt de détection sait alors qu'il
        # ne doit juger ni le pouvoir d'achat ni les obligations réglementaires.
        return raw if isinstance(raw, dict) and raw.get("country") else None

    async def analyze(self, dossier: Dossier) -> DossierAnalysis:
        calls = 0
        context = await self._detect_dossier_context(dossier)
        if self._detect_context:
            calls += 1

        prompts = [
            build_inconsistency_prompt(
                narrative=dossier.narrative,
                group=group,
                category=dossier.category,
                archetype=dossier.archetype,
                context=context,
            )
            for group in INCONSISTENCY_GROUPS
        ]
        outputs = await asyncio.gather(*(self._ask(prompt) for prompt in prompts))
        calls += len(prompts)

        failed = sum(1 for output in outputs if output is None)
        if failed == len(prompts):
            logger.error("inconsistency_dossier_failed", reference=dossier.reference, calls=calls)
            return DossierAnalysis(
                reference=dossier.reference,
                context=context,
                failed_passes=failed,
                llm_calls=calls,
                error="toutes les passes de détection ont échoué",
            )

        parsed: list[Finding] = []
        for output in outputs:
            if output is not None:
                parsed.extend(parse_analysis(output))

        grounded, dropped = keep_grounded(parsed, dossier.narrative)
        findings = deduplicate(grounded)

        logger.info(
            "inconsistency_dossier_analyzed",
            reference=dossier.reference,
            findings=len(findings),
            dropped=len(dropped),
            failed_passes=failed,
            calls=calls,
            prompt_version=INCONSISTENCY_PROMPT_VERSION,
        )
        return DossierAnalysis(
            reference=dossier.reference,
            findings=findings,
            context=context,
            dropped=len(dropped),
            failed_passes=failed,
            llm_calls=calls,
        )

    async def analyze_batch(self, dossiers: Sequence[Dossier]) -> list[DossierAnalysis]:
        """Analyse un lot. Un dossier en échec est rapporté, il n'interrompt jamais le lot."""
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _run(dossier: Dossier) -> DossierAnalysis:
            async with semaphore:
                try:
                    return await self.analyze(dossier)
                except Exception as exc:  # dernier filet : le lot doit aboutir
                    logger.error(
                        "inconsistency_dossier_crashed",
                        reference=dossier.reference,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    return DossierAnalysis(
                        reference=dossier.reference,
                        error=f"{type(exc).__name__}: {exc}",
                    )

        return await asyncio.gather(*(_run(dossier) for dossier in dossiers))


def summarize(analyses: Sequence[DossierAnalysis]) -> BatchSummary:
    """Agrège un lot — c'est la matière de l'en-tête du rapport d'audit.

    `clean` porte la phrase qui distingue un audit d'une machine à accuser : « N dossiers sur
    M ne présentent aucune incohérence détectée ».
    """
    by_type: dict[str, int] = {type_.value: 0 for type_ in InconsistencyType}
    for analysis in analyses:
        for finding in analysis.findings:
            by_type[finding.type.value] += 1

    failed = sum(1 for analysis in analyses if analysis.error is not None)
    return BatchSummary(
        analyzed=len(analyses) - failed,
        with_findings=sum(1 for analysis in analyses if analysis.error is None and analysis.findings),
        clean=sum(1 for analysis in analyses if analysis.is_clean),
        failed=failed,
        total_findings=sum(len(analysis.findings) for analysis in analyses),
        by_type={key: count for key, count in by_type.items() if count},
        llm_calls=sum(analysis.llm_calls for analysis in analyses),
    )
