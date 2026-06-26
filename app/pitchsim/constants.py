"""Rubrique de pitch (placeholder v1) + comités virtuels.

Même robustesse que la grille Radar : axes ANCRÉS (paliers contigus 0..10), versionnés.
- `PITCH_AXES` : 8 axes **Fond** notés par le LLM → le credential portable.
- `BIO_AXES`   : 2 axes biométriques (ton/voix, posture/regard) → Mode Caméra (Premium/V2),
  renvoyés `null` au MVP.
- `COMMITTEES` : 3 comités, chaque juge a une **obsession = un axe Fond** → c'est le lien
  « faiblesse détectée → juge qui attaque » (moteur de scénario, PITCH-03).

Les ancres/personas sont *placeholder* : à figer en atelier produit, comme la grille Radar.
"""

from __future__ import annotations

PITCH_RUBRIC_VERSION = "pitch-v1-placeholder"
PITCH_SCALE_MAX = 10


def _bands(b0: str, b1: str, b2: str, b3: str) -> list[dict]:
    # 4 paliers contigus couvrant 0..10 (max exclusif sauf le plus haut) — cf. engine.anchors_cover_range.
    return [
        {"min": 0, "max": 3, "label": b0},
        {"min": 3, "max": 6, "label": b1},
        {"min": 6, "max": 8, "label": b2},
        {"min": 8, "max": 10, "label": b3},
    ]


# --- 8 axes Fond (notés par le LLM, ancrés) ---
PITCH_AXES: list[dict] = [
    {
        "key": "clarte_probleme",
        "label": "Clarté du problème",
        "kind": "fond",
        "source": "llm",
        "weight": 0.15,
        "central_question": "Le problème est-il compris en 30 secondes ?",
        "anchors": _bands(
            "Problème absent ou confus.",
            "Problème évoqué mais vague ou non incarné.",
            "Problème clair, cible identifiée.",
            "Problème limpide, ressenti, chiffré et incarné.",
        ),
    },
    {
        "key": "solution",
        "label": "Solution",
        "kind": "fond",
        "source": "llm",
        "weight": 0.15,
        "central_question": "La solution est-elle pertinente et faisable ?",
        "anchors": _bands(
            "Solution floue ou hors-sujet.",
            "Solution plausible mais générique.",
            "Solution pertinente et différenciée.",
            "Solution évidente, différenciée et défendable.",
        ),
    },
    {
        "key": "marche",
        "label": "Marché",
        "kind": "fond",
        "source": "llm",
        "weight": 0.12,
        "central_question": "Les chiffres de marché sont-ils crédibles et sourcés ?",
        "anchors": _bands(
            "Aucun dimensionnement.",
            "Chiffres avancés sans source.",
            "Marché dimensionné, sources partielles.",
            "TAM/SAM/SOM sourcés et défendables.",
        ),
    },
    {
        "key": "business_model",
        "label": "Business model",
        "kind": "fond",
        "source": "llm",
        "weight": 0.15,
        "central_question": "Qui paie, combien, pourquoi — et est-ce viable ?",
        "anchors": _bands(
            "Modèle économique absent.",
            "Source de revenus citée sans logique de marge.",
            "Modèle cohérent, unit economics esquissés.",
            "Modèle viable, marge et coût d'acquisition tenus.",
        ),
    },
    {
        "key": "traction",
        "label": "Traction / preuves",
        "kind": "fond",
        "source": "llm",
        "weight": 0.15,
        "central_question": "Y a-t-il des preuves d'usage ou de demande ?",
        "anchors": _bands(
            "Aucune preuve.",
            "Intérêt déclaratif, pas de preuve.",
            "Premières preuves (pilotes, usagers).",
            "Traction mesurée et croissante.",
        ),
    },
    {
        "key": "equipe",
        "label": "Équipe",
        "kind": "fond",
        "source": "llm",
        "weight": 0.12,
        "central_question": "L'équipe est-elle crédible pour exécuter ?",
        "anchors": _bands(
            "Équipe non présentée.",
            "Profils cités sans adéquation claire.",
            "Équipe complémentaire et engagée.",
            "Équipe complémentaire, légitime et qui a déjà exécuté.",
        ),
    },
    {
        "key": "gestion_questions",
        "label": "Gestion des questions",
        "kind": "fond",
        "source": "llm",
        "weight": 0.08,
        "central_question": "Les réponses aux juges sont-elles solides et chiffrées ?",
        "anchors": _bands(
            "Réponses évasives ou hors-sujet.",
            "Réponses partielles, peu étayées.",
            "Réponses claires et argumentées.",
            "Réponses précises, chiffrées, qui désamorcent le doute.",
        ),
    },
    {
        "key": "resilience",
        "label": "Résilience sous pression",
        "kind": "fond",
        "source": "llm",
        "weight": 0.08,
        "central_question": "Le porteur garde-t-il son calme et sa clarté sous pression ?",
        "anchors": _bands(
            "Se déstabilise, perd le fil.",
            "Tient mais se crispe sous la pression.",
            "Reste clair et posé face aux objections.",
            "Transforme l'objection en force, garde le cap.",
        ),
    },
]

