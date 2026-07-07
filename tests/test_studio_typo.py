"""Mode typographique du Studio : le picto habite le mot (déterministe, sans réseau)."""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest

from app.studio.logo_render import render_logo_svg
from app.studio.metaphors import METAPHORS, keyword_to_metaphor, resolve_metaphor
from app.studio.typo_render import render_typographic


def _valid_svg(svg: str) -> None:
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    minidom.parseString(svg)  # lève si le XML est malformé


def test_dispatch_typographic_from_render_logo_svg():
    spec = {"mode": "typographic", "word": "hungry", "transform": "letter-inhabit",
            "target_index": 1, "metaphor": "spoon"}
    svg = render_logo_svg(spec)
    _valid_svg(svg)
    assert "hungry" in svg


def test_non_typographic_spec_unchanged_path():
    # Un spec classique (sans mode) ne passe PAS par le renderer typo.
    spec = {"name": "Acme", "mark_type": "geometric", "geometric": "orbit",
            "layout": "icon-left", "palette": {"primary": "#123456"}}
    svg = render_logo_svg(spec)
    _valid_svg(svg)
    assert "Acme" in svg


@pytest.mark.parametrize("transform", ["letter-swap", "letter-inhabit", "letter-attach", "none"])
def test_all_transforms_render_valid(transform):
    spec = {"mode": "typographic", "word": "PENCIL", "transform": transform,
            "target_index": 5, "metaphor": "pencil", "palette": {"ink": "#141B34"}}
    _valid_svg(render_typographic(spec))


def test_letter_swap_places_metaphor_path():
    spec = {"mode": "typographic", "word": "PENCIL", "transform": "letter-swap",
            "target_index": 5, "metaphor": "pencil"}
    svg = render_typographic(spec)
    # le path exact de la métaphore « pencil » doit être présent, et la lettre retirée.
    assert METAPHORS["pencil"] in svg
    # préfixe rendu, pas de « L » final dans un <text> (il est devenu icône)
    assert ">PENCI<" in svg


def test_nested_accent_renders_second_icon():
    spec = {"mode": "typographic", "word": "hungry", "transform": "letter-swap",
            "target_index": 1, "metaphor": "spoon",
            "nested": {"metaphor": "drop", "color": "#E8912E"}}
    svg = render_typographic(spec)
    assert "#E8912E" in svg
    assert METAPHORS["drop"] in svg


def test_out_of_range_index_falls_back_to_plain_wordmark():
    for bad in (-1, 99, "x", None):
        spec = {"mode": "typographic", "word": "Sun", "transform": "letter-swap",
                "target_index": bad, "metaphor": "sun"}
        svg = render_typographic(spec)
        _valid_svg(svg)
        assert ">Sun<" in svg  # mot entier, aucune lettre retirée


def test_empty_word_is_safe():
    _valid_svg(render_typographic({"mode": "typographic", "word": "   "}))


def test_case_transform_applies():
    up = render_typographic({"mode": "typographic", "word": "graine", "case": "upper"})
    assert ">GRAINE<" in up
    low = render_typographic({"mode": "typographic", "word": "GRAINE", "case": "lower"})
    assert ">graine<" in low


def test_unknown_metaphor_falls_back():
    spec = {"mode": "typographic", "word": "Acme", "transform": "letter-swap",
            "target_index": 0, "metaphor": "does-not-exist"}
    svg = render_typographic(spec)
    _valid_svg(svg)  # résolu vers un défaut, pas de crash


@pytest.mark.parametrize("name", list(METAPHORS))
def test_every_metaphor_renders(name):
    spec = {"mode": "typographic", "word": "TESTOR", "transform": "letter-swap",
            "target_index": 0, "metaphor": name}
    _valid_svg(render_typographic(spec))


def test_keyword_routing():
    assert keyword_to_metaphor("plateforme d'écriture") == "feather"
    assert keyword_to_metaphor("appli agri pour la pousse") == "sprout"
    assert keyword_to_metaphor(None) == "spark"
    assert resolve_metaphor("book") == "book"
    assert resolve_metaphor(None, fallback_text="cuisine du monde") == "spoon"
