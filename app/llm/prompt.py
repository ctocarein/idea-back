"""Construction du prompt de scoring — DÉTERMINISTE, à partir de la grille ancrée.

Le prompt n'est jamais bricolé dans le métier : il est assemblé ici depuis la grille
(axes + ANCRES + questions guidantes) et le contexte du projet. C'est ce qui garantit
que l'IA note CHAQUE axe contre sa rubrique (et non « au feeling »).

`prompt_version` est figé ici et stocké sur chaque `ScoreRun` → reproductibilité.
"""

from __future__ import annotations

import json

PROMPT_VERSION = "scoring-v3"  # v3 : scoring honnête (« à compléter » au lieu d'inventer)
REPORT_PROMPT_VERSION = "report-v1"
COACH_PROMPT_VERSION = "coach-v1"
PITCH_PROMPT_VERSION = "pitch-v2"  # v2 : cohérence dit/montré
VERDICT_PROMPT_VERSION = "verdict-v2"  # v2 : le verdict voit le deck + juge la cohérence
EXTRACTION_PROMPT_VERSION = "extract-v1"  # récit libre → 12 dimensions captées / manquantes
MODULE_PROMPT_VERSION = "module-v1"       # modules Academy : opener + turn + form + fiches


def build_extraction_prompt(
    *, idea: str, axes: list[dict], project_name: str | None = None
) -> str:
    # « Raconte, on structure » : depuis le RÉCIT LIBRE, on repère pour chaque dimension si
    # l'info est déjà là (preuve) ou s'il faut la demander (question). On n'INVENTE jamais.
    lines = [
        "FORMAT=extraction.",
        "Tu es un analyste de projets. À partir du RÉCIT LIBRE du porteur, traite CHAQUE dimension :",
        "- si le récit donne assez d'info → captured=true + 'evidence' (courte preuve tirée du récit) ;",
        "- sinon → captured=false + 'question' (UNE question courte et simple pour combler le manque).",
        "N'INVENTE rien : si ce n'est pas dans le récit, c'est un manque (captured=false).",
        "",
        f"NOM du projet fourni : {project_name or '(aucun — déduis-le du récit s’il est nommé, sinon null)'}",
        "",
        "DIMENSIONS À COUVRIR :",
    ]
    for a in axes:
        pistes = " / ".join(a.get("guiding_questions", []))
        lines.append(f"- {a['key']} ({a['label']}) — {a['central_question']} Pistes : {pistes}")
    lines += [
        "",
        "RÉCIT DU PORTEUR :",
        idea,
        "",
        "Réponds STRICTEMENT en JSON : { \"project_name\": \"<nom ou null>\", \"dimensions\": {",
        '  "<key d1..d12>": { "captured": <true|false>, "evidence": "<preuve si captured, sinon \\"\\">", '
        '"question": "<question courte si manquant, sinon \\"\\">" } } }',
    ]
    return "\n".join(lines)


def build_verdict_prompt(*, persona: dict, transcript: str, slide_text: str, conviction: int) -> str:
    # Délibération : l'agent donne SON verdict, avec SES mots et son style (Règle d'or n°5).
    # Il juge AUSSI la cohérence entre ce qui est dit (pitch) et ce qui est montré (deck).
    return "\n".join(
        [
            "FORMAT=verdict.",
            f"Tu es {persona['name']}, {persona.get('role', '')} ({persona.get('personality', '')}).",
            f"Ton obsession : {persona.get('obsession', '')}. Ta conviction (−2 à +2) : {conviction}.",
            "Après ce pitch, donne TON verdict en 1-2 phrases, avec TES mots et ton style — franc et utile.",
            "Juge AUSSI la COHÉRENCE entre ce qui est DIT et ce qui est MONTRÉ : relève tout écart "
            "(un chiffre annoncé absent du deck, une slide qui contredit le pitch, une promesse non étayée).",
            f"Ce qui est DIT (transcript) : {transcript[:2000]}",
            f"Ce qui est MONTRÉ (slides du deck) : {(slide_text or '(aucun deck partagé)')[:1500]}",
            'Réponds STRICTEMENT en JSON : { "verdict": "<1-2 phrases>", "vote": "go|conditional|nogo" }',
        ]
    )


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
        "PITCH (transcript du porteur — ce qui est DIT) :",
        transcript or "(vide)",
        "",
        "SLIDES (le deck — ce qui est MONTRÉ) :",
        slide_text or "(aucune)",
        "",
        "COHÉRENCE : si le PITCH et les SLIDES se contredisent (chiffres divergents, promesse non",
        "étayée par le deck, slide hors-sujet), PÉNALISE l'axe concerné et dis-le dans sa justification.",
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
        "HONNÊTETÉ : si une dimension n'est PAS étayée par le projet (aucune info), ne l'invente",
        "PAS — note-la dans le bas de l'échelle ET écris « à compléter » dans sa justification.",
        "Un trou honnête vaut mieux qu'un score gonflé.",
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