# --- 2 axes biométriques (Mode Caméra — Premium/V2), null au MVP ---
BIO_AXES: list[dict] = [
    {
        "key": "impact_emotionnel",
        "label": "Impact émotionnel (ton, voix)",
        "kind": "bio",
        "source": "biometric",
        "central_question": "Le ton est-il engageant et confiant ?",
        "available": "camera",  # nécessite l'audio/vidéo + consentement RGPD
    },
    {
        "key": "posture_regard",
        "label": "Posture & regard",
        "kind": "bio",
        "source": "biometric",
        "central_question": "Le langage non-verbal est-il maîtrisé ?",
        "available": "camera",
    },
]

# Mots de remplissage pour le score de Forme-texte (déterministe, PITCH-04).
FILLER_WORDS = ["euh", "ben", "en fait", "du coup", "voilà", "genre", "tu vois", "bah"]


# --- 3 comités virtuels (chaque juge : obsession = un axe Fond) ---
COMMITTEES: list[dict] = [
    {
        "key": "incubateur",
        "label": "Comité Incubateur",
        "personas": [
            {
                "name": "Mme Diallo",
                "role": "Directrice d'incubateur",
                "personality": "Visionnaire, bienveillante mais exigeante sur le fond",
                "style": "Encourage, puis pousse sur la mission et l'équipe",
                "obsession": "equipe",
            },
            {
                "name": "M. Morel",
                "role": "Serial entrepreneur",
                "personality": "Cynique, pragmatique",
                "style": "Déstabilise, coupe la parole, traque l'irréalisme",
                "obsession": "marche",
            },
            {
                "name": "Mme Chen",
                "role": "Experte financière",
                "personality": "Analytique, froide",
                "style": "Demande des preuves et des chiffres",
                "obsession": "business_model",
            },
            {
                "name": "M. Koné",
                "role": "Investisseur early-stage",
                "personality": "Impatient",
                "style": "Veut l'essentiel, coupe le blabla",
                "obsession": "traction",
            },
        ],
    },
    {
        "key": "concours",
        "label": "Comité Concours",
        "personas": [
            {
                "name": "Expert Innovation",
                "role": "Juré innovation",
                "personality": "Curieux, rigoureux",
                "style": "Sonde le problème et la solution",
                "obsession": "clarte_probleme",
            },
            {
                "name": "Expert Marché",
                "role": "Juré marché",
                "personality": "Sceptique",
                "style": "Challenge le marché et la concurrence",
                "obsession": "marche",
            },
            {
                "name": "Expert Impact",
                "role": "Juré impact",
                "personality": "Engagé",
                "style": "Interroge la mission et l'équipe",
                "obsession": "equipe",
            },
        ],
    },
    {
        "key": "investisseur",
        "label": "Comité Investisseur",
        "personas": [
            {
                "name": "VC Growth",
                "role": "VC croissance",
                "personality": "Ambitieux",
                "style": "Veut de la scalabilité et de la traction",
                "obsession": "traction",
            },
            {
                "name": "VC Deeptech",
                "role": "VC deeptech",
                "personality": "Exigeant techniquement",
                "style": "Sonde la différenciation et la défensibilité",
                "obsession": "solution",
            },
            {
                "name": "Business Angel",
                "role": "Business angel",
                "personality": "Humain, intuitif",
                "style": "Mise sur l'équipe et l'exécution",
                "obsession": "equipe",
            },
        ],
    },
]


def committee(key: str) -> dict | None:
    return next((c for c in COMMITTEES if c["key"] == key), None)


