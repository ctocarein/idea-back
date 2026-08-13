"""Construction du prompt de scoring — DÉTERMINISTE, à partir de la grille ancrée.

Le prompt n'est jamais bricolé dans le métier : il est assemblé ici depuis la grille
(axes + ANCRES + questions guidantes) et le contexte du projet. C'est ce qui garantit
que l'IA note CHAQUE axe contre sa rubrique (et non « au feeling »).

`prompt_version` est figé ici et stocké sur chaque `ScoreRun` → reproductibilité.
"""

from __future__ import annotations

import json

from app.inconsistencies.dedup import InconsistencyType

PROMPT_VERSION = "scoring-v3"  # v3 : scoring honnête (« à compléter » au lieu d'inventer)
REPORT_PROMPT_VERSION = "report-v1"
COACH_PROMPT_VERSION = "coach-v1"
PITCH_PROMPT_VERSION = "pitch-v2"  # v2 : cohérence dit/montré
VERDICT_PROMPT_VERSION = "verdict-v2"  # v2 : le verdict voit le deck + juge la cohérence
EXTRACTION_PROMPT_VERSION = "extract-v2"  # v2 : chiffres devinés marqués « ≈ … (à confirmer) »
MODULE_PROMPT_VERSION = "module-v1"  # modules Academy : opener + turn + form + fiches
CONTEXT_PROMPT_VERSION = "context-v1"  # pays + devise + repère de pouvoir d'achat
INCONSISTENCY_PROMPT_VERSION = "inconsistency-v1"  # mesuré 9/10 constats, 0 faux positif


# --- Bilingue : directive de langue injectée en tête des prompts génératifs -----
# Le contenu généré par l'IA (bilan, coach, deck…) suit la langue du porteur.
# Défaut "fr" (marché actuel) → aucun changement de comportement tant que non "en".
_LANG_DIRECTIVE = {
    "fr": "Rédige TOUTE ta réponse en français.",
    "en": "Write your ENTIRE response in English (labels, prose, values).",
}


def lang_directive(lang: str | None) -> str:
    return _LANG_DIRECTIVE.get((lang or "fr").lower(), _LANG_DIRECTIVE["fr"])


def build_extraction_prompt(
    *,
    idea: str,
    axes: list[dict],
    project_name: str | None = None,
    lang: str = "fr",
    currency: str = "XOF",
) -> str:
    # « Raconte, on structure » : depuis le RÉCIT LIBRE, on repère pour chaque dimension si
    # l'info est déjà là (preuve) ou s'il faut la demander (question) + un brouillon proposé.
    lines = [
        "FORMAT=extraction.",
        lang_directive(lang)
        + " (evidence, questions & suggestions suivent la langue ; les clés d'axes restent d1..d12)",
        "Tu es un analyste de projets. À partir du RÉCIT LIBRE du porteur, traite CHAQUE dimension :",
        "- si le récit donne assez d'info → captured=true + 'evidence' (courte preuve tirée du récit) ;",
        "- sinon → captured=false + 'question' (UNE question courte et simple) + 'suggestion' (voir ci-dessous).",
        "",
        "RÈGLE evidence : n'INVENTE rien — si l'info n'est pas dans le récit, c'est un manque (captured=false).",
        "",
        "RÈGLE suggestion (pour les manques uniquement) : propose un BROUILLON à la 1re personne, comme si",
        "tu devinais ce que le porteur AURAIT écrit, à partir du contexte de son récit (secteur, cible, ton).",
        "Objectif : qu'il se dise « oui, c'est exactement ça » et n'ait qu'à confirmer ou ajuster.",
        "1 phrase, concret, plausible, humble (pas de promesse grandiose). C'est une intuition, pas une vérité :",
        "reste cohérent avec CE projet précis. Pour tout montant/prix, exprime-le en " + currency + ".",
        "CHIFFRES : tout nombre que tu n'as PAS lu dans le récit (montant, volume, %, délai) est une",
        "ESTIMATION — écris-le précédé de « ≈ » et suivi de « (à confirmer) », ex. « ≈ 50 000 "
        + currency
        + " (à confirmer) ».",
        "Ne donne jamais un chiffre inventé comme s'il était un fait établi.",
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
        'Réponds STRICTEMENT en JSON : { "project_name": "<nom ou null>", "dimensions": {',
        '  "<key d1..d12>": { "captured": <true|false>, "evidence": "<preuve si captured, sinon \\"\\">", '
        '"question": "<question courte si manquant, sinon \\"\\">", '
        '"suggestion": "<brouillon 1re personne si manquant, sinon \\"\\">" } } }',
    ]
    return "\n".join(lines)


