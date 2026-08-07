"""Génération des variations de logo — IA contrainte + fallback déterministe.

Stratégie « best-effort, jamais de panne » :
1. On construit TOUJOURS un lot déterministe (depuis nom + secteur) qui rend bien.
2. On tente l'IA pour proposer 4 specs affinés, validés contre le vocabulaire curé.
3. Chaque champ invalide retombe sur un défaut → un spec IA partiel reste rendu.
Si l'IA échoue complètement, on sert le lot déterministe.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.llm.prompt import lang_directive
from app.studio.metaphors import METAPHORS, keyword_to_metaphor, resolve_metaphor
from app.studio.vocab import (
    CONTAINERS,
    FONTS,
    GEOMETRICS,
    ICONS,
    LAYOUTS,
    MARK_TYPES,
    SECTOR_HINTS,
    SECTOR_PALETTES,
    sector_key,
)

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# --- Stratégie des 4 variantes : un ANGLE imposé par slot (diversité garantie) --
# V1 le nom littéral · V2 l'idée/contexte · V3 jeu de lettres · V4 le mot en belle typo.
ANGLES = ("name-literal", "concept", "letter-fantasy", "wordmark")
# Mode de rendu d'une variante (le renderer dispatche dessus).
MODES = ("typographic", "combination", "monogram", "wordmark")
# Transforms du mode typographique (le picto habite une lettre).
TRANSFORMS = ("letter-swap", "letter-inhabit", "letter-attach", "none")
# Mode par défaut associé à chaque angle (si l'IA ne le précise pas).
_ANGLE_MODE = {
    "name-literal": "typographic",
    "concept": "combination",
    "letter-fantasy": "monogram",
    "wordmark": "wordmark",
}


def _default_target(word: str) -> int:
    """Lettre à transformer par défaut : 1re voyelle (contour rond, reste lisible)."""
    for i, c in enumerate(word):
        if c.lower() in "aeiouy":
            return i
    return 0


def build_logo_prompt(
    *, name: str, sector: str | None, archetype: str | None, description: str | None, lang: str = "fr"
) -> str:
    icons = ", ".join(sorted(ICONS))
    geos = ", ".join(GEOMETRICS)
    fonts = ", ".join(sorted(FONTS))
    metas = ", ".join(sorted(METAPHORS))
    desc = (description or "").strip()[:600]
    return (
        "FORMAT=logo\n"
        + lang_directive(lang)
        + " (le slogan/tagline suit la langue ; les autres champs restent des clés)\n"
        "Tu es directeur artistique de marque. Conçois EXACTEMENT 4 concepts de LOGO, UN PAR ANGLE imposé "
        "(pour garantir 4 pistes franchement différentes). Tu ne dessines pas : tu CHOISIS dans des listes "
        "fermées et tu proposes une palette.\n\n"
        f"Projet : {name}\n"
        f"Secteur : {sector or 'non précisé'}\n"
        f"Archétype : {archetype or 'non précisé'}\n"
        f"Description : {desc or 'non précisée'}\n\n"
        "ANALYSE d'abord l'idée : que fait ce projet, pour qui, quelle émotion ? Le logo doit RACONTER CE "
        "projet précis (agri→nature, santé→rassurant, fintech→confiance…). Évite le générique.\n\n"
        "LES 4 ANGLES (dans cet ordre, un concept chacun) :\n"
        "1) angle='name-literal', mode='typographic' : le SENS du NOM habite une lettre. Choisis "
        "target_index (la lettre, 0-based) + transform ∈ [letter-swap, letter-inhabit, letter-attach] + "
        f"metaphor ∈ [{metas}]. Ex. « hungry »→u=spoon, « lumen »→l=spark.\n"
        "2) angle='concept', mode='combination' : un EMBLÈME du contexte/secteur (mark_type=icon + "
        "layout=icon-top). L'icône reflète ce que FAIT le projet, pas le nom.\n"
        "3) angle='letter-fantasy', mode='monogram' : l'INITIALE stylisée (mark_type=monogram, "
        "container=rounded/circle).\n"
        "4) angle='wordmark', mode='wordmark' : le NOM en belle typo (layout=wordmark-only), sans picto ; "
        "tu peux colorer une lettre via name_parts.\n\n"
        "Contraintes STRICTES (n'invente aucune valeur hors listes) :\n"
        f"- mark_type ∈ [{', '.join(MARK_TYPES)}] · layout ∈ [{', '.join(LAYOUTS)}] · "
        f"container ∈ [{', '.join(CONTAINERS)}] · font ∈ [{fonts}]\n"
        f"- icon ∈ [{icons}] · geometric ∈ [{geos}] · metaphor ∈ [{metas}]\n"
        "- palette = 4 hex #RRGGBB : primary, secondary, accent, bg (souvent #FFFFFF). Palette COHÉRENTE "
        "entre les 4 (même marque).\n"
        "- tagline : courte (3-5 mots) ou vide\n\n"
        "Réponds UNIQUEMENT en JSON : "
        '{"variations":[{"angle":"name-literal","mode":"typographic","word":"...","transform":"...",'
        '"target_index":0,"metaphor":"...","name":"...","tagline":"...","font":"...",'
        '"palette":{"primary":"#...","secondary":"#...","accent":"#...","bg":"#FFFFFF"}},'
        '{"angle":"concept","mode":"combination","mark_type":"icon","icon":"...","layout":"icon-top",'
        '"name":"...","font":"...","palette":{...}},'
        '{"angle":"letter-fantasy","mode":"monogram","mark_type":"monogram","monogram":"...",'
        '"container":"rounded","name":"...","font":"...","palette":{...}},'
        '{"angle":"wordmark","mode":"wordmark","layout":"wordmark-only","name":"...","font":"...",'
        '"palette":{...}}]}'
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    if isinstance(text, dict):
        return text
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(r"(\{.*\})", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, TypeError):
        return None


def _pick(value: Any, allowed: tuple[str, ...] | dict, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def coerce_spec(raw: Any, *, name: str, sector: str | None) -> dict[str, Any] | None:
    """Valide un spec IA contre le vocabulaire ; retombe par champ sur un défaut sain."""
    if not isinstance(raw, dict):
        return None
    key = sector_key(sector)
    hint = SECTOR_HINTS.get(key, SECTOR_HINTS["default"])
    base_pal = SECTOR_PALETTES.get(key, SECTOR_PALETTES["default"])

    mark_type = _pick(raw.get("mark_type"), MARK_TYPES, "geometric")
    rp = raw.get("palette")
    raw_pal: dict = rp if isinstance(rp, dict) else {}
    palette = {
        k: (raw_pal.get(k) if _HEX.match(str(raw_pal.get(k, ""))) else base_pal[k])
        for k in ("primary", "secondary", "accent", "bg")
    }
    tagline = raw.get("tagline")
    tagline = tagline.strip()[:60] if isinstance(tagline, str) else ""

    angle = _pick(raw.get("angle"), ANGLES, "")
    mode = _pick(raw.get("mode"), MODES, _ANGLE_MODE.get(angle, ""))

    spec = {
        "name": name,
        "angle": angle or None,
        "mode": mode or None,
        "tagline": tagline,
        "mark_type": mark_type,
        "icon": _pick(raw.get("icon"), ICONS, hint["icon"]),
        "geometric": _pick(raw.get("geometric"), GEOMETRICS, hint["geometric"]),
        "monogram": (str(raw.get("monogram") or "")[:2].upper()) or None,
        "layout": _pick(raw.get("layout"), LAYOUTS, "icon-left"),
        "container": _pick(raw.get("container"), CONTAINERS, "none"),
        "font": _pick(raw.get("font"), FONTS, hint["font"]),
        "palette": palette,
        # Peaufinage manuel (édition) : wordmark multicolore + réglages du slogan.
        "name_color": raw.get("name_color") if _HEX.match(str(raw.get("name_color", ""))) else None,
        "name_parts": _coerce_name_parts(raw.get("name_parts")),
        "tagline_font": raw.get("tagline_font") if raw.get("tagline_font") in FONTS else None,
        "tagline_size": raw.get("tagline_size") if raw.get("tagline_size") in ("s", "m", "l") else "m",
        "tagline_color": raw.get("tagline_color") if _HEX.match(str(raw.get("tagline_color", ""))) else None,
    }

    # Mode typographique : le picto habite une lettre → champs dédiés validés.
    if mode == "typographic":
        word = (raw.get("word") or name or "Logo").strip() or "Logo"
        ti = raw.get("target_index")
        spec["word"] = word
        spec["transform"] = _pick(raw.get("transform"), TRANSFORMS, "letter-swap")
        spec["target_index"] = ti if isinstance(ti, int) and 0 <= ti < len(word) else _default_target(word)
        spec["metaphor"] = resolve_metaphor(raw.get("metaphor"), fallback_text=f"{name} {sector or ''}")
        spec["case"] = raw.get("case") if raw.get("case") in ("upper", "lower") else None
        nested = raw.get("nested")
        if isinstance(nested, dict) and nested.get("metaphor") in METAPHORS:
            ncol = nested.get("color")
            spec["nested"] = {
                "metaphor": nested["metaphor"],
                "color": ncol if _HEX.match(str(ncol or "")) else palette["accent"],
            }
    return spec


def _coerce_name_parts(parts: Any) -> list[dict[str, str]] | None:
    """Valide les segments colorés du wordmark : [{text, color}]. None si absent/vide."""
    if not isinstance(parts, list):
        return None
    out: list[dict[str, str]] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        text = str(p.get("text", ""))
        if not text:
            continue
        color = str(p.get("color") or "")
        out.append({"text": text[:40], "color": color if _HEX.match(color) else "#111827"})
    return out or None


def _default_for_angle(angle: str, name: str, sector: str | None) -> dict[str, Any]:
    """Une variante déterministe pour UN angle donné — toujours propre, sans IA."""
    key = sector_key(sector)
    hint = SECTOR_HINTS.get(key, SECTOR_HINTS["default"])
    pal = dict(SECTOR_PALETTES.get(key, SECTOR_PALETTES["default"]))
    base = {
        "name": name,
        "angle": angle,
        "mode": _ANGLE_MODE[angle],
        "tagline": "",
        "monogram": None,
        "font": hint["font"],
        "palette": pal,
    }
    if angle == "name-literal":  # le sens du nom habite une lettre
        word = (name.split() or ["Logo"])[0]
        return {
            **base,
            "word": word,
            "transform": "letter-swap",
            "target_index": _default_target(word),
            "metaphor": keyword_to_metaphor(f"{name} {sector or ''}"),
            "mark_type": "icon",
            "icon": hint["icon"],
            "geometric": hint["geometric"],
            "layout": "wordmark-only",
            "container": "none",
            "case": None,
        }
    if angle == "concept":  # emblème du contexte + wordmark
        return {
            **base,
            "mark_type": "icon",
            "icon": hint["icon"],
            "geometric": hint["geometric"],
            "layout": "icon-top",
            "container": "none",
        }
    if angle == "letter-fantasy":  # monogramme initiale
        return {
            **base,
            "mark_type": "monogram",
            "icon": hint["icon"],
            "geometric": hint["geometric"],
            "layout": "icon-top",
            "container": "rounded",
            "font": "space",
        }
    # wordmark : le nom en belle typo
    return {
        **base,
        "mark_type": "monogram",
        "icon": hint["icon"],
        "geometric": hint["geometric"],
        "layout": "wordmark-only",
        "container": "none",
    }


def default_variations(name: str, sector: str | None) -> list[dict[str, Any]]:
    """Lot déterministe de 4 concepts — un par angle imposé, toujours propre, sans IA."""
    return [_default_for_angle(a, name, sector) for a in ANGLES]


def parse_variations(llm_text: Any, *, name: str, sector: str | None) -> list[dict[str, Any]]:
    """Parse la sortie IA → 4 specs, UN PAR ANGLE. Chaque angle manquant retombe sur son défaut."""
    data = _extract_json(llm_text)
    by_angle: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict) and isinstance(data.get("variations"), list):
        for raw in data["variations"]:
            spec = coerce_spec(raw, name=name, sector=sector)
            if spec is None:
                continue
            angle = spec.get("angle")
            # Angle non fourni par l'IA → on comble le 1er slot d'angle encore vide.
            if angle not in ANGLES:
                angle = next((a for a in ANGLES if a not in by_angle), None)
                if angle is None:
                    continue
                spec["angle"] = angle
                spec["mode"] = spec.get("mode") or _ANGLE_MODE[angle]
            by_angle.setdefault(angle, spec)
    # Garantit exactement 4 variantes, une par angle, dans l'ordre canonique.
    return [by_angle.get(a) or _default_for_angle(a, name, sector) for a in ANGLES]
