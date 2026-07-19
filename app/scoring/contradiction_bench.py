"""Banc d'essai du détecteur de contradictions — vérification « Magicien d'Oz ».

On soumet des RÉCITS réalistes de porteurs, dont on connaît d'avance les contradictions
plantées (le corrigé), et on regarde ce que le modèle trouve. C'est un humain qui décide
ensuite si une détection correspond bien à une contradiction attendue : aucun appariement
automatique n'est tenté ici, il fausserait le jugement.

Le corpus contient un CONTRÔLE PROPRE (dossier honnête, sans contradiction). Toute détection
sur ce cas est un FAUX POSITIF. Pour un produit d'audit, la PRÉCISION prime sur le rappel :
rater une contradiction est un manque à gagner, en inventer une est un accident industriel.
L'objectif d'ingénierie est donc « monter le rappel en maintenant les faux positifs à zéro ».

Variantes comparables sur le même corpus :
  v1     — passe unique libre (2/8, 0 faux positif)
  v2a    — passe unique exhaustive (4/8, mais faux positifs systématiques : DISQUALIFIÉE)
  v2abis — types procéduraux (4/8, 0 faux positif, mais perd l'arithmétique)
  v2b    — une passe focalisée par type (0/8 : sur-permissive, elle n'ose plus rien signaler)
  v2c    — deux passes de 3 types + contexte pays/devise (9/10, 0 faux positif) ← PRODUCTION

Les variantes v1 à v2b sont des BASELINES HISTORIQUES gelées : leurs prompts restent locaux,
avec leurs clés françaises d'origine, pour que les mesures passées restent rejouables.
La v2c, elle, appelle les prompts promus dans `app/llm/prompt.py` — le banc mesure donc
exactement ce qui tourne en production, et non une copie qui pourrait diverger.

    python -m app.scoring.contradiction_bench --variant v2c --runs 3
    python -m app.scoring.contradiction_bench --variant v2c --case tontine-fintech --raw
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.inconsistencies.dedup import Finding, deduplicate, parse_analysis, parse_findings
from app.inconsistencies.verification import keep_grounded
from app.llm.factory import get_llm
from app.llm.prompt import (
    INCONSISTENCY_GROUPS,
    INCONSISTENCY_PROMPT_VERSION,
    build_context_prompt,
    build_inconsistency_prompt,
)

_DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "calibration" / "contradiction_corpus.json"

VARIANTS = ("v1", "v2a", "v2abis", "v2b", "v2cfr", "v2c")

# Types de contradiction recherchés. La consigne de recherche est spécifique à chaque type :
# c'est elle qui porte le gain attendu de la v2a (exhaustivité) et de la v2b (focalisation).
TYPES: dict[str, str] = {
    "arithmetique": (
        "deux chiffres du récit sont incompatibles. RECALCULE systématiquement : tout produit "
        "volume x prix unitaire doit être comparé au chiffre d'affaires déclaré ; toute somme "
        "de parts doit être comparée au total annoncé."
    ),
    "temporelle": (
        "une durée ou une date rend une affirmation impossible. COMPARE entre elles toutes les "
        "durées du récit (ancienneté du projet, historique invoqué, durée d'expérience)."
    ),
    "capacite": (
        "l'ampleur annoncée est incompatible avec l'équipe ou les moyens décrits. Confronte "
        "la taille de l'équipe et les ressources aux volumes, couvertures ou fréquences annoncés."
    ),
    "marche": (
        "la cible, le prix ou la concurrence décrits sont mutuellement incohérents. Confronte "
        "le pouvoir d'achat de la cible déclarée au prix annoncé."
    ),
    "interne": (
        "deux passages du récit se contredisent directement. Relis le récit en cherchant deux "
        "affirmations qui ne peuvent pas être vraies en même temps."
    ),
    "reglementaire": (
        "l'activité décrite implique une obligation que le récit nie. Vérifie notamment la "
        "détention de fonds de tiers, les données sensibles et les actes réservés."
    ),
}

# v2a-bis : chaque type devient une PROCÉDURE exécutable, pas une exhortation. Le banc a montré
# que « RECALCULE tout produit volume x prix » fonctionne (C1 attrapé) là où « COMPARE les durées »
# échoue (C3 raté) — la différence est qu'une procédure donne des étapes, pas une intention.
TYPES_PROC: dict[str, str] = {
    "arithmetique": (
        "PROCÉDURE : (1) relève tout couple volume + prix unitaire ; (2) calcule le produit ; "
        "(3) compare-le au chiffre d'affaires ou au revenu déclaré ; (4) signale tout écart."
    ),
    "temporelle": (
        "PROCÉDURE : (1) relève TOUTES les dates, durées et anciennetés du récit (depuis quand le "
        "projet existe, quelle profondeur d'historique est invoquée, quelle durée d'expérience) ; "
        "(2) compare-les deux à deux ; (3) signale toute paire où l'une rend l'autre impossible — "
        "par exemple un historique de données plus long que l'ancienneté du projet lui-même."
    ),
    "capacite": (
        "PROCÉDURE : (1) relève la taille exacte de l'équipe et les moyens déclarés ; (2) relève "
        "tous les volumes, couvertures géographiques et fréquences annoncés ; (3) confronte les "
        "deux et signale ce qui excède manifestement les moyens décrits."
    ),
    "marche": (
        "PROCÉDURE : (1) relève la cible déclarée et le pouvoir d'achat qu'elle implique ; "
        "(2) relève le prix annoncé ; (3) vérifie leur compatibilité."
    ),
    "interne": (
        "PROCÉDURE : (1) repère toute affirmation ABSOLUE ou d'unicité (« aucun concurrent », "
        "« personne ne fait », « le seul », « déjà N utilisateurs », « validé par ») ; (2) relis "
        "le RESTE du récit en cherchant une phrase qui la dément ou la contredit ; (3) signale la paire."
    ),
    "reglementaire": (
        "PROCÉDURE : (1) repère toute activité impliquant une obligation légale — détention de "
        "fonds de tiers, collecte d'épargne, données de santé, acte réservé à une profession ; "
        "(2) vérifie si le récit nie, ignore ou contourne cette obligation."
    ),
}

_ANTI_FP = [
    "RÈGLE ABSOLUE — un MANQUE d'information n'est PAS une contradiction.",
    "Un récit incomplet, vague, modeste ou prudent est NORMAL à ce stade d'un projet.",
    "Un porteur qui reconnaît ce qu'il ne sait pas encore est honnête, pas contradictoire :",
    "ne le signale JAMAIS pour ça. Une faiblesse du projet n'est pas une contradiction non plus.",
]

_CITATION_RULE = [
    "Pour CHAQUE contradiction, cite les DEUX passages en conflit, mot pour mot, tirés du récit.",
    "N'invente jamais un passage : si tu ne peux pas citer les deux, ne signale rien.",
]


def _header(category: str, archetype: str) -> list[str]:
    return [
        "Rédige TOUTE ta réponse en français.",
        "Tu es un analyste de dossiers entrepreneuriaux, rigoureux et strictement factuel.",
        f"Catégorie : {category} · Archétype : {archetype}.",
        "Tu ne notes rien, tu n'évalues pas la qualité du projet, tu ne donnes aucun conseil.",
    ]


def build_v1(*, recit: str, category: str, archetype: str) -> str:
    lines = [
        "FORMAT=contradictions.",
        *_header(category, archetype),
        "",
        "Ta SEULE tâche : repérer les CONTRADICTIONS INTERNES du récit ci-dessous.",
        "",
        *_ANTI_FP,
        "",
        "TYPES DE CONTRADICTION :",
        *[f"- {key} : {desc.split('.')[0]}." for key, desc in TYPES.items()],
        "",
        *_CITATION_RULE,
        "",
        "Si le récit ne contient AUCUNE contradiction, renvoie une liste VIDE.",
        "C'est un résultat parfaitement acceptable et attendu pour un dossier honnête.",
        "",
        "RÉCIT DU PORTEUR :",
        recit,
        "",
        "Réponds STRICTEMENT en JSON :",
        '{ "contradictions": [ { "type": "<un des types>", "passage_a": "<citation>",',
        '  "passage_b": "<citation>", "explication": "<1 phrase>", "gravite": "haute|moyenne|basse" } ] }',
    ]
    return "\n".join(lines)


def build_v2a(*, recit: str, category: str, archetype: str) -> str:
    # Exhaustivité FORCÉE PAR LE SCHÉMA : le modèle doit produire une entrée par type,
    # ce qui l'empêche structurellement de s'arrêter à la première trouvaille.
    lines = [
        "FORMAT=contradictions_exhaustif.",
        *_header(category, archetype),
        "",
        "Ta tâche : passer en revue CHAQUE type de contradiction ci-dessous, l'un APRÈS l'autre,",
        "et te prononcer sur CHACUN. Tu dois produire une entrée par type, même quand tu ne",
        "trouves rien — dans ce cas `trouve` vaut false et la liste est vide.",
        "Ne t'arrête JAMAIS après une première trouvaille : continue jusqu'au dernier type.",
        "",
        *_ANTI_FP,
        "",
        "TYPES À EXAMINER, DANS CET ORDRE :",
        *[f"- {key} : {desc}" for key, desc in TYPES.items()],
        "",
        *_CITATION_RULE,
        "",
        "RÉCIT DU PORTEUR :",
        recit,
        "",
        "Réponds STRICTEMENT en JSON, avec les 6 types dans l'ordre :",
        '{ "analyse": [ { "type": "<type>", "trouve": <true|false>, "contradictions": [',
        '  { "passage_a": "<citation>", "passage_b": "<citation>",',
        '    "explication": "<1 phrase>", "gravite": "haute|moyenne|basse" } ] } ] }',
    ]
    return "\n".join(lines)


def build_v2abis(*, recit: str, category: str, archetype: str) -> str:
    # v2a + 3 correctifs : types procéduraux, anti-faux-positif explicite, anti-doublon.
    lines = [
        "FORMAT=contradictions_exhaustif.",
        *_header(category, archetype),
        "",
        "Ta tâche : appliquer CHAQUE procédure ci-dessous, l'une APRÈS l'autre, et te prononcer",
        "sur CHACUNE. Tu dois produire une entrée par type, même quand tu ne trouves rien.",
        "Ne t'arrête JAMAIS après une première trouvaille : va jusqu'au dernier type.",
        "",
        *_ANTI_FP,
        "",
        "N'émets une contradiction QUE si tu CONCLUS à une incohérence.",
        "Si ta vérification confirme que tout est cohérent, c'est un SUCCÈS de la vérification :",
        "`trouve` vaut false et la liste reste VIDE. N'utilise JAMAIS le champ `contradictions`",
        "pour exposer un calcul qui tombe juste ou une vérification qui passe.",
        "",
        "ANTI-DOUBLON : une même contradiction ne doit apparaître qu'UNE seule fois, sous le type",
        "le PLUS SPÉCIFIQUE. Si tu l'as déjà signalée sous un type, ne la répète pas sous un autre.",
        "",
        "PROCÉDURES À APPLIQUER, DANS CET ORDRE :",
        *[f"- {key} : {desc}" for key, desc in TYPES_PROC.items()],
        "",
        *_CITATION_RULE,
        "",
        "RÉCIT DU PORTEUR :",
        recit,
        "",
        "Réponds STRICTEMENT en JSON, avec les 6 types dans l'ordre :",
        '{ "analyse": [ { "type": "<type>", "trouve": <true|false>, "contradictions": [',
        '  { "passage_a": "<citation>", "passage_b": "<citation>",',
        '    "explication": "<1 phrase>", "gravite": "haute|moyenne|basse" } ] } ] }',
    ]
    return "\n".join(lines)


# --- v2cfr : baseline GELÉE, clés françaises ------------------------------------
# Reproduction fidèle de la v2c telle qu'elle a mesuré 9/10 constats et 0 faux positif, AVANT
# l'anglicisation des clés (IDX-INCOH-01). Elle sert d'étalon : comparée à la v2c actuelle avec
# le MÊME post-traitement (ancrage + déduplication), elle isole l'effet du seul renommage.
# Ne jamais la « corriger » : sa valeur tient à ce qu'elle ne bouge plus.
V2CFR_GROUPS: dict[str, tuple[str, ...]] = {
    "quantitatif": ("arithmetique", "capacite", "marche"),
    "textuel": ("temporelle", "interne", "reglementaire"),
}


def build_context_prompt_fr(*, recit: str) -> str:
    return "\n".join(
        [
            "FORMAT=contexte.",
            "Rédige TOUTE ta réponse en français.",
            "Déduis du récit ci-dessous le pays et la devise dans lesquels le projet opère.",
            "Appuie-toi sur les indices explicites : villes, monnaies citées, institutions,",
            "dispositifs sociaux, mentions géographiques, vocabulaire administratif.",
            "Si aucun indice fiable n'existe, réponds pays et devise à null — n'invente pas.",
            "",
            "Donne aussi un ORDRE DE GRANDEUR du revenu mensuel médian d'un ménage modeste",
            "dans ce pays, exprimé dans la devise locale. C'est ce repère qui permettra ensuite",
            "de juger si un prix est compatible avec la cible annoncée.",
            "",
            "RÉCIT :",
            recit,
            "",
            "Réponds STRICTEMENT en JSON :",
            '{ "pays": "<pays ou null>", "devise": "<code ISO ou null>",',
            '  "indices": "<les indices qui ont permis de trancher, 1 phrase>",',
            '  "revenu_menage_modeste": "<ordre de grandeur mensuel, devise locale, ou null>" }',
        ]
    )


def _context_block_fr(context: dict | None) -> list[str]:
    if not context or not context.get("pays"):
        return [
            "CONTEXTE : pays indéterminé. Ne juge PAS le pouvoir d'achat ni les obligations",
            "réglementaires — tu n'as pas la juridiction. Concentre-toi sur les incohérences",
            "internes au récit, qui ne dépendent d'aucun pays.",
            "",
        ]
    revenu = context.get("revenu_menage_modeste") or "non déterminé"
    return [
        f"CONTEXTE DÉTECTÉ : pays = {context['pays']} · devise = {context.get('devise') or '?'}.",
        f"Repère de pouvoir d'achat : revenu mensuel d'un ménage modeste ≈ {revenu}.",
        "Utilise CE repère pour juger si un prix est compatible avec la cible annoncée,",
        "et CETTE juridiction pour juger les obligations réglementaires. Un même montant",
        "n'a pas la même portée selon le pays : raisonne toujours en ordre de grandeur local.",
        "",
    ]


def build_v2cfr(*, recit: str, category: str, archetype: str, group: str, context: dict | None = None) -> str:
    keys = V2CFR_GROUPS[group]
    lines = [
        "FORMAT=contradictions_exhaustif.",
        *_header(category, archetype),
        "",
        *_context_block_fr(context),
        f"Tu examines UNIQUEMENT le groupe « {group} » : {', '.join(keys)}.",
        "Applique CHAQUE procédure ci-dessous, l'une APRÈS l'autre, et prononce-toi sur CHACUNE.",
        "Produis une entrée par type, même quand tu ne trouves rien.",
        "",
        *_ANTI_FP,
        "Une FAIBLESSE, un sous-dimensionnement, un risque ou une fragilité du projet n'est PAS",
        "une contradiction. Ne signale que des INCOMPATIBILITÉS FACTUELLES entre deux affirmations.",
        "",
        "RÈGLE SYMÉTRIQUE — les deux moitiés comptent autant :",
        "- Si ta vérification CONFIRME la cohérence → `trouve: false`, liste vide. C'est un succès,",
        "  et tu n'exposes JAMAIS dans `contradictions` un calcul qui tombe juste.",
        "- Si ta vérification RÉVÈLE un écart → SIGNALE-LE sans hésiter, c'est exactement ce qu'on",
        "  cherche. Un écart de calcul avéré est la trouvaille la plus précieuse de toutes.",
        "",
        "ANTI-DOUBLON : une même contradiction n'apparaît qu'UNE fois, sous le type le plus spécifique.",
        "",
        "PROCÉDURES À APPLIQUER, DANS CET ORDRE :",
        *[f"- {key} : {TYPES_PROC[key]}" for key in keys],
        "",
        *_CITATION_RULE,
        "",
        "RÉCIT DU PORTEUR :",
        recit,
        "",
        f"Réponds STRICTEMENT en JSON, avec les {len(keys)} types du groupe, dans l'ordre :",
        '{ "analyse": [ { "type": "<type>", "trouve": <true|false>, "contradictions": [',
        '  { "passage_a": "<citation>", "passage_b": "<citation>",',
        '    "explication": "<1 phrase>", "gravite": "haute|moyenne|basse" } ] } ] }',
    ]
    return "\n".join(lines)


def build_v2b(*, recit: str, category: str, archetype: str, type_key: str) -> str:
    # Passe FOCALISÉE : un seul type recherché. Le risque propre à cette variante est le
    # faux positif (un chercheur spécialisé veut justifier sa présence) — d'où l'autorisation
    # explicite et répétée de ne rien trouver.
    lines = [
        "FORMAT=contradictions.",
        *_header(category, archetype),
        "",
        f"Ta SEULE tâche : chercher les contradictions de type « {type_key} », et RIEN d'autre.",
        f"Définition : {TYPES[type_key]}",
        "Ignore complètement les autres types de problème, même si tu en repères.",
        "",
        *_ANTI_FP,
        "",
        f"Il est parfaitement NORMAL et ATTENDU qu'aucune contradiction de type « {type_key} »",
        "ne soit présente dans ce récit. Dans ce cas, renvoie une liste VIDE sans hésiter.",
        "Ne force JAMAIS une trouvaille pour justifier ta réponse : une liste vide est un",
        "excellent résultat. Mieux vaut ne rien signaler que signaler à tort.",
        "",
        *_CITATION_RULE,
        "",
        "RÉCIT DU PORTEUR :",
        recit,
        "",
        "Réponds STRICTEMENT en JSON :",
        '{ "contradictions": [ { "passage_a": "<citation>", "passage_b": "<citation>",',
        '  "explication": "<1 phrase>", "gravite": "haute|moyenne|basse" } ] }',
    ]
    return "\n".join(lines)


def _apply_temperature(provider: Any, temperature: float) -> None:
    # Introspection assumée, réservée au banc : on force la température sur le provider
    # et sur ceux qu'il enveloppe (FallbackProvider), sans toucher à la config produit.
    if hasattr(provider, "_temperature"):
        provider._temperature = temperature
    for wrapped in getattr(provider, "_providers", []) or []:
        _apply_temperature(wrapped, temperature)


class Counter:
    def __init__(self) -> None:
        self.calls = 0


async def _ask(provider: Any, prompt: str, sem: asyncio.Semaphore, counter: Counter) -> dict | None:
    async with sem:
        counter.calls += 1
        try:
            return await provider.analyze_json(prompt, max_tokens=1800)
        except Exception:
            return None


def _finalize(raws: list[dict], *, use_dedup: bool) -> list[Finding]:
    """Frontière du banc : dicts bruts du modèle → domaine typé, puis déduplication."""
    findings = parse_findings(raws)
    return deduplicate(findings) if use_dedup else findings


def _flatten_analyse(out: dict) -> list[dict]:
    """Aplatit le schéma `analyse` (une entrée par type) en liste plate de contradictions."""
    found: list[dict] = []
    for entry in out.get("analyse") or []:
        if not isinstance(entry, dict):
            continue
        type_key = entry.get("type", "?")
        for item in entry.get("contradictions") or []:
            if isinstance(item, dict):
                found.append({**item, "type": type_key})
    return found


async def _detect(
    provider: Any,
    case: dict,
    variant: str,
    sem: asyncio.Semaphore,
    counter: Counter,
    *,
    use_context: bool = True,
    use_dedup: bool = True,
) -> tuple[list[Finding], str | None, dict | None]:
    common = {
        "recit": case["recit"],
        "category": case.get("category", "?"),
        "archetype": case.get("archetype", "?"),
    }

    if variant in {"v2c", "v2cfr"}:
        # v2c   = PRODUCTION : prompts promus dans `app/llm/prompt.py` (le banc mesure le réel).
        # v2cfr = baseline gelée en clés françaises, MÊME post-traitement → isole le renommage.
        french = variant == "v2cfr"
        context = None
        if use_context:
            context_prompt = (
                build_context_prompt_fr(recit=case["recit"])
                if french
                else build_context_prompt(narrative=case["recit"])
            )
            context = await _ask(provider, context_prompt, sem, counter)
        if french:
            prompts = [
                build_v2cfr(**common, group=group, context=context) for group in V2CFR_GROUPS
            ]
        else:
            prompts = [
                build_inconsistency_prompt(
                    narrative=case["recit"],
                    group=group,
                    category=common["category"],
                    archetype=common["archetype"],
                    context=context,
                )
                for group in INCONSISTENCY_GROUPS
            ]
        outs = await asyncio.gather(*(_ask(provider, p, sem, counter) for p in prompts))
        findings: list[Finding] = []
        failures = 0
        for out in outs:
            if out is None:
                failures += 1
                continue
            findings.extend(parse_analysis(out))
        if failures == len(prompts):
            return [], "toutes les passes ont échoué", context
        notes = [f"{failures} passe(s) en échec"] if failures else []
        # Garde-fou déterministe : un constat dont les citations ne se retrouvent pas dans le
        # récit n'est pas vérifiable par le client — il ne doit jamais atteindre le rapport.
        findings, dropped = keep_grounded(findings, case["recit"])
        if dropped:
            notes.append(f"{len(dropped)} constat(s) écarté(s) : citations introuvables")
        return (
            (deduplicate(findings) if use_dedup else findings),
            " · ".join(notes) or None,
            context,
        )

    if variant == "v2b":
        prompts = {key: build_v2b(**common, type_key=key) for key in TYPES}
        outs = await asyncio.gather(*(_ask(provider, p, sem, counter) for p in prompts.values()))
        found: list[dict] = []
        failures = 0
        for type_key, out in zip(prompts.keys(), outs, strict=True):
            if out is None:
                failures += 1
                continue
            items = out.get("contradictions")
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    found.append({**item, "type": type_key})
        if failures == len(prompts):
            return [], "toutes les passes ont échoué", None
        note = f"{failures} passe(s) en échec" if failures else None
        return _finalize(found, use_dedup=use_dedup), note, None

    builder = {"v1": build_v1, "v2a": build_v2a, "v2abis": build_v2abis}[variant]
    out = await _ask(provider, builder(**common), sem, counter)
    if out is None:
        return [], "appel en échec", None

    if variant == "v1":
        items = out.get("contradictions")
        if not isinstance(items, list):
            return [], "sortie sans liste 'contradictions'", None
        raws = [item for item in items if isinstance(item, dict)]
        return _finalize(raws, use_dedup=use_dedup), None, None

    if not isinstance(out.get("analyse"), list):
        return [], "sortie sans liste 'analyse'", None
    return _finalize(_flatten_analyse(out), use_dedup=use_dedup), None, None


def _print_case(case: dict, found: list[Finding], error: str | None, context: dict | None = None) -> None:
    corrige = case.get("corrige", [])
    is_control = bool(case.get("controle_propre"))

    label = f"  {case['id']}"
    if is_control:
        label += "   [CONTRÔLE PROPRE]"
    print()
    print(label)
    print("  " + "-" * 74)
    attendu = ", ".join(f"{c['ref']}:{c['type']}" for c in corrige) or "aucune (toute détection = faux positif)"
    print(f"  attendu  : {attendu}")
    if context is not None:
        # La baseline gelée renvoie des clés françaises : on lit les deux jeux.
        pays = context.get("country") or context.get("pays") or "indéterminé"
        devise = context.get("currency") or context.get("devise") or "?"
        revenu = context.get("modest_household_income") or context.get("revenu_menage_modeste") or "?"
        cible = case.get("pays_attendu")
        ok = "" if cible is None else ("  [OK]" if cible.lower() in str(pays).lower() else f"  [ATTENDU {cible}]")
        print(f"  contexte : {pays} · {devise} · ménage modeste ≈ {revenu}{ok}")

    if error and not found:
        print(f"  détecté  : ÉCHEC — {error}")
        return
    if error:
        print(f"  (avertissement : {error})")
    if not found:
        print("  détecté  : rien")
        return

    print(f"  détecté  : {len(found)}")
    for index, finding in enumerate(found, start=1):
        merged = ""
        if finding.merged_types:
            merged = "  (doublons fusionnés : " + ", ".join(t.value for t in finding.merged_types) + ")"
        print(f"    {index}. [{finding.type.value}] gravité={finding.severity.value}{merged}")
        print(f"       A : « {finding.quote_a[:120]} »")
        print(f"       B : « {finding.quote_b[:120]} »")
        print(f"       -> {finding.explanation[:170]}")


async def run(
    corpus_path: Path,
    *,
    variants: list[str],
    temperature: float | None,
    only: str | None,
    raw: bool,
    runs: int,
    use_context: bool = True,
    use_dedup: bool = True,
) -> int:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if only:
        cases = [c for c in cases if c["id"] == only]
    if not cases:
        raise SystemExit("Aucun cas à traiter.")

    settings = get_settings()
    provider = get_llm(settings)
    model = getattr(provider, "model", settings.llm_provider)
    effective_temp = temperature if temperature is not None else settings.llm_temperature
    if temperature is not None:
        _apply_temperature(provider, temperature)

    total_planted = sum(len(c.get("corrige", [])) for c in cases)
    # La version de prompt figure dans l'en-tête : une mesure sans elle n'est pas rejouable.
    print(
        f"Banc contradictions · modèle {model} · température {effective_temp}"
        f" · prompt {INCONSISTENCY_PROMPT_VERSION}"
    )
    print(f"Corpus : {corpus_path.name} · {len(cases)} cas · {total_planted} contradictions plantées")

    sem = asyncio.Semaphore(4)  # ménage les quotas du provider
    summary: list[dict] = []

    for variant in variants:
        counter = Counter()
        print()
        print("=" * 78)
        print(f"VARIANTE {variant} · {runs} run(s)")
        print("=" * 78)

        per_run: list[tuple[int, int]] = []
        for run_index in range(1, runs + 1):
            results = await asyncio.gather(
                *(
                    _detect(provider, c, variant, sem, counter, use_context=use_context, use_dedup=use_dedup)
                    for c in cases
                )
            )
            detected = 0
            false_pos = 0

            if run_index == 1:
                for case, (found, error, context) in zip(cases, results, strict=True):
                    _print_case(case, found, error, context)
                    if raw and found:
                        print("    BRUT : " + json.dumps([asdict(f) for f in found], ensure_ascii=False, default=str))
            else:
                # Runs suivants : forme compacte, on ne veut que la STABILITÉ des trouvailles.
                print(f"\n  -- run {run_index} (compact) --")
                for case, (found, _err, _ctx) in zip(cases, results, strict=True):
                    types = ", ".join(sorted({f.type.value for f in found})) or "rien"
                    flag = "  <-- FAUX POSITIF" if case.get("controle_propre") and found else ""
                    print(f"    {case['id']:<24} {types}{flag}")

            for case, (found, _err, _ctx) in zip(cases, results, strict=True):
                detected += len(found)
                if case.get("controle_propre"):
                    false_pos += len(found)
            per_run.append((detected, false_pos))

        avg_det = sum(d for d, _ in per_run) / len(per_run)
        avg_fp = sum(f for _, f in per_run) / len(per_run)
        summary.append(
            {
                "variant": variant,
                "detected": round(avg_det, 1),
                "false_pos": round(avg_fp, 1),
                "calls": counter.calls,
                "per_run": per_run,
            }
        )

    print()
    print("=" * 78)
    print("COMPARAISON")
    print("=" * 78)
    print(f"  {'variante':<10}{'détect. moy':>13}{'faux pos. moy':>15}{'appels':>9}   par run")
    for row in summary:
        detail = " · ".join(f"{d}d/{f}fp" for d, f in row["per_run"])
        print(
            f"  {row['variant']:<10}{row['detected']:>13}{row['false_pos']:>15}"
            f"{row['calls']:>9}   {detail}"
        )
    print()
    print(f"  Rappel : {total_planted} contradictions plantées au total.")
    print("  L'appariement détection <-> corrigé reste un JUGEMENT HUMAIN : le nombre de")
    print("  détections n'est PAS un score. Relis les blocs ci-dessus pour trancher.")
    print("  Un faux positif sur le contrôle propre disqualifie une variante, quel que soit son rappel.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # sorties accentuées sous Windows
    parser = argparse.ArgumentParser(description="Banc d'essai du détecteur de contradictions.")
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--variant", default="all", help=f"'all', ou liste séparée par virgules : {','.join(VARIANTS)}")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--case", dest="only", default=None)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--runs", type=int, default=1, help="répétitions par variante (mesure bruitée)")
    parser.add_argument(
        "--no-context", action="store_true", help="désactive la passe pays/devise (v2c seulement)"
    )
    parser.add_argument("--no-dedup", action="store_true", help="désactive la déduplication des constats")
    args = parser.parse_args()
    variants = list(VARIANTS) if args.variant == "all" else args.variant.split(",")
    return asyncio.run(
        run(
            args.corpus,
            variants=variants,
            temperature=args.temperature,
            only=args.only,
            raw=args.raw,
            runs=args.runs,
            use_context=not args.no_context,
            use_dedup=not args.no_dedup,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
