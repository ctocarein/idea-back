"""Stratégie des 4 variantes du Studio : un angle imposé par slot (déterministe)."""

from __future__ import annotations

import json
import xml.dom.minidom as minidom

from app.studio.logo_gen import ANGLES, coerce_spec, default_variations, parse_variations
from app.studio.logo_render import render_logo_svg


def _angles(specs):
    return [s.get("angle") for s in specs]


def test_default_variations_cover_the_four_angles_in_order():
    specs = default_variations("Graine", "agritech")
    assert _angles(specs) == list(ANGLES)
    # chaque défaut porte son mode canonique
    assert specs[0]["mode"] == "typographic"
    assert specs[3]["mode"] == "wordmark"


def test_default_variations_all_render_valid_svg():
    for s in default_variations("Ideaxion", "saas"):
        svg = render_logo_svg(s)
        assert svg.startswith("<svg")
        minidom.parseString(svg)


def test_parse_empty_falls_back_to_four_angles():
    specs = parse_variations("pas du json", name="Acme", sector=None)
    assert _angles(specs) == list(ANGLES)


def test_parse_partial_fills_missing_angles():
    raw = json.dumps(
        {
            "variations": [
                {"angle": "wordmark", "mode": "wordmark", "name": "Acme", "layout": "wordmark-only"},
                {"angle": "concept", "mode": "combination", "mark_type": "icon", "icon": "leaf"},
            ]
        }
    )
    specs = parse_variations(raw, name="Acme", sector="agritech")
    assert _angles(specs) == list(ANGLES)  # toujours 4, dans l'ordre
    # les 2 fournis sont conservés, les 2 autres comblés
    assert specs[ANGLES.index("concept")]["icon"] == "leaf"


def test_parse_assigns_angle_when_missing():
    raw = json.dumps(
        {
            "variations": [
                {"mode": "combination", "mark_type": "icon", "icon": "spark"},
                {"mode": "monogram", "mark_type": "monogram", "monogram": "AC"},
            ]
        }
    )
    specs = parse_variations(raw, name="Acme", sector=None)
    assert _angles(specs) == list(ANGLES)
    assert len(specs) == 4


def test_coerce_typographic_fields_validated():
    raw = {
        "angle": "name-literal",
        "mode": "typographic",
        "word": "hungry",
        "transform": "letter-inhabit",
        "target_index": 1,
        "metaphor": "spoon",
        "nested": {"metaphor": "drop", "color": "#E8912E"},
    }
    spec = coerce_spec(raw, name="hungry", sector="food")
    assert spec["mode"] == "typographic"
    assert spec["transform"] == "letter-inhabit"
    assert spec["target_index"] == 1
    assert spec["metaphor"] == "spoon"
    assert spec["nested"] == {"metaphor": "drop", "color": "#E8912E"}


def test_coerce_typographic_bad_values_recover():
    raw = {
        "angle": "name-literal",
        "mode": "typographic",
        "word": "Sun",
        "transform": "wat",
        "target_index": 99,
        "metaphor": "nope",
    }
    spec = coerce_spec(raw, name="Sun", sector=None)
    assert spec["transform"] == "letter-swap"  # défaut
    assert 0 <= spec["target_index"] < len("Sun")  # recalé
    assert spec["metaphor"] in ("sun", "spark")  # routé/défaut


def test_coerce_infers_mode_from_angle():
    spec = coerce_spec({"angle": "letter-fantasy"}, name="Acme", sector=None)
    assert spec["mode"] == "monogram"


def test_classic_spec_without_mode_still_valid():
    spec = coerce_spec({"mark_type": "geometric", "geometric": "orbit"}, name="Acme", sector=None)
    assert spec["mode"] is None
    minidom.parseString(render_logo_svg(spec))
