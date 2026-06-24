"""Moteur de scénario — imprévus NON aléatoires, déclenchés par les faiblesses.

Cœur de l'innovation : pendant un tour, on **pré-note la narration par heuristique**
(déterministe, coût ~0) → l'axe faible désigne **le juge dont c'est l'obsession** (§5), qui
**interrompt** avec une question ciblée. Le vrai scoring LLM, lui, n'a lieu qu'à `finish`
(PITCH-04) → on garde le drame en temps réel sans exploser le coût freemium.

Tout est **pur et déterministe** (sélection par hash, pas de `random`) → testable et rejouable.
"""

from __future__ import annotations

import hashlib

from app.pitchsim.constants import FILLER_WORDS

# Types d'imprévus (cf. SPEC §7.3 / UX innovation 2).
IMPREVU_INTERRUPTION = "interruption"
IMPREVU_DOUBT = "doute"
IMPREVU_TRAP = "question_piege"
IMPREVU_INVESTOR = "investor_surprise"

# Questions ciblées par axe : le juge attaque son obsession.
AXIS_QUESTIONS: dict[str, str] = {
    "clarte_probleme": "En une phrase : quel est le problème, et pour qui exactement ?",
    "solution": "En quoi votre solution est-elle défendable si un grand groupe la copie demain ?",
    "marche": "Votre chiffre de marché, d'où vient-il ? Donnez-moi la source.",
    "business_model": "Concrètement : qui paie, combien, et quelle est votre marge ?",
    "traction": "Quelles preuves d'usage avez-vous, chiffrées ?",
    "equipe": "Pourquoi votre équipe est-elle la bonne pour exécuter ça ?",
    "gestion_questions": "Vous esquivez. Répondez précisément à la question posée.",
    "resilience": "Vous semblez déstabilisé. Reprenez : quel est l'essentiel ?",
}

# Mots-clés qui ATTÉNUENT la faiblesse d'un axe (présence = signal positif).
_MONEY_HINTS = ("€", "euro", "prix", "abonnement", "commission", "marge", "paie", "payer")
_PROOF_HINTS = ("client", "pilote", "utilisateur", "vente", "%", "croissance", "preuve", "test")

# Priorité de traitement des faiblesses (du plus structurant au plus fin).
_AXIS_PRIORITY = [
    "clarte_probleme",
    "marche",
    "business_model",
    "traction",
    "solution",
    "equipe",
]


def _seed(*parts: str) -> int:
    # Entier stable dérivé d'un hash — déterministe, sans random (rejouable).
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def assess_weakness(text: str) -> list[str]:
    """Heuristique déterministe : axes faibles d'une narration (pré-notation gratuite)."""
    t = (text or "").lower()
    words = t.split()
    weak: list[str] = []
    if len(words) < 12:
        weak.append("clarte_probleme")  # trop court = problème pas posé
    if not any(c.isdigit() for c in t):
        weak.append("marche")  # aucun chiffre = marché non quantifié
    if not any(h in t for h in _MONEY_HINTS):
        weak.append("business_model")  # pas de logique de revenu
    if not any(h in t for h in _PROOF_HINTS):
        weak.append("traction")  # aucune preuve
    return weak


def count_fillers(text: str) -> int:
    """Tics de langage (pour le score de Forme-texte, PITCH-04)."""
    t = (text or "").lower()
    return sum(t.count(f) for f in FILLER_WORDS)


def choose_interruption(
    personas: list[dict],
    weak_axes: list[str],
    *,
    imprevus_enabled: bool,
    hard_questions: bool,
    seed_key: str,
) -> dict | None:
    """Décide si un juge interrompt, lequel, sur quel axe, avec quel type d'imprévu.

    Renvoie {actor, axis, type, content} ou None. Un juge n'intervient que si une faiblesse
    touche SON obsession (sinon le comité laisse passer).
    """
    if not imprevus_enabled or not weak_axes:
        return None
    weak = set(weak_axes)
    obsessed = {p["obsession"]: p for p in personas}
    # Première faiblesse (par priorité) couverte par un juge du comité.
    for axis in _AXIS_PRIORITY:
        if axis in weak and axis in obsessed:
            persona = obsessed[axis]
            types = [IMPREVU_INTERRUPTION, IMPREVU_DOUBT, IMPREVU_TRAP] if hard_questions else [IMPREVU_INTERRUPTION]
            imprevu_type = types[_seed(seed_key, axis) % len(types)]
            question = AXIS_QUESTIONS.get(axis, "Précisez ce point.")
            return {
                "actor": persona["name"],
                "axis": axis,
                "type": imprevu_type,
                "content": f"{persona['name']} : {question}",
            }
    return None


def investor_surprise() -> dict:
    """Imprévu « investisseur surprise » (déclenché manuellement ou en fin de session)."""
    return {
        "actor": "M. Traoré",
        "axis": "clarte_probleme",
        "type": IMPREVU_INVESTOR,
        "content": (
            "M. Traoré (Family Office, ticket 500k€) vient d'entrer. Il ne connaît rien de "
            "votre projet. Vous avez 90 secondes pour le convaincre — l'essentiel, maintenant."
        ),
    }


def deliberation(personas: list[dict], weak_axes: list[str]) -> list[dict]:
    """Verdicts courts du comité en fin de session (un par juge, déterministe)."""
    weak = set(weak_axes)
    verdicts: list[dict] = []
    for p in personas:
        if p["obsession"] in weak:
            line = f"Pas convaincu sur {p['obsession'].replace('_', ' ')}."
        else:
            line = "Solide sur mon point."
        verdicts.append({"actor": p["name"], "content": f"{p['name']} : {line}"})
    return verdicts
