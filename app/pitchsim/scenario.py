"""Heuristiques de pré-notation (déterministes, sans LLM).

Utilisées par le flux « comité silencieux » : `assess_weakness` pilote les micro-réactions et
la conviction pendant le pitch ; `count_fillers` alimente le score de Forme (PITCH-04).

NB : l'ancien moteur d'interruption (choose_interruption / imprévus / délibération générique) a
été retiré lors de la bascule sur le modèle canonique « comité silencieux » (SPEC §14).
"""

from __future__ import annotations

from app.pitchsim.constants import FILLER_WORDS

# Mots-clés qui ATTÉNUENT la faiblesse d'un axe (présence = signal positif).
_MONEY_HINTS = ("€", "euro", "prix", "abonnement", "commission", "marge", "paie", "payer")
_PROOF_HINTS = ("client", "pilote", "utilisateur", "vente", "%", "croissance", "preuve", "test")


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
