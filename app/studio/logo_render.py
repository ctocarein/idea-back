"""Composition déterministe d'un logo en SVG à partir d'un spec curé.

`spec` (choisi par l'IA dans le vocabulaire `vocab`, puis éditable par le porteur) :
  {
    name, tagline?, mark_type: icon|monogram|geometric,
    icon?, geometric?, monogram?, layout, container,
    palette: {primary, secondary, accent, bg}, font
  }
Le rendu est vectoriel, autonome, sans dépendance externe (fonts via @import Google).
"""

from __future__ import annotations

from html import escape

from app.studio.vocab import FONTS, ICONS


def _font(spec: dict) -> dict[str, str]:
    return FONTS.get(spec.get("font", "poppins"), FONTS["poppins"])


def _pal(spec: dict) -> dict[str, str]:
    p = dict(spec.get("palette") or {})
    return {
        "primary": p.get("primary", "#4338CA"),
        "secondary": p.get("secondary", "#6366F1"),
        "accent": p.get("accent", "#F59E0B"),
        "bg": p.get("bg", "#FFFFFF"),
    }


def _initials(spec: dict) -> str:
    mono = (spec.get("monogram") or "").strip()
    if mono:
        return mono[:2].upper()
    words = (spec.get("name") or "").split()
    if len(words) >= 2:
        return (words[0][:1] + words[1][:1]).upper()
    name = spec.get("name") or "A"
    return name[:2].upper()


# --- Marques géométriques paramétriques (box locale 0..100) --------------------
def _geometric(style: str, pri: str, sec: str, acc: str, bg: str) -> str:
    if style == "orbit":
        return (
            f'<circle cx="50" cy="50" r="38" fill="none" stroke="{pri}" stroke-width="9"/>'
            f'<circle cx="77" cy="23" r="10" fill="{acc}"/>'
            f'<circle cx="50" cy="50" r="9" fill="{pri}"/>'
        )
    if style == "ring":
        return f'<circle cx="50" cy="50" r="36" fill="none" stroke="{pri}" stroke-width="14"/>'
    if style == "hexagon":
        return f'<polygon points="50,6 88,28 88,72 50,94 12,72 12,28" fill="{pri}"/>'
    if style == "triangle":
        return (
            f'<polygon points="50,8 92,86 8,86" fill="{pri}"/>'
            f'<polygon points="50,40 72,82 28,82" fill="{acc}"/>'
        )
    if style == "diamond":
        return (
            f'<polygon points="50,6 94,50 50,94 6,50" fill="{pri}"/>'
            f'<polygon points="50,32 68,50 50,68 32,50" fill="{bg}"/>'
        )
    if style == "arc":
        return (
            f'<circle cx="50" cy="50" r="40" fill="{pri}"/>'
            f'<circle cx="66" cy="42" r="34" fill="{bg}"/>'
        )
    if style == "waves":
        return (
            f'<path d="M8 42 Q29 24 50 42 T92 42" fill="none" stroke="{pri}" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M8 60 Q29 42 50 60 T92 60" fill="none" stroke="{sec}" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M8 78 Q29 60 50 78 T92 78" fill="none" stroke="{acc}" stroke-width="9" stroke-linecap="round"/>'
        )
    if style == "bars":
        return (
            f'<rect x="12" y="60" width="16" height="30" rx="3" fill="{pri}"/>'
            f'<rect x="34" y="44" width="16" height="46" rx="3" fill="{pri}"/>'
            f'<rect x="56" y="30" width="16" height="60" rx="3" fill="{sec}"/>'
            f'<rect x="78" y="14" width="16" height="76" rx="3" fill="{acc}"/>'
        )
    if style == "venn":
        return (
            f'<circle cx="38" cy="50" r="30" fill="{pri}" fill-opacity="0.85"/>'
            f'<circle cx="62" cy="50" r="30" fill="{acc}" fill-opacity="0.85"/>'
        )
    if style == "chevron":
        return (
            f'<path d="M20 26 L50 52 L80 26" fill="none" stroke="{pri}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>'  # noqa: E501
            f'<path d="M20 52 L50 78 L80 52" fill="none" stroke="{acc}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>'  # noqa: E501
        )
    # défaut : orbit
    return _geometric("orbit", pri, sec, acc, bg)


