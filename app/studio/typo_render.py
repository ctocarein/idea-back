"""Rendu du mode `typographic` — le picto HABITE le mot (letter-swap / inhabit / attach).

Le sens du nom pilote la transformation d'UNE lettre : « hungry » → le « u » devient une
cuillère ; « PENCIL » → le « L » devient un crayon. L'IA choisit `{transform, target_index,
metaphor}` (l'hallucination) ; ici on compose le SVG de façon déterministe.

Positionnement : on DÉCOUPE le mot à la lettre cible (préfixe | créneau-icône | suffixe) et
on estime la largeur du préfixe via une table d'avances (pas de moteur de fonte côté serveur).
Une seule couture approximée → rendu propre et lisible. Fontes réelles via @import Google.
"""

from __future__ import annotations

from html import escape

from app.studio.metaphors import METAPHORS, resolve_metaphor
from app.studio.vocab import FONTS

# Avance par caractère (fraction de l'em) — gras géométrique approximé. Sert UNIQUEMENT
# à estimer les largeurs pour la découpe ; le rendu final utilise la vraie fonte.
_ADV: dict[str, float] = {
    "A": .70, "B": .68, "C": .72, "D": .74, "E": .60, "F": .58, "G": .76, "H": .76,
    "I": .30, "J": .44, "K": .68, "L": .56, "M": .92, "N": .76, "O": .80, "P": .66,
    "Q": .80, "R": .70, "S": .64, "T": .60, "U": .74, "V": .70, "W": .96, "X": .68,
    "Y": .66, "Z": .64,
    "a": .58, "b": .60, "c": .54, "d": .60, "e": .58, "f": .36, "g": .60, "h": .60,
    "i": .26, "j": .28, "k": .54, "l": .26, "m": .90, "n": .60, "o": .60, "p": .60,
    "q": .60, "r": .40, "s": .52, "t": .38, "u": .60, "v": .54, "w": .82, "x": .54,
    "y": .54, "z": .52, " ": .34,
}


def _adv(ch: str, fs: float) -> float:
    return _ADV.get(ch, _ADV.get(ch.upper(), 0.66)) * fs


def _width(text: str, fs: float) -> float:
    return sum(_adv(c, fs) for c in text)


def _font(spec: dict) -> dict[str, str]:
    return FONTS.get(spec.get("font", "montserrat"), FONTS["montserrat"])


def _pal(spec: dict) -> dict[str, str]:
    p = dict(spec.get("palette") or {})
    ink = p.get("ink") or p.get("primary") or "#1C1633"
    return {
        "ink": ink,
        "accent": p.get("accent") or "#FF7A4D",
        "bg": p.get("bg", "#FFFFFF"),
    }


def _icon(name: str, cx: float, top: float, size: float, color: str) -> str:
    s = size / 100.0
    ox = cx - size / 2
    return (
        f'<g transform="translate({ox:.1f},{top:.1f}) scale({s:.3f})" '
        f'fill="{color}" stroke="none">{METAPHORS.get(name, METAPHORS["spark"])}</g>'
    )


def render_typographic(spec: dict, *, standalone: bool = True, background: bool = True) -> str:
    """Compose un logo typographique complet (chaîne SVG autonome)."""
    word = (spec.get("word") or spec.get("name") or "Logo").strip() or "Logo"
    case = spec.get("case")
    if case == "upper":
        word = word.upper()
    elif case == "lower":
        word = word.lower()

    pal = _pal(spec)
    f = _font(spec)
    fs = 120.0
    cap = 0.72 * fs
    pad = 22.0

    transform = spec.get("transform", "letter-swap")
    metaphor = resolve_metaphor(spec.get("metaphor"), fallback_text=word)
    ti = spec.get("target_index", -1)
    if not isinstance(ti, int) or not (0 <= ti < len(word)):
        transform = "none"

    nested = spec.get("nested") if isinstance(spec.get("nested"), dict) else None
    top_pad = pad + (0.60 * cap if transform == "letter-attach" else 0.0)
    baseline = top_pad + cap
    parts: list[str] = []

    if transform == "letter-swap":
        prefix, suffix = word[:ti], word[ti + 1:]
        wp = _width(prefix, fs)
        slot = max(_adv(word[ti], fs), 0.72 * fs)
        icon_cx = pad + wp + slot / 2
        parts.append(_text(prefix, pad, baseline, fs, f, pal["ink"]))
        parts.append(_icon(metaphor, icon_cx, baseline - cap, cap, pal["ink"]))
        if nested:
            parts.append(_icon(resolve_metaphor(nested.get("metaphor"), fallback_text=word),
                               icon_cx, baseline - cap * 0.66, cap * 0.34,
                               nested.get("color") or pal["accent"]))
        parts.append(_text(suffix, pad + wp + slot, baseline, fs, f, pal["ink"]))
        total = wp + slot + _width(suffix, fs)
    else:
        # inhabit / attach / none : le mot est rendu entier (kerning naturel), icône posée.
        parts.append(_text(word, pad, baseline, fs, f, pal["ink"]))
        total = _width(word, fs)
        if transform in ("letter-inhabit", "letter-attach"):
            cx = pad + _width(word[:ti], fs) + _adv(word[ti], fs) / 2
            if transform == "letter-attach":
                parts.append(_icon(metaphor, cx, pad, 0.62 * cap, pal["ink"]))
            else:  # inhabit : petite icône logée dans la lettre
                parts.append(_icon(metaphor, cx, baseline - cap * 0.72, 0.48 * cap, pal["accent"]))

    w = total + 2 * pad
    h = baseline + pad
    imp = f["import"].replace("&", "&amp;")  # URL valide en XML (le parseur SVG décode)
    style = f'<style>@import url("{imp}");</style>' if standalone else ""
    bg = f'<rect width="{w:.0f}" height="{h:.0f}" fill="{pal["bg"]}"/>' if background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" '
        f'width="{w:.0f}" height="{h:.0f}" role="img" aria-label="{escape(word)} logo">'
        f'{style}{bg}{"".join(parts)}</svg>'
    )


def _text(s: str, x: float, y: float, fs: float, f: dict, fill: str) -> str:
    if not s:
        return ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="start" '
        f'font-family="{escape(f["display"])}, sans-serif" font-weight="{f["weight"]}" '
        f'font-size="{fs:.0f}" fill="{fill}" letter-spacing="-1">{escape(s)}</text>'
    )