def build_module_opener_prompt(
    *,
    dimension: str,
    label: str,
    context_questions: list[str],
    project_title: str | None = None,
    sector: str | None = None,
    axis_score: int | None = None,
) -> str:
    # Premier message du coach au démarrage d'un module Academy.
    # Il pose les questions de contexte de manière directe et bienveillante.
    projet = f"« {project_title} »" if project_title else "ton projet"
    secteur = f" dans le secteur {sector}" if sector else ""
    questions = "\n".join(f"- {q}" for q in context_questions)
    # Personnalisation : le coach part du score réel du diagnostic sur cet axe.
    score_line = (
        f"CONTEXTE — au diagnostic Radar, le porteur a obtenu {axis_score}/10 sur cet axe : "
        "c'est un des points à renforcer. Reconnais-le en une demi-phrase, sans le culpabiliser, "
        "et cadre l'échange comme une manière concrète de faire monter ce score."
        if axis_score is not None
        else ""
    )
    return "\n".join(
        [
            "FORMAT=module_coach.",
            f"Tu es un coach entrepreneurial travaillant avec le porteur de {projet}{secteur}.",
            f"Tu commences le module « {dimension.upper()} — {label} ».",
            *([score_line] if score_line else []),
            "Présente-toi brièvement (1 phrase) puis pose les questions de contexte ci-dessous",
            "en un seul message structuré. Sois direct et bienveillant.",
            "N'utilise JAMAIS de placeholder entre crochets ([Prénom], [Ton nom]…) :",
            "tu ne connais pas le prénom du porteur, alors tutoie-le sans le nommer.",
            "Ne rédige jamais à la place du porteur — tu poses des questions.",
            "",
            "QUESTIONS À POSER :",
            questions,
            "",
            "RÈGLE PÉDAGOGIQUE — pour CHAQUE question, ajoute un exemple concret",
            "en *italique*, pour montrer le type de réponse attendu.",
            "N'utilise PAS de parenthèses autour de l'exemple : écris-le directement",
            "en italique, sur sa propre ligne, en commençant par « ex : ».",
            "Mets des exemples CHIFFRÉS et plausibles — montants, %, durées, volumes —",
            "adaptés au secteur du projet, jamais des placeholders vagues.",
            "Exemple de formulation :",
            "**Comment génères-tu des revenus ?**",
            "*ex : abonnement SaaS à 29 €/mois, commission de 15 % par transaction, "
            "licence annuelle à 5 000 €*",
            "Formate en Markdown : questions en **gras**, exemples en *italique*,",
            "une question par puce. L'objectif : que le porteur comprenne instantanément",
            "ce qu'on lui demande grâce à l'exemple.",
            "",
            "Réponds en prose Markdown (pas de JSON) — le porteur va lire et répondre.",
        ]
    )


def build_module_turn_prompt(
    *,
    dimension: str,
    label: str,
    history: list[dict],
    message: str,
) -> str:
    # Tour de conversation dans un module (phase context).
    hist = "\n".join(
        f"{'Porteur' if t['role'] == 'porteur' else 'Coach'}: {t['text']}"
        for t in history[-6:]
    )
    return "\n".join(
        [
            "FORMAT=module_coach.",
            f"Tu coaches le porteur sur « {dimension.upper()} — {label} ».",
            "Ton rôle : comprendre son projet sur cet aspect, poser des questions précises,",
            "expliquer des concepts si besoin. Tu NE rédiges JAMAIS à sa place.",
            "Quand tu poses une nouvelle question, illustre-la d'un exemple concret et",
            "CHIFFRÉ en *italique* (montant, %, durée, volume), sur sa propre ligne,",
            "commençant par « ex : », SANS parenthèses autour.",
            "Formate en Markdown : points clés en **gras**, exemples en *italique*,",
            "listes à puces quand tu énumères.",
            "Réponds en prose Markdown (3-5 phrases max).",
            "",
            "SIGNAL DE FIN — RÈGLE STRICTE :",
            "Ne cherche JAMAIS la perfection. Dès que le porteur a donné une réponse",
            "de fond sur les 2-3 questions principales (même perfectibles), tu DOIS",
            "déclencher le signal. En pratique : au plus tard après sa 2e ou 3e réponse",
            "substantielle, considère que l'essentiel est couvert.",
            "Quand c'est le cas, tu DOIS : (1) le féliciter en une phrase,",
            "(2) lui dire qu'il peut passer à la synthèse de ses réponses (sans",
            "poser de nouvelle question), et (3) terminer EXACTEMENT par [[PRET]].",
            "Tant que l'essentiel reste couvert, remets [[PRET]] à chaque message suivant.",
            "Tu peux suggérer UNE piste d'amélioration optionnelle, mais déclenche",
            "quand même le signal — c'est le porteur qui décide de continuer ou non.",
            "",
            f"Historique récent :\n{hist or '(début de session)'}",
            f"Message du porteur : {message}",
        ]
    )


