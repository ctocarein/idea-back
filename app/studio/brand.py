"""Kit de marque dérivé du logo (Studio, tranche 3).

Le logo choisi FIXE l'identité : sa palette + sa typo + la marque elle-même. On en
dérive un « brand kit » que le deck de pitch applique → cohérence logo ↔ pitch.
"""

from __future__ import annotations

from app.studio.logo_render import render_logo_svg
from app.studio.vocab import FONTS


def build_brand(spec: dict | None) -> dict | None:
    """Dérive le kit de marque d'un spec de logo. None si pas de logo."""
    if not spec:
        return None
    pal = spec.get("palette") or {}
    primary = pal.get("primary", "#4338CA")
    bg = pal.get("bg", "#FFFFFF")
    f = FONTS.get(spec.get("font", "poppins"), FONTS["poppins"])
    return {
        # Variables CSS du deck (le --accent porte la couleur dominante de la marque).
        "accent": primary,
        "ink": "#1C1633",
        "bg": bg,
        "muted": "#6B6580",
        "band": f"{primary}14",  # teinte 8% de la couleur de marque (fond de slide "stat")
        "display_font": f["display"],
        "body_font": f["body"],
        "font_import": f["import"],
        # Logo en filigrane (fond transparent) pour le pied des slides de contenu.
        "logo_svg": render_logo_svg(spec, standalone=False, background=False),
    }


def kit_view(spec: dict | None) -> dict:
    """Vue du kit pour l'UI (page « Kit de marque »)."""
    if not spec:
        return {"has_logo": False}
    pal = spec.get("palette") or {}
    f = FONTS.get(spec.get("font", "poppins"), FONTS["poppins"])
    return {
        "has_logo": True,
        "palette": {
            "primary": pal.get("primary", "#4338CA"),
            "secondary": pal.get("secondary", "#6366F1"),
            "accent": pal.get("accent", "#F59E0B"),
            "bg": pal.get("bg", "#FFFFFF"),
        },
        "display_font": f["display"],
        "body_font": f["body"],
        "font_import": f["import"],
        "logo_svg": render_logo_svg(spec, standalone=True),
    }