def _mark(spec: dict, box: float) -> str:
    """Markup de la marque (icône / monogramme / géométrique) dans une box carrée."""
    pal = _pal(spec)
    container = spec.get("container", "none")
    mark_type = spec.get("mark_type", "geometric")
    on_container = container != "none"
    ink = "#FFFFFF" if on_container else pal["primary"]

    parts: list[str] = []

    # Fond (conteneur) derrière la marque.
    if on_container:
        if container == "circle":
            parts.append(f'<circle cx="{box/2}" cy="{box/2}" r="{box/2}" fill="{pal["primary"]}"/>')
        elif container == "rounded":
            parts.append(f'<rect x="0" y="0" width="{box}" height="{box}" rx="{box*0.24}" fill="{pal["primary"]}"/>')
        else:  # square
            parts.append(f'<rect x="0" y="0" width="{box}" height="{box}" fill="{pal["primary"]}"/>')

    if mark_type == "icon":
        path = ICONS.get(spec.get("icon", "spark"), ICONS["spark"])
        # Icône dans une viewBox 24 ; on la centre sur ~64% de la box.
        s = box / 24 * 0.62
        off = (box - 24 * s) / 2
        fill = ink if on_container else pal["primary"]
        # stroke même couleur : rend visibles les détails en traits (nervures, grilles)
        # sans épaissir les formes déjà pleines.
        parts.append(
            f'<g transform="translate({off},{off}) scale({s})">'
            f'<path d="{path}" fill="{fill}" stroke="{fill}" stroke-width="1.2" '
            f'stroke-linejoin="round" stroke-linecap="round"/></g>'
        )
    elif mark_type == "monogram":
        f = _font(spec)
        fill = ink if on_container else pal["primary"]
        parts.append(
            f'<text x="{box/2}" y="{box/2}" text-anchor="middle" dominant-baseline="central" '
            f'font-family="{escape(f["display"])}, sans-serif" font-weight="{f["weight"]}" '
            f'font-size="{box*0.52}" fill="{fill}">{escape(_initials(spec))}</text>'
        )
    else:  # geometric
        if on_container:
            # Sur conteneur : marque en blanc/accent, réduite dans la box.
            inner = _geometric(spec.get("geometric", "orbit"), "#FFFFFF", pal["secondary"], pal["accent"], pal["primary"])  # noqa: E501
        else:
            inner = _geometric(spec.get("geometric", "orbit"), pal["primary"], pal["secondary"], pal["accent"], pal["bg"])  # noqa: E501
        s = box / 100 * (0.72 if on_container else 1.0)
        off = (box - 100 * s) / 2
        parts.append(f'<g transform="translate({off},{off}) scale({s})">{inner}</g>')

    return "".join(parts)


_TAGLINE_SCALE = {"s": 0.24, "m": 0.30, "l": 0.38}


def _name_parts(spec: dict) -> list[dict] | None:
    parts = spec.get("name_parts")
    if isinstance(parts, list) and any(isinstance(p, dict) and p.get("text") for p in parts):
        return [p for p in parts if isinstance(p, dict) and p.get("text")]
    return None


def _wordmark_text(spec: dict) -> str:
    """Texte effectif du wordmark (concaténé si multicolore)."""
    parts = _name_parts(spec)
    if parts:
        return "".join(str(p.get("text", "")) for p in parts)
    return spec.get("name") or ""


def _tagline_font(spec: dict) -> dict[str, str]:
    tf = spec.get("tagline_font")
    return FONTS.get(tf, _font(spec)) if tf else _font(spec)