def build_module_form_prefill_prompt(
    *,
    dimension: str,
    label: str,
    form_sections: list[dict],
    history: list[dict],
    project_title: str | None = None,
    sector: str | None = None,
) -> str:
    # Pré-remplit le formulaire structuré à partir de la conversation de contexte.
    # Ne JAMAIS inventer — seulement ce qui est dans la conversation.
    projet = f"« {project_title} »" if project_title else "ce projet"
    secteur = f" ({sector})" if sector else ""
    sections_json = json.dumps(
        [{"key": s["key"], "label": s["label"]} for s in form_sections],
        ensure_ascii=False,
    )
    hist = "\n".join(
        f"{'Porteur' if t['role'] == 'porteur' else 'Coach'}: {t['text']}"
        for t in history
    )
    return "\n".join(
        [
            "FORMAT=form_prefill.",
            f"À partir de la conversation sur le module « {dimension.upper()} — {label} »",
            f"pour le projet {projet}{secteur}, pré-remplis les sections du formulaire.",
            "RÈGLE ABSOLUE : ne JAMAIS inventer une info absente de la conversation.",
            "Si une section n'est pas couverte par la conversation → chaîne vide (\"\").",
            "",
            f"SECTIONS DU FORMULAIRE : {sections_json}",
            "",
            "CONVERSATION :",
            hist or "(aucun historique)",
            "",
            "Réponds STRICTEMENT en JSON : { \"<section_key>\": \"<valeur ou vide>\", ... }",
        ]
    )


def build_module_fiches_prompt(
    *,
    dimension: str,
    label: str,
    form_data: dict,
    project_title: str | None = None,
    sector: str | None = None,
) -> str:
    # Génère des fiches de besoin structurées à partir du formulaire rempli.
    projet = f"« {project_title} »" if project_title else "ce projet"
    secteur = f" ({sector})" if sector else ""
    return "\n".join(
        [
            "FORMAT=fiches.",
            f"À partir du formulaire complété sur « {dimension.upper()} — {label} »",
            f"pour le projet {projet}{secteur}, identifie les besoins concrets",
            "qui permettraient de consolider ce projet.",
            "",
            "TYPES DE BESOIN POSSIBLES :",
            "- dev : développeur (web, mobile, IoT, logiciel)",
            "- expert : expert sectoriel (financier, juridique, RH, technique, sectoriel)",
            "- cofondateur : cofondateur avec un profil complémentaire",
            "- partenaire : partenaire commercial, de distribution ou technologique",
            "- outil : outil, logiciel ou ressource technologique",
            "- financement : recherche de financement (investisseur, subvention, prêt)",
            "- formation : formation ou accompagnement spécialisé",
            "- autre : autre type de besoin",
            "",
            "Pour CHAQUE besoin identifié, génère une fiche structurée.",
            "Génère seulement les besoins réellement identifiés (1-4 fiches max).",
            "",
            f"FORMULAIRE :\n{json.dumps(form_data, ensure_ascii=False, indent=2)}",
            "",
            "Réponds STRICTEMENT en JSON :",
            '{ "fiches": [',
            '  {',
            '    "need_type": "<type>",',
            '    "title": "<titre court et concret>",',
            '    "description": "<description 2-3 phrases>",',
            '    "details": {',
            '      "profile": "<profil recherché>",',
            '      "skills": ["<compétence1>", "..."],',
            '      "budget": "<estimation budgétaire ou vide>",',
            '      "timeline": "<délai souhaité>",',
            '      "deliverables": ["<livrable1>", "..."],',
            '      "priority": "high|medium|low",',
            '      "engagement_type": "<freelance|CDI|association|prestation|autre>"',
            '    }',
            '  }',
            '] }',
        ]
    )


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
