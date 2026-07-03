"""Vocabulaire curé du générateur de logo.

L'IA ne dessine PAS le SVG : elle CHOISIT dans ces ensembles fermés (type de marque,
icône, style géométrique, layout, pairing typo) + propose une palette hex. On compose
ensuite le SVG de façon déterministe (`logo_render`). Ça garantit un rendu toujours
propre, vectoriel et éditable — jamais de SVG halluciné.
"""

from __future__ import annotations

# --- Types de marque autorisés -------------------------------------------------
MARK_TYPES = ("icon", "monogram", "geometric")
LAYOUTS = ("icon-left", "icon-top", "mark-only", "wordmark-only")
CONTAINERS = ("none", "circle", "rounded", "square")

# --- Icônes (mot-clé → path SVG dans une viewBox 0 0 24 24) --------------------
# Pictogrammes simples et nets, remplis (fill). Choisis pour couvrir les thèmes
# récurrents des projets accompagnés. Path = tracé unique remplissable.
ICONS: dict[str, str] = {
    "spark": "M12 2 L14.6 9.4 L22 12 L14.6 14.6 L12 22 L9.4 14.6 L2 12 L9.4 9.4 Z",
    "bolt": "M13 2 L4 13.5 L11 13.5 L10 22 L20 9.5 L13 9.5 Z",
    "leaf": "M20 4 C10 4 4 10 4 20 C14 20 20 14 20 4 Z M8 16 L16 8",
    "drop": "M12 3 C12 3 5.5 11 5.5 15.5 A6.5 6.5 0 0 0 18.5 15.5 C18.5 11 12 3 12 3 Z",
    "heart": "M12 21 C12 21 3 14.5 3 8.8 A4.8 4.8 0 0 1 12 6.4 A4.8 4.8 0 0 1 21 8.8 C21 14.5 12 21 12 21 Z",
    "shield": "M12 2 L20 5.5 V11.5 C20 16.5 12 22 12 22 C12 22 4 16.5 4 11.5 V5.5 Z",
    "chat": "M4 4 H20 A2 2 0 0 1 22 6 V15 A2 2 0 0 1 20 17 H11 L6 21 V17 H4 A2 2 0 0 1 2 15 V6 A2 2 0 0 1 4 4 Z",
    "rocket": "M12 2 C16 5 17 10 17 14 H7 C7 10 8 5 12 2 Z M7 14 L4 18 H9 M17 14 L20 18 H15 M12 8 a1.6 1.6 0 0 0 0 3.2 a1.6 1.6 0 0 0 0 -3.2 Z",  # noqa: E501
    "book": "M4 4 H11 A2 2 0 0 1 13 6 V21 A2 2 0 0 0 11 19 H4 Z M13 6 A2 2 0 0 1 15 4 H21 V19 H15 A2 2 0 0 0 13 21 Z",
    "cart": "M3 4 H6 L8 15 H19 L21 7 H8 M9 20 a1.4 1.4 0 1 0 0.01 0 Z M18 20 a1.4 1.4 0 1 0 0.01 0 Z",
    "globe": "M12 2 A10 10 0 1 0 12 22 A10 10 0 0 0 12 2 Z M2.5 12 H21.5 M12 2.5 C7 7 7 17 12 21.5 C17 17 17 7 12 2.5 Z",  # noqa: E501
    "pin": "M12 2 A7 7 0 0 0 5 9 C5 15 12 22 12 22 C12 22 19 15 19 9 A7 7 0 0 0 12 2 Z M12 6.5 a2.5 2.5 0 1 0 0.01 0 Z",
    "cube": "M12 2 L21 7 V17 L12 22 L3 17 V7 Z M12 2 L12 12 M12 12 L21 7 M12 12 L3 7",
    "graph": "M4 20 H20 M6 18 V12 H9 V18 Z M11 18 V7 H14 V18 Z M16 18 V10 H19 V18 Z",
    "cross": "M9.5 3 H14.5 V9.5 H21 V14.5 H14.5 V21 H9.5 V14.5 H3 V9.5 H9.5 Z",
}

