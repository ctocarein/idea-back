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


def build_logo_prompt(
    *, name: str, sector: str | None, archetype: str | None, description: str | None, lang: str = "fr"
) -> str:
    icons = ", ".join(sorted(ICONS))
    geos = ", ".join(GEOMETRICS)
    fonts = ", ".join(sorted(FONTS))
    desc = (description or "").strip()[:600]
    return (
        "FORMAT=logo\n"
        + lang_directive(lang) + " (le slogan/tagline suit la langue ; les autres champs restent des clés)\n"
        "Tu es directeur artistique de marque. Conçois 4 concepts de LOGO distincts pour une startup. "
        "Tu ne dessines pas : tu CHOISIS dans des listes fermées et tu proposes une palette.\n\n"
        f"Projet : {name}\n"
        f"Secteur : {sector or 'non précisé'}\n"
        f"Archétype : {archetype or 'non précisé'}\n"
        f"Description : {desc or 'non précisée'}\n\n"
        "ANALYSE d'abord l'idée : que fait ce projet, pour qui, quelle émotion doit porter la marque ? "
        "Le logo doit RACONTER CE projet précis — un projet agricole n'évoque pas la même chose qu'un "
        "projet santé ou fintech. Choisis marque, couleurs et typo qui collent au thème et à l'ambiance : "
        "ex. agri/vert → tons terre/nature, formes organiques (leaf, waves, drop) ; santé → tons apaisants, "
        "formes rassurantes (heart, shield, cross) ; fintech → tons confiance, formes nettes (bars, graph, "
        "hexagon) ; edtech → tons chaleureux, formes ludiques. Évite le générique.\n\n"
        "Contraintes STRICTES (n'invente aucune valeur hors listes) :\n"
        f"- mark_type ∈ [{', '.join(MARK_TYPES)}]\n"
        f"- icon ∈ [{icons}] (si mark_type=icon)\n"
        f"- geometric ∈ [{geos}] (si mark_type=geometric)\n"
        "- monogram = 1 à 2 lettres (si mark_type=monogram)\n"
        f"- layout ∈ [{', '.join(LAYOUTS)}]\n"
        f"- container ∈ [{', '.join(CONTAINERS)}]\n"
        f"- font ∈ [{fonts}]\n"
        "- palette = 4 couleurs hex #RRGGBB : primary (marque), secondary, accent, bg (souvent #FFFFFF)\n"
        "- tagline : courte (3-5 mots) ou vide\n\n"
        "Varie les concepts (au moins 2 mark_type différents, des palettes cohérentes avec le secteur). "
        "Réponds UNIQUEMENT en JSON : "
        '{"variations":[{"name":"...","tagline":"...","mark_type":"...","icon":"...","geometric":"...",'
        '"monogram":"...","layout":"...","container":"...","font":"...",'
        '"palette":{"primary":"#...","secondary":"#...","accent":"#...","bg":"#FFFFFF"}}]}'
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

    return {
        "name": name,
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


def default_variations(name: str, sector: str | None) -> list[dict[str, Any]]:
    """Lot déterministe de 4 concepts — toujours propre, sans IA."""
    key = sector_key(sector)
    hint = SECTOR_HINTS.get(key, SECTOR_HINTS["default"])
    pal = dict(SECTOR_PALETTES.get(key, SECTOR_PALETTES["default"]))
    return [
        {"name": name, "tagline": "", "mark_type": "geometric", "geometric": hint["geometric"],
         "icon": hint["icon"], "monogram": None, "layout": "icon-left", "container": "none",
         "font": hint["font"], "palette": pal},
        {"name": name, "tagline": "", "mark_type": "monogram", "geometric": hint["geometric"],
         "icon": hint["icon"], "monogram": None, "layout": "icon-left", "container": "rounded",
         "font": "space", "palette": pal},
        {"name": name, "tagline": "", "mark_type": "icon", "geometric": hint["geometric"],
         "icon": hint["icon"], "monogram": None, "layout": "icon-top", "container": "circle",
         "font": hint["font"], "palette": pal},
        {"name": name, "tagline": "", "mark_type": "geometric", "geometric": "hexagon",
         "icon": hint["icon"], "monogram": None, "layout": "mark-only", "container": "none",
         "font": "inter", "palette": pal},
    ]


def parse_variations(llm_text: Any, *, name: str, sector: str | None) -> list[dict[str, Any]]:
    """Parse la sortie IA en 4 specs valides ; fallback déterministe si insuffisant."""
    data = _extract_json(llm_text)
    out: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("variations"), list):
        for raw in data["variations"]:
            spec = coerce_spec(raw, name=name, sector=sector)
            if spec is not None:
                out.append(spec)
    if len(out) >= 2:
        # Complète jusqu'à 4 avec des défauts si l'IA en a rendu moins.
        if len(out) < 4:
            out += default_variations(name, sector)[len(out):]
        return out[:4]
    return default_variations(name, sector)
