"""Score de Forme — proxies DÉTERMINISTES sur le texte (pas de biométrie au MVP).

« Indicatif », jamais le credential (cf. SPEC §1). Quatre proxies, chacun /10 :
- concision  : volume de parole vs durée cible (~130 mots/min) ;
- fluidite   : pénalité de tics de langage ;
- completude : a-t-on répondu aux questions des juges ? ;
- structure  : présence des briques attendues (problème/solution/marché/modèle/ask).

Tout est calculé en clair → défendable et rejouable. Les 2 axes biométriques du radar
(impact émotionnel, posture) restent `null` hors Mode Caméra.
"""

from __future__ import annotations

from app.pitchsim.scenario import count_fillers

WORDS_PER_MINUTE = 130
_STRUCTURE_HINTS = {
    "probleme": ("problème", "probleme", "douleur"),
    "solution": ("solution", "produit", "service"),
    "marche": ("marché", "marche", "client", "cible"),
    "modele": ("modèle", "revenu", "prix", "commission", "abonnement"),
    "ask": ("demande", "recherche", "levée", "besoin", "ask"),
}


def _clamp(x: float) -> float:
    return round(max(0.0, min(10.0, x)), 1)


def score_forme(*, narration_text: str, n_questions: int, n_answers: int, duration_min: int) -> dict:
    words = len(narration_text.split())
    expected = max(1, duration_min * WORDS_PER_MINUTE)
    ratio = words / expected
    # concision : optimum à ~1.0 ; on pénalise l'écart (trop court OU trop long).
    concision = _clamp(10 - abs(1 - ratio) * 10)

    fillers = count_fillers(narration_text)
    fluidite = _clamp(10 - fillers)  # ~1 point par tic

    completude = _clamp(10 * (n_answers / n_questions)) if n_questions else 10.0

    t = narration_text.lower()
    present = sum(1 for hints in _STRUCTURE_HINTS.values() if any(h in t for h in hints))
    structure = _clamp(10 * present / len(_STRUCTURE_HINTS))

    scores = {
        "concision": concision,
        "fluidite": fluidite,
        "completude": completude,
        "structure": structure,
    }
    overall = _clamp(sum(scores.values()) / len(scores))
    return {"scores": scores, "overall": overall}
