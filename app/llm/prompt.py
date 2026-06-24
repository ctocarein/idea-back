"""Construction du prompt de scoring — DÉTERMINISTE, à partir de la grille ancrée.

Le prompt n'est jamais bricolé dans le métier : il est assemblé ici depuis la grille
(axes + ANCRES + questions guidantes) et le contexte du projet. C'est ce qui garantit
que l'IA note CHAQUE axe contre sa rubrique (et non « au feeling »).

`prompt_version` est figé ici et stocké sur chaque `ScoreRun` → reproductibilité.
"""

from __future__ import annotations

import json

PROMPT_VERSION = "scoring-v2"
REPORT_PROMPT_VERSION = "report-v1"
COACH_PROMPT_VERSION = "coach-v1"
PITCH_PROMPT_VERSION = "pitch-v1"


def build_pitch_prompt(
    *,
    rubric_axes: list[dict],
    committee_label: str,
    transcript: str,
    slide_text: str,
) -> str:
    # Le comité note CHAQUE axe Fond contre ses ancres, à partir du transcript + des slides.
    # Marqueur FORMAT=axes : même contrat de sortie que le scoring Radar (axes + justifications).
    lines = [
        "FORMAT=axes.",
        f"Tu es un comité de pitch ({committee_label}), rigoureux et bienveillant.",
        "Note CHAQUE axe de 0 à 10 EN T'APPUYANT sur ses ancres. Juge le pitch, pas l'enthousiasme.",
        "",
        "AXES, QUESTION & ANCRES :",
    ]
    for axis in rubric_axes:
        bands = " | ".join(f"{b['min']}-{b['max']}: {b['label']}" for b in axis.get("anchors", []))
        cq = axis.get("central_question", "")
        lines.append(f"- {axis['key']} ({axis['label']}) — {cq} Ancres : {bands}")
    lines += [
        "",
        "PITCH (transcript du porteur) :",
        transcript or "(vide)",
        "",
        "SLIDES :",
        slide_text or "(aucune)",
        "",
        'Réponds STRICTEMENT en JSON : { "axes": { "<key>": <0-10> }, '
        '"justifications": { "<key>": "<raison courte>" } }',
    ]
    return "\n".join(lines)


def build_coach_prompt(*, section: str, draft: str, message: str) -> str:
    # « Construire guidé » : garde-fou central — le porteur RESTE l'auteur. Le coach
    # explique, questionne, structure, donne des exemples — il NE rédige JAMAIS la section
    # à sa place (frontière gratuit/payant : « apprendre à faire », pas « faire avec toi »).
    return "\n".join(
        [
            "FORMAT=coach.",
            "Tu es un coach entrepreneurial bienveillant et exigeant. Le porteur travaille la",
            f"section « {section} » de son projet. **Le porteur reste l'auteur** : tu EXPLIQUES,",
            "tu QUESTIONNES, tu donnes des repères et des exemples — tu ne rédiges JAMAIS la",
            "section à sa place, tu ne produis pas le livrable. Pose des questions qui le font avancer.",
            "",
            f"Son brouillon actuel : {draft or '(vide)'}",
            f"Son message : {message}",
            "",
            "Réponds en 3-5 phrases : une explication courte + 1-2 questions précises pour qu'il progresse.",
        ]
    )


def build_scoring_prompt(
    grid_axes: list[dict],
    *,
    category: str,
    archetype: str,
    description: str | None,
    answers: dict[str, str] | None,
    perspective: int = 0,
) -> str:
    # `perspective` varie d'une passe à l'autre (ensemble) sans changer la rubrique :
    # on demande à l'IA un angle d'analyse légèrement différent pour révéler l'incertitude.
    lines: list[str] = [
        "FORMAT=axes.",
        "Tu es un évaluateur de projets entrepreneuriaux rigoureux et bienveillant.",
        f"Catégorie : {category} · Archétype : {archetype}.",
        "Note CHAQUE dimension de 0 à 10 EN T'APPUYANT sur ses ancres (paliers ci-dessous).",
        "Ne te fie pas à l'enthousiasme : juge les faits fournis.",
        "",
        "DIMENSIONS, QUESTION CENTRALE & ANCRES :",
    ]
    for axis in grid_axes:
        bands = " | ".join(f"{b['min']}-{b['max']}: {b['label']}" for b in axis.get("anchors", []))
        cq = axis.get("central_question", "")
        qs = " ".join(axis.get("guiding_questions", []))
        lines.append(f"- {axis['key']} ({axis['label']}) — {cq} Ancres : {bands}. {qs}")

    lines += [
        "",
        "PROJET :",
        f"Description : {description or '(via document uploadé)'}",
        f"Réponses : {json.dumps(answers or {}, ensure_ascii=False)}",
        "",
        f"Angle d'analyse #{perspective}.",
        "Réponds STRICTEMENT en JSON :",
        '{ "axes": { "<dimKey d1..d12>": <0-10>, ... }, "justifications": { "<dimKey>": "<courte raison>", ... } }',
    ]
    return "\n".join(lines)


def build_report_prompt(
    *,
    category: str,
    archetype: str,
    description: str | None,
    answers: dict[str, str] | None,
    scores: dict[str, int] | None = None,
) -> str:
    # Couche STRUCTURÉE du rapport de pré-diagnostic (au-delà des notes /10) : description,
    # verdict, matrice de risques, concurrents, avancement, recos priorisées, next steps.
    # Best-effort, affinée ensuite par l'analyste. Ton bienveillant et factuel.
    return "\n".join(
        [
            "FORMAT=report.",
            "Tu es un analyste qui rédige un pré-diagnostic synthétique et actionnable.",
            f"Catégorie : {category} · Archétype : {archetype}.",
            f"Scores Radar (0-10) déjà calculés : {json.dumps(scores or {}, ensure_ascii=False)}",
            "",
            "PROJET :",
            f"Description : {description or '(via document uploadé)'}",
            f"Réponses : {json.dumps(answers or {}, ensure_ascii=False)}",
            "",
            "Réponds STRICTEMENT en JSON avec CE schéma (sections vides tolérées) :",
            "{",
            '  "summary": "<2-3 phrases>",',
            '  "maturity": "<Idée|Prototype|Traction|Passage à l\'échelle>", "maturity_rationale": "<raison>",',
            '  "description": { "problem": "...", "solution": "...", "target_client": "...", "business_model": "..." },',
            '  "benchmark": ["..."],',
            '  "strengths": [ { "text": "...", "dimension": "d1..d12" } ],',
            '  "risks": [ { "text": "...", "probability": "high|medium|low", "severity": "critical|high|medium|low" } ],',
            '  "competition": [ { "name": "...", "type": "direct|indirect", "description": "...", "threat": "high|medium|low" } ],',
            '  "progress": { "stage": "...", "team_size": 0, "customers": 0, "revenue": 0, "funding": 0 },',
            '  "verdict": { "status": "go|conditional|nogo", "label": "...", "analysis": "<6-8 lignes>" },',
            '  "recommendations": [ { "priority": 1, "title": "...", "description": "..." } ],',
            '  "next_steps": [ { "deadline": "1 semaine", "action": "..." } ]',
            "}",
        ]
    )
