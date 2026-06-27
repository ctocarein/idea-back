"""Rendu deck PDF → images de slides (présentation nette + vision)."""

from __future__ import annotations

from app.pitchsim.render import png_to_data_url, render_pdf_to_pngs

# PDF minimal valide (1 page) — pypdfium2/PDFium reconstruit l'xref si besoin.
_MIN_PDF = (
    b"%PDF-1.1\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_render_pdf_to_pngs_returns_a_png_per_page():
    pngs = render_pdf_to_pngs(_MIN_PDF)
    assert len(pngs) == 1
    assert pngs[0][:8] == _PNG_MAGIC


def test_render_is_bounded_by_max_pages():
    pngs = render_pdf_to_pngs(_MIN_PDF, max_pages=0)
    assert pngs == []


def test_png_to_data_url_shape():
    url = png_to_data_url(b"\x89PNGxxxx")
    assert url.startswith("data:image/png;base64,")
    assert len(url) > len("data:image/png;base64,")