# --- Styles géométriques (paramétriques, rendus dans logo_render) --------------
GEOMETRICS = ("orbit", "hexagon", "triangle", "diamond", "arc", "waves", "bars", "venn", "chevron", "ring")

# --- Pairings typographiques (Google Fonts) ------------------------------------
# display = titre/wordmark, body = tagline. `import` = URL @import Google Fonts.
FONTS: dict[str, dict[str, str]] = {
    "poppins": {"display": "Poppins", "body": "Poppins", "weight": "700",
                "import": "https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap"},
    "inter": {"display": "Inter", "body": "Inter", "weight": "800",
              "import": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap"},
    "montserrat": {"display": "Montserrat", "body": "Montserrat", "weight": "700",
                   "import": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap"},
    "space": {"display": "Space Grotesk", "body": "Space Grotesk", "weight": "700",
              "import": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap"},
    "sora": {"display": "Sora", "body": "Sora", "weight": "700",
             "import": "https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&display=swap"},
    "playfair": {"display": "Playfair Display", "body": "Inter", "weight": "700",
                 "import": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500&display=swap"},
    "fraunces": {"display": "Fraunces", "body": "Inter", "weight": "600",
                 "import": "https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=Inter:wght@400;500&display=swap"},
    "dmsans": {"display": "DM Sans", "body": "DM Sans", "weight": "700",
               "import": "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap"},
}

# --- Palettes par défaut selon le secteur (fallback déterministe) --------------
# Chaque palette : primary (marque), secondary (variante), accent (touche), bg.
SECTOR_PALETTES: dict[str, dict[str, str]] = {
    "fintech": {"primary": "#1E40AF", "secondary": "#3B82F6", "accent": "#22D3EE", "bg": "#FFFFFF"},
    "edtech": {"primary": "#7C3AED", "secondary": "#A78BFA", "accent": "#FBBF24", "bg": "#FFFFFF"},
    "healthtech": {"primary": "#0D9488", "secondary": "#2DD4BF", "accent": "#F472B6", "bg": "#FFFFFF"},
    "agritech": {"primary": "#15803D", "secondary": "#4ADE80", "accent": "#FACC15", "bg": "#FFFFFF"},
    "greentech": {"primary": "#047857", "secondary": "#34D399", "accent": "#A3E635", "bg": "#FFFFFF"},
    "retail": {"primary": "#BE123C", "secondary": "#FB7185", "accent": "#FB923C", "bg": "#FFFFFF"},
    "mobility": {"primary": "#0F766E", "secondary": "#14B8A6", "accent": "#38BDF8", "bg": "#FFFFFF"},
    "saas": {"primary": "#4F46E5", "secondary": "#818CF8", "accent": "#22D3EE", "bg": "#FFFFFF"},
    "default": {"primary": "#4338CA", "secondary": "#6366F1", "accent": "#F59E0B", "bg": "#FFFFFF"},
}

# Association secteur → (icône, style géo, font) pour la variante déterministe.
SECTOR_HINTS: dict[str, dict[str, str]] = {
    "fintech": {"icon": "graph", "geometric": "bars", "font": "space"},
    "edtech": {"icon": "book", "geometric": "orbit", "font": "poppins"},
    "healthtech": {"icon": "heart", "geometric": "arc", "font": "inter"},
    "agritech": {"icon": "leaf", "geometric": "waves", "font": "dmsans"},
    "greentech": {"icon": "leaf", "geometric": "waves", "font": "sora"},
    "retail": {"icon": "cart", "geometric": "diamond", "font": "montserrat"},
    "mobility": {"icon": "pin", "geometric": "chevron", "font": "space"},
    "saas": {"icon": "cube", "geometric": "hexagon", "font": "inter"},
    "default": {"icon": "spark", "geometric": "orbit", "font": "poppins"},
}


def sector_key(sector: str | None) -> str:
    """Normalise un secteur libre vers une clé connue (sinon 'default')."""
    if not sector:
        return "default"
    s = sector.strip().lower()
    return s if s in SECTOR_PALETTES else "default"