def _wordmark(spec: dict, x: float, y: float, anchor: str, size: float) -> str:
    f = _font(spec)
    pal = _pal(spec)
    name_color = spec.get("name_color") or pal["primary"]

    parts = _name_parts(spec)
    if parts:
        # Wordmark multicolore : un tspan par segment (couleur propre).
        content = "".join(
            f'<tspan fill="{p.get("color") or name_color}">{escape(str(p.get("text", "")))}</tspan>'
            for p in parts
        )
    else:
        content = escape(spec.get("name") or "")

    out = [
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="{escape(f["display"])}, sans-serif" font-weight="{f["weight"]}" '
        f'font-size="{size}" fill="{name_color}" letter-spacing="-0.5">{content}</text>'
    ]

    tagline = (spec.get("tagline") or "").strip()
    if tagline:
        tf = _tagline_font(spec)
        tscale = _TAGLINE_SCALE.get(spec.get("tagline_size", "m"), 0.30)
        tcolor = spec.get("tagline_color") or pal["secondary"]
        out.append(
            f'<text x="{x}" y="{y + size*0.62}" text-anchor="{anchor}" '
            f'font-family="{escape(tf["body"])}, sans-serif" font-weight="500" '
            f'font-size="{size*tscale}" fill="{tcolor}" letter-spacing="0.5">{escape(tagline)}</text>'
        )
    return "".join(out)


def _text_width(text: str, size: float) -> float:
    return max(1, len(text)) * size * 0.60


def _tagline_width(spec: dict, size: float) -> float:
    tagline = (spec.get("tagline") or "").strip()
    if not tagline:
        return 0.0
    tscale = _TAGLINE_SCALE.get(spec.get("tagline_size", "m"), 0.30)
    return _text_width(tagline, size * tscale)


def _imports(spec: dict) -> str:
    """@import de la (des) police(s) : wordmark + slogan si différente."""
    urls = {_font(spec)["import"], _tagline_font(spec)["import"]}
    return "".join(f'@import url("{u}");' for u in urls)


def render_logo_svg(spec: dict, *, standalone: bool = True, background: bool = True) -> str:
    """Compose le logo complet en SVG (chaîne autonome).

    background=False : fond transparent (utile en filigrane sur un fond quelconque).
    """
    pal = _pal(spec)
    layout = spec.get("layout", "icon-left")
    name = _wordmark_text(spec)
    tagline = (spec.get("tagline") or "").strip()
    P = 14.0  # padding

    style = f"<style>{_imports(spec)}</style>" if standalone else ""

    if layout == "wordmark-only":
        size = 60.0
        tw = max(_text_width(name, size), _tagline_width(spec, size))
        w = tw + 2 * P
        h = P + size + (size * 0.7 if tagline else 0) + P
        body = _wordmark(spec, P, P + size, "start", size)

    elif layout == "mark-only":
        M = 120.0
        w = h = M + 2 * P
        body = f'<g transform="translate({P},{P})">{_mark(spec, M)}</g>'

    elif layout == "icon-top":
        M = 108.0
        size = 44.0
        tw = max(_text_width(name, size), _tagline_width(spec, size))
        w = max(M, tw) + 2 * P
        h = P + M + 22 + size + (size * 0.7 if tagline else 0) + P
        mark = f'<g transform="translate({(w - M)/2},{P})">{_mark(spec, M)}</g>'
        text = _wordmark(spec, w / 2, P + M + 22 + size * 0.82, "middle", size)
        body = mark + text

    else:  # icon-left (défaut)
        M = 100.0
        size = 52.0
        tw = max(_text_width(name, size), _tagline_width(spec, size))
        text_x = P + M + 24
        w = text_x + tw + P
        h = 2 * P + M
        cy = P + M / 2
        mark = f'<g transform="translate({P},{P})">{_mark(spec, M)}</g>'
        # baseline verticalement centrée (décalée vers le haut si tagline).
        base_y = cy + size * 0.34 - (size * 0.22 if tagline else 0)
        text = _wordmark(spec, text_x, base_y, "start", size)
        body = mark + text

    bg_rect = f'<rect width="{w:.0f}" height="{h:.0f}" fill="{pal["bg"]}"/>' if background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" '
        f'width="{w:.0f}" height="{h:.0f}" role="img" aria-label="{escape(name)} logo">'
        f'{style}{bg_rect}{body}</svg>'
    )
