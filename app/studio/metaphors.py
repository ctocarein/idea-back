"""Bibliothèque de métaphores — pictos « sens » pour le mode typographique.

Contrairement à `vocab.ICONS` (viewBox 24, pictos génériques accolés au wordmark),
ces métaphores sont pensées pour **habiter une lettre** (letter-swap / inhabit / attach) :
tracés pleins dans une box 0..100, calés pour lire au poids d'un caractère gras.

L'IA CHOISIT une clé dans cet ensemble fermé (elle ne dessine jamais le path) ; le
`keyword_to_metaphor` route un mot du récit (« écrire », « pousse »…) vers la bonne clé.
"""

from __future__ import annotations

# clé → path SVG rempli (box locale 0..100, origine haut-gauche).
METAPHORS: dict[str, str] = {
    # écriture / idées
    "spark": "M50 4 L59 39 L96 50 L59 61 L50 96 L41 61 L4 50 L41 39 Z",
    "bulb": (
        "M50 8 A30 30 0 0 1 68 64 L64 74 H36 L32 64 A30 30 0 0 1 50 8 Z"
        "M38 80 H62 V86 H38 Z M42 90 H58 V94 H42 Z"
    ),
    "pencil": "M34 4 H66 V16 H34 Z M34 20 H66 V70 L50 96 L34 70 Z",
    "feather": "M22 92 Q18 44 60 14 Q86 34 60 74 Q46 96 22 92 Z",
    # croissance / nature
    "sprout": (
        "M46 96 H54 V54 H46 Z"
        "M46 60 Q22 60 20 36 Q46 36 46 60 Z M54 56 Q78 56 80 32 Q54 32 54 56 Z"
    ),
    "leaf": "M50 6 C16 20 16 66 50 94 C84 66 84 20 50 6 Z M50 20 V82",
    "drop": "M50 6 C50 6 20 44 20 66 A30 30 0 0 0 80 66 C80 44 50 6 50 6 Z",
    "mountain": "M6 88 L34 38 L52 66 L68 30 L94 88 Z",
    # cuisine / food
    "spoon": "M50 4 A18 26 0 0 1 50 56 A18 26 0 0 1 50 4 Z M44 54 H56 L53 96 H47 Z",
    "flask": "M40 6 H60 V38 L82 88 Q86 98 74 98 H26 Q14 98 18 88 L40 38 Z",
    # savoir / tech / business
    "book": "M50 22 C38 12 18 12 8 18 V82 C18 76 38 76 50 86 C62 76 82 76 92 82 V18 C82 12 62 12 50 22 Z M50 22 V86",  # noqa: E501
    "rocket": "M50 4 C66 18 72 40 72 60 H28 C28 40 34 18 50 4 Z M28 60 L14 82 H34 M72 60 L86 82 H66 M50 30 a8 8 0 0 0 0 16 a8 8 0 0 0 0 -16 Z",  # noqa: E501
    "gear": "M50 20 L58 22 L64 16 L72 24 L66 30 L70 38 L78 40 L78 50 L70 52 L66 60 L72 66 L64 74 L58 68 L50 70 L42 68 L36 74 L28 66 L34 60 L30 52 L22 50 L22 40 L30 38 L34 30 L28 24 L36 16 L42 22 Z M50 34 a12 12 0 1 0 0.1 0 Z",  # noqa: E501
    "graph": "M14 86 V14 H22 V78 H90 V86 Z M32 70 L52 46 L66 58 L86 28 L86 46 L66 74 L52 62 L32 82 Z",
    "heart": "M50 88 C50 88 12 62 12 36 A20 20 0 0 1 50 26 A20 20 0 0 1 88 36 C88 62 50 88 50 88 Z",
    "shield": "M50 6 L86 20 V48 C86 74 50 96 50 96 C50 96 14 74 14 48 V20 Z",
    "star": "M50 6 L62 38 L96 40 L69 62 L78 96 L50 76 L22 96 L31 62 L4 40 L38 38 Z",
    "sun": "M50 26 a24 24 0 1 0 0.1 0 Z M50 2 V16 M50 84 V98 M2 50 H16 M84 50 H98 M15 15 L26 26 M74 74 L85 85 M85 15 L74 26 M26 74 L15 85",  # noqa: E501
}

# Mots-clés (récit / secteur) → clé de métaphore. L'IA peut aussi choisir directement ;
# ce mapping sert de repli déterministe et de garde-fou.
_KEYWORDS: dict[str, str] = {
    "idée": "bulb", "idea": "bulb", "innovation": "spark", "créa": "spark",
    "écri": "feather", "writ": "feather", "plume": "feather", "édition": "book",
    "crayon": "pencil", "design": "pencil", "dessin": "pencil",
    "pousse": "sprout", "graine": "sprout", "agri": "sprout", "croissance": "sprout",
    "nature": "leaf", "bio": "leaf", "vert": "leaf", "eco": "leaf",
    "eau": "drop", "goutte": "drop", "boisson": "drop",
    "montagne": "mountain", "sommet": "mountain", "outdoor": "mountain",
    "cuisine": "spoon", "food": "spoon", "resto": "spoon", "repas": "spoon",
    "labo": "flask", "chimie": "flask", "science": "flask", "santé": "flask",
    "livre": "book", "edu": "book", "formation": "book", "école": "book", "savoir": "book",
    "fusée": "rocket", "startup": "rocket", "lancement": "rocket", "boost": "rocket",
    "tech": "gear", "outil": "gear", "moteur": "gear", "process": "gear",
    "data": "graph", "finance": "graph", "croiss": "graph", "analyse": "graph",
    "cœur": "heart", "soin": "heart", "care": "heart", "amour": "heart",
    "sécur": "shield", "protec": "shield", "assur": "shield", "confiance": "shield",
    "étoile": "star", "premium": "star", "qualité": "star", "excellence": "star",
    "soleil": "sun", "énergie": "sun", "solaire": "sun", "lumière": "bulb",
}

DEFAULT_METAPHOR = "spark"


def keyword_to_metaphor(text: str | None) -> str:
    """Route un mot/récit vers une clé de métaphore connue (sinon DEFAULT)."""
    if not text:
        return DEFAULT_METAPHOR
    low = text.lower()
    for kw, key in _KEYWORDS.items():
        if kw in low:
            return key
    return DEFAULT_METAPHOR


def resolve_metaphor(value: str | None, *, fallback_text: str | None = None) -> str:
    """Valide une clé choisie par l'IA ; sinon route depuis un texte ; sinon défaut."""
    if isinstance(value, str) and value in METAPHORS:
        return value
    return keyword_to_metaphor(fallback_text)