# --- Timing : format (taxonomie réelle des concours/comités) ---
# Speed-pitching, Standard, Approfondi : durée de pitch (minutes).
FORMATS = {"speed": 3, "standard": 5, "approfondi": 10}

# Profondeur de Q&A pilotée par le FORMAT (décision produit 2026-06-26) : le format pilote le
# nombre de questions par juge ; le comité ne fait que colorer le ton. Plus le format est court,
# plus les réponses doivent être concises (règle d'or : viser `answer_target_s`).
FORMAT_QA: dict[str, dict] = {
    "speed": {"qa_questions_per_agent": 1, "qa_minutes": 3, "answer_target_s": 45},
    "standard": {"qa_questions_per_agent": 2, "qa_minutes": 6, "answer_target_s": 45},
    "approfondi": {"qa_questions_per_agent": 3, "qa_minutes": 12, "answer_target_s": 60},
}


def format_qa(fmt: str) -> dict:
    return FORMAT_QA.get(fmt, FORMAT_QA["standard"])


# --- Contexte par comité : ton + format conseillé (PITCH-06 §14.5) ---
# Le comité ne fait que colorer le ton (décision produit 2026-06-26) : tous les formats sont
# permis partout ; `default_format` n'est que le format conseillé pour ce contexte.
_ALL_FORMATS = ["speed", "standard", "approfondi"]

COMMITTEE_TIMING: dict[str, dict] = {
    # Incubateurs / concours classiques → standard conseillé.
    "incubateur": {
        "default_format": "standard",
        "allowed_formats": _ALL_FORMATS,
        "tour_libre": True,
    },
    # Concours de pitch → speed/standard, conseillé standard.
    "concours": {
        "default_format": "standard",
        "allowed_formats": _ALL_FORMATS,
        "tour_libre": False,
    },
    # Comités d'investissement / grandes finales → approfondi conseillé.
    "investisseur": {
        "default_format": "approfondi",
        "allowed_formats": _ALL_FORMATS,
        "tour_libre": True,
    },
}


def committee_timing(key: str) -> dict:
    return COMMITTEE_TIMING.get(
        key,
        {
            "default_format": "standard",
            "allowed_formats": ["standard"],
            "tour_libre": False,
        },
    )


# --- Expert métier : 5ᵉ juge dynamique injecté selon project.sector (placeholder v1) ---
SECTOR_EXPERTS: dict[str, dict] = {
    "fintech": {
        "name": "Mme Sow (Fintech)",
        "role": "Experte fintech",
        "personality": "Pointue sur le risque",
        "style": "Sonde la régulation et les unit economics",
        "obsession": "business_model",
        "concerns": ["régulation / agrément", "confiance", "unit economics"],
    },
    "agritech": {
        "name": "M. Bah (AgriTech)",
        "role": "Expert agritech",
        "personality": "Pragmatique terrain",
        "style": "Confronte à la réalité de la chaîne d'appro",
        "obsession": "marche",
        "concerns": ["chaîne d'approvisionnement", "saisonnalité", "logistique"],
    },
    "sante": {
        "name": "Dr Mensah (Santé)",
        "role": "Expert santé",
        "personality": "Rigoureux",
        "style": "Exige la preuve et le cadre réglementaire",
        "obsession": "traction",
        "concerns": ["preuve clinique", "régulation", "remboursement"],
    },
    "edtech": {
        "name": "Mme Traoré (EdTech)",
        "role": "Experte edtech",
        "personality": "Exigeante sur l'usage",
        "style": "Challenge l'apprentissage réel et le modèle",
        "obsession": "traction",
        "concerns": ["preuve d'apprentissage", "engagement", "modèle B2B2C"],
    },
    "_default": {
        "name": "Expert Secteur",
        "role": "Expert métier",
        "personality": "Exigeant sur le terrain",
        "style": "Confronte aux réalités du secteur",
        "obsession": "solution",
        "concerns": ["spécificités du secteur"],
    },
}


def expert_for(sector: str | None) -> dict:
    return SECTOR_EXPERTS.get((sector or "").lower(), SECTOR_EXPERTS["_default"])


def resolve_personas(committee_key: str, sector: str | None) -> list[dict]:
    # Comité = personas fixes + expert sectoriel (→ « 3 à 5 juges »). Snapshotté sur la session.
    c = committee(committee_key)
    base = c["personas"] if c else []
    return [*base, expert_for(sector)]