def build_verdict_prompt(*, persona: dict, transcript: str, slide_text: str, conviction: int, lang: str = "fr") -> str:
    # Délibération : l'agent donne SON verdict, avec SES mots et son style (Règle d'or n°5).
    # Il juge AUSSI la cohérence entre ce qui est dit (pitch) et ce qui est montré (deck).
    return "\n".join(
        [
            "FORMAT=verdict.",
            lang_directive(lang),
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
    lang: str = "fr",
) -> str:
    # Le comité note CHAQUE axe Fond contre ses ancres, à partir du transcript + des slides.
    # Marqueur FORMAT=axes : même contrat de sortie que le scoring Radar (axes + justifications).
    lines = [
        "FORMAT=axes.",
        lang_directive(lang) + " (les justifications suivent la langue ; les clés d'axes restent inchangées)",
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


def build_scoring_prompt(
    grid_axes: list[dict],
    *,
    category: str,
    archetype: str,
    description: str | None,
    answers: dict[str, str] | None,
    perspective: int = 0,
    lang: str = "fr",
) -> str:
    # `perspective` varie d'une passe à l'autre (ensemble) sans changer la rubrique :
    # on demande à l'IA un angle d'analyse légèrement différent pour révéler l'incertitude.
    lines: list[str] = [
        "FORMAT=axes.",
        lang_directive(lang) + " (les justifications suivent la langue ; les clés d'axes restent d1..d12)",
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
    lang: str = "fr",
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
            lang_directive(lang),
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
            "*ex : abonnement SaaS à 29 €/mois, commission de 15 % par transaction, licence annuelle à 5 000 €*",
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
    lang: str = "fr",
) -> str:
    # Tour de conversation dans un module (phase context).
    hist = "\n".join(f"{'Porteur' if t['role'] == 'porteur' else 'Coach'}: {t['text']}" for t in history[-6:])
    return "\n".join(
        [
            "FORMAT=module_coach.",
            lang_directive(lang),
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
    lang: str = "fr",
) -> str:
    # Pré-remplit le formulaire structuré à partir de la conversation de contexte.
    # Ne JAMAIS inventer — seulement ce qui est dans la conversation.
    projet = f"« {project_title} »" if project_title else "ce projet"
    secteur = f" ({sector})" if sector else ""
    sections_json = json.dumps(
        [{"key": s["key"], "label": s["label"]} for s in form_sections],
        ensure_ascii=False,
    )
    hist = "\n".join(f"{'Porteur' if t['role'] == 'porteur' else 'Coach'}: {t['text']}" for t in history)
    return "\n".join(
        [
            "FORMAT=form_prefill.",
            lang_directive(lang),
            f"À partir de la conversation sur le module « {dimension.upper()} — {label} »",
            f"pour le projet {projet}{secteur}, pré-remplis les sections du formulaire.",
            "RÈGLE ABSOLUE : ne JAMAIS inventer une info absente de la conversation.",
            'Si une section n\'est pas couverte par la conversation → chaîne vide ("").',
            "",
            f"SECTIONS DU FORMULAIRE : {sections_json}",
            "",
            "CONVERSATION :",
            hist or "(aucun historique)",
            "",
            'Réponds STRICTEMENT en JSON : { "<section_key>": "<valeur ou vide>", ... }',
        ]
    )


def build_module_fiches_prompt(
    *,
    dimension: str,
    label: str,
    form_data: dict,
    project_title: str | None = None,
    sector: str | None = None,
    lang: str = "fr",
) -> str:
    # Génère des fiches de besoin structurées à partir du formulaire rempli.
    projet = f"« {project_title} »" if project_title else "ce projet"
    secteur = f" ({sector})" if sector else ""
    return "\n".join(
        [
            "FORMAT=fiches.",
            lang_directive(lang)
            + " (titres, descriptions et détails suivent la langue ; les need_type restent des clés)",
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
            "  {",
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
            "    }",
            "  }",
            "] }",
        ]
    )


def build_report_prompt(
    *,
    category: str,
    archetype: str,
    description: str | None,
    answers: dict[str, str] | None,
    scores: dict[str, int] | None = None,
    lang: str = "fr",
) -> str:
    # Couche STRUCTURÉE du rapport de pré-diagnostic (au-delà des notes /10) : description,
    # verdict, matrice de risques, concurrents, avancement, recos priorisées, next steps.
    # Best-effort, affinée ensuite par l'analyste. Ton bienveillant et factuel.
    return "\n".join(
        [
            "FORMAT=report.",
            lang_directive(lang),
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


def build_pitch_section_prompt(
    *,
    section_title: str,
    section_hint: str,
    existing_content: str | None,
    evidence: str | None,
    project_title: str | None = None,
    sector: str | None = None,
    lang: str = "fr",
) -> str:
    """Génère ou améliore UNE section de pitch, à partir du travail Workshop.

    `evidence` = matière brute (synthèse Workshop de la dimension, ou fiches de
    besoin pour la section « Nos besoins »). Le ton est celui d'un pitch : court,
    concret, percutant — jamais de blabla ni de superlatifs creux.
    """
    projet = f"« {project_title} »" if project_title else "le projet"
    secteur = f" (secteur {sector})" if sector else ""
    mode = "AMÉLIORE" if (existing_content or "").strip() else "RÉDIGE"
    lines = [
        "FORMAT=pitch_section.",
        lang_directive(lang),
        f"Tu es un coach pitch. Tu {mode.lower()}s la section « {section_title} » du pitch de {projet}{secteur}.",
        f"Objectif de la section : {section_hint}",
        "STYLE : court et percutant (2 à 4 phrases MAX), concret, chiffré quand c'est possible.",
        "Pas de superlatifs creux (« révolutionnaire », « leader »), pas de listes à puces,",
        "pas de titre ni de préambule — juste le texte de la section, prêt à coller dans un deck.",
        "N'invente AUCUN chiffre : n'utilise que ce qui est étayé par la matière ci-dessous ;",
        "s'il manque une donnée, reste qualitatif plutôt que d'inventer.",
        "",
        "MATIÈRE (issue du diagnostic et du Workshop) :",
        evidence or "(peu d'éléments — reste général mais honnête)",
    ]
    if (existing_content or "").strip():
        lines += ["", "VERSION ACTUELLE À AMÉLIORER :", existing_content or ""]
    lines += ["", "Réponds UNIQUEMENT par le texte de la section (aucun JSON, aucun guillemet englobant)."]
    return "\n".join(lines)


# --- Incohérences : détection de contradictions internes ------------------------
# Chaque type est une PROCÉDURE exécutable, pas une exhortation. La mesure a montré que
# « RECALCULE tout produit volume × prix » fonctionne là où « COMPARE les durées » échoue :
# une procédure donne des étapes, une exhortation donne une intention.
# Les procédures sont en français ; le paramètre `lang` ne pilote que la langue de SORTIE
# (une version anglaise des procédures reste à écrire ET à mesurer avant usage).
_INCONSISTENCY_PROCEDURES: dict[InconsistencyType, str] = {
    InconsistencyType.ARITHMETIC: (
        "PROCÉDURE : (1) relève tout couple volume + prix unitaire ; (2) calcule le produit ; "
        "(3) compare-le au chiffre d'affaires ou au revenu déclaré ; (4) signale tout écart "
        "SIGNIFICATIF. Un porteur qui écrit « environ », « à peu près » ou « ~ » arrondit : "
        "un écart inférieur à 10 % sur un montant explicitement approximatif est un arrondi "
        "NORMAL et ne se signale JAMAIS. On cherche les écarts d'un facteur, pas les décimales."
    ),
    InconsistencyType.CAPACITY: (
        "PROCÉDURE : (1) relève la taille exacte de l'équipe et les moyens déclarés ; (2) relève "
        "tous les volumes, couvertures géographiques et fréquences annoncés ; (3) confronte les "
        "deux et signale ce qui excède manifestement les moyens décrits."
    ),
    InconsistencyType.MARKET: (
        "PROCÉDURE : (1) identifie QUI PAIE — un ménage, ou une entreprise ? Le repère de revenu "
        "des ménages ne vaut QUE si le payeur est un particulier : pour un prix facturé à un "
        "commerçant ou à une entreprise, il est HORS SUJET. Dans ce cas `found: false`, liste "
        "VIDE, et tu n'écris RIEN — pas même pour expliquer que le repère ne s'applique pas ; "
        "(2) si le payeur "
        "est un ménage, relève le pouvoir d'achat qu'implique la cible déclarée ; (3) relève le "
        "prix annoncé ; (4) vérifie leur compatibilité."
    ),
    InconsistencyType.TEMPORAL: (
        "PROCÉDURE : (1) relève TOUTES les dates, durées et anciennetés du récit (depuis quand le "
        "projet existe, quelle profondeur d'historique est invoquée, quelle durée d'expérience) ; "
        "(2) compare-les deux à deux ; (3) signale toute paire où l'une rend l'autre impossible — "
        "par exemple un historique de données plus long que l'ancienneté du projet lui-même."
    ),
    InconsistencyType.INTERNAL: (
        "PROCÉDURE : (1) repère toute affirmation ABSOLUE ou d'unicité (« aucun concurrent », "
        "« personne ne fait », « le seul », « déjà N utilisateurs », « validé par ») ; (2) relis "
        "le RESTE du récit en cherchant une phrase qui la dément ; (3) signale la paire."
    ),
    InconsistencyType.REGULATORY: (
        "PROCÉDURE : (1) repère toute activité impliquant une obligation légale — détention de "
        "fonds de tiers, collecte d'épargne, données de santé, acte réservé à une profession ; "
        "(2) cherche dans le récit une affirmation qui NIE explicitement cette obligation "
        "(« nous n'avons pas besoin d'agrément », « nous ne sommes qu'un intermédiaire »). "
        "SANS cette négation explicite, il n'y a PAS de contradiction : un dossier qui reste "
        "muet sur la réglementation ne se contredit pas, il est seulement incomplet — et un "
        "manque n'est jamais un constat. N'écris JAMAIS « le récit ne mentionne pas… »."
    ),
}

# Deux passes de trois types. Le regroupement sépare ce qui se vérifie PAR CALCUL de ce qui se
# vérifie PAR RELECTURE. Mesuré meilleur qu'une passe unique (procédures diluées) et qu'une
# passe par type (six appels, et un chercheur isolé n'ose plus rien signaler).
INCONSISTENCY_GROUPS: dict[str, tuple[InconsistencyType, ...]] = {
    "quantitative": (
        InconsistencyType.ARITHMETIC,
        InconsistencyType.CAPACITY,
        InconsistencyType.MARKET,
    ),
    "textual": (
        InconsistencyType.TEMPORAL,
        InconsistencyType.INTERNAL,
        InconsistencyType.REGULATORY,
    ),
}


def build_context_prompt(*, narrative: str, lang: str = "fr") -> str:
    """Déduit pays et devise — sans quoi `market` et `regulatory` jugent à l'aveugle.

    Un prix ne se juge que rapporté au pouvoir d'achat local, et une obligation légale dépend
    de la juridiction. Passe EXPLICITE plutôt que déduction implicite dans chaque prompt :
    le contexte retenu figure dans le rapport d'audit, et le client peut le contester.
    """
    return "\n".join(
        [
            "FORMAT=context.",
            lang_directive(lang) + " (les clés JSON restent en anglais)",
            "Déduis du récit ci-dessous le pays et la devise dans lesquels le projet opère.",
            "Appuie-toi sur les indices explicites : villes, monnaies citées, institutions,",
            "dispositifs sociaux, mentions géographiques, vocabulaire administratif.",
            "Si aucun indice fiable n'existe, réponds country et currency à null — n'invente pas.",
            "",
            "Donne aussi un ORDRE DE GRANDEUR du revenu mensuel d'un ménage modeste dans ce pays,",
            "exprimé dans la devise locale. C'est ce repère qui permettra de juger si un prix est",
            "compatible avec la cible annoncée.",
            "",
            "RÉCIT :",
            narrative,
            "",
            "Réponds STRICTEMENT en JSON :",
            '{ "country": "<pays ou null>", "currency": "<code ISO ou null>",',
            '  "signals": "<les indices qui ont permis de trancher, 1 phrase>",',
            '  "modest_household_income": "<ordre de grandeur mensuel, devise locale, ou null>" }',
        ]
    )


def _inconsistency_context_block(context: dict | None) -> list[str]:
    if not context or not context.get("country"):
        return [
            "CONTEXTE : pays indéterminé. Ne juge PAS le pouvoir d'achat ni les obligations",
            "réglementaires — tu n'as pas la juridiction. Concentre-toi sur les incohérences",
            "internes au récit, qui ne dépendent d'aucun pays.",
            "",
        ]
    income = context.get("modest_household_income") or "non déterminé"
    return [
        f"CONTEXTE DÉTECTÉ : pays = {context['country']} · devise = {context.get('currency') or '?'}.",
        f"Repère de pouvoir d'achat : revenu mensuel d'un ménage modeste ≈ {income}.",
        "Utilise CE repère pour juger si un prix est compatible avec la cible annoncée,",
        "et CETTE juridiction pour juger les obligations réglementaires. Un même montant",
        "n'a pas la même portée selon le pays : raisonne toujours en ordre de grandeur local.",
        "ATTENTION : ce bloc de contexte est une donnée de RÉFÉRENCE, il ne fait PAS partie du",
        "récit du porteur. Ne le cite JAMAIS comme passage : toute citation doit être extraite",
        "du récit lui-même, et de lui seul.",
        "",
    ]


def build_inconsistency_prompt(
    *,
    narrative: str,
    group: str,
    category: str,
    archetype: str,
    context: dict | None = None,
    lang: str = "fr",
) -> str:
    """Détecte les contradictions internes d'un récit, pour un groupe de types donné.

    Ne note rien et ne juge pas la qualité du projet : constate ce qui ne peut pas être vrai
    en même temps, en citant les deux passages. C'est ce qui rend le constat vérifiable en
    cinq secondes par le client, donc vendable sans calibration préalable.
    """
    types = INCONSISTENCY_GROUPS[group]
    lines = [
        "FORMAT=inconsistencies.",
        lang_directive(lang) + " (les clés et valeurs JSON restent en anglais)",
        "Tu es un analyste de dossiers entrepreneuriaux, rigoureux et strictement factuel.",
        f"Catégorie : {category} · Archétype : {archetype}.",
        "Tu ne notes rien, tu n'évalues pas la qualité du projet, tu ne donnes aucun conseil.",
        "",
        *_inconsistency_context_block(context),
        f"Tu examines UNIQUEMENT le groupe « {group} » : {', '.join(t.value for t in types)}.",
        "Applique CHAQUE procédure ci-dessous, l'une APRÈS l'autre, et prononce-toi sur CHACUNE.",
        "Produis une entrée par type, même quand tu ne trouves rien.",
        "",
        "RÈGLE ABSOLUE — un MANQUE d'information n'est PAS une contradiction.",
        "Un récit incomplet, vague, modeste ou prudent est NORMAL à ce stade d'un projet.",
        "Un porteur qui reconnaît ce qu'il ne sait pas encore est honnête, pas contradictoire :",
        "ne le signale JAMAIS pour ça.",
        "Une FAIBLESSE, un sous-dimensionnement, un risque ou une fragilité du projet n'est PAS",
        "une contradiction. Ne signale que des INCOMPATIBILITÉS FACTUELLES entre deux affirmations.",
        "",
        "RÈGLE SYMÉTRIQUE — les deux moitiés comptent autant :",
        "- Si ta vérification CONFIRME la cohérence → `found: false`, liste vide. C'est un succès,",
        "  et tu n'exposes JAMAIS dans `contradictions` un calcul qui tombe juste. La liste",
        "  `contradictions` ne contient QUE des contradictions : si ton explication contient le mot",
        "  « cohérent », « correct » ou « compatible », l'entrée n'a rien à y faire — retire-la.",
        "- Si ta vérification RÉVÈLE un écart → SIGNALE-LE sans hésiter, c'est exactement ce qu'on",
        "  cherche. Un écart avéré est la trouvaille la plus précieuse de toutes.",
        "",
        "ANTI-DOUBLON : une même contradiction n'apparaît qu'UNE fois, sous le type le plus spécifique.",
        "",
        "NE RENDS JAMAIS COMPTE DE TA MÉTHODE. Les `contradictions` parlent du DOSSIER, jamais de",
        "la façon dont tu l'as analysé. « le calcul est cohérent », « ce repère ne s'applique pas »,",
        "« ce type est hors sujet ici » sont des remarques sur TON travail : elles n'ont rien à y",
        "faire. Quand une procédure ne donne rien, la bonne réponse est le SILENCE : `found: false`.",
        "",
        "PROCÉDURES À APPLIQUER, DANS CET ORDRE :",
        *[f"- {t.value} : {_INCONSISTENCY_PROCEDURES[t]}" for t in types],
        "",
        "Pour CHAQUE contradiction, cite les DEUX passages en conflit, MOT POUR MOT, et tous deux",
        "extraits du RÉCIT DU PORTEUR uniquement — jamais du bloc de contexte, jamais de ta propre",
        "rédaction. Un calcul que tu poses (« 1 200 × 5 000 = 6 000 000 ») n'est PAS une citation :",
        "il va dans `explanation`. Si tu ne peux pas produire deux extraits littéraux, ne signale rien.",
        "",
        "RÉCIT DU PORTEUR :",
        narrative,
        "",
        f"Réponds STRICTEMENT en JSON, avec les {len(types)} types du groupe, dans l'ordre :",
        '{ "analysis": [ { "type": "<type>", "found": <true|false>, "contradictions": [',
        '  { "quote_a": "<citation tirée du récit>", "quote_b": "<citation tirée du récit>",',
        '    "explanation": "<1 phrase>", "severity": "high|medium|low" } ] } ] }',
    ]
    return "\n".join(lines)


def build_deck_prompt(
    *,
    source: str,
    project_title: str | None = None,
    sector: str | None = None,
    lang: str = "fr",
) -> str:
    """Transforme la matière (pitch/Workshop/texte) en SLIDES structurées.

    Sortie = JSON. Peu de texte, des CHIFFRES, un visuel par slide. Le rendu
    HTML/CSS se charge du beau ; l'IA ne produit que la structure et la substance.
    """
    projet = f"« {project_title} »" if project_title else "le projet"
    secteur = f" (secteur {sector})" if sector else ""
    return "\n".join(
        [
            "FORMAT=deck.",
            lang_directive(lang) + " (titres, bullets, légendes suivent la langue ; image_keyword reste en anglais)",
            f"Tu es un designer de pitch deck. À partir de la MATIÈRE ci-dessous sur {projet}{secteur},",
            "produis un deck de 7 à 10 slides, façon Gamma : PEU de texte, des CHIFFRES, un visuel par slide.",
            "",
            "RÈGLES :",
            "- Titre de slide : 3 à 6 mots MAX. Bullets : 3 max, une ligne chacune, percutantes.",
            "- Mets en avant les CHIFFRES réels de la matière (montants, %, volumes) — n'en invente aucun.",
            "- Choisis le bon layout par slide :",
            "  · cover   → 1re slide : titre du projet + sous-titre accrocheur + image_keyword",
            "  · stat    → UN chiffre clé : stat={value,label} + une phrase de contexte",
            "  · bullets → titre + 2-3 bullets + image_keyword",
            "  · chart   → titre + chart={type:'bar'|'line'|'pie', labels:[...], values:[...]} (données de la matière)",
            "  · image   → titre + image_keyword + 1 courte légende",
            "- Couvre l'arc : accroche, problème, solution, marché (stat/chart), modèle éco (chart), "
            "traction (stat), concurrence, équipe, demande/besoins.",
            "- image_keyword = 1 à 3 mots ANGLAIS pour une photo Unsplash (ex. 'city logistics', 'team meeting').",
            "",
            "MATIÈRE :",
            source or "(peu d'éléments — reste général mais honnête)",
            "",
            'Réponds STRICTEMENT en JSON : { "slides": [ {',
            '  "layout": "cover|stat|bullets|chart|image",',
            '  "title": "...", "subtitle": "", "bullets": [], ',
            '  "stat": { "value": "", "label": "" }, ',
            '  "chart": { "type": "bar", "labels": [], "values": [] }, ',
            '  "image_keyword": "", "caption": "" } ] }',
            "Omets les champs non pertinents pour le layout (ou laisse-les vides).",
        ]
    )
