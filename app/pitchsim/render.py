"""Rendu d'un deck PDF en images de slides (présentation nette + vision du comité).

pypdfium2 = moteur PDFium embarqué (binaire), zéro dépendance système → portable en Docker.
Le PNG par page sert à (a) l'affichage du salon, (b) la vision multimodale (Pixtral).
Imports paresseux : pypdfium2/Pillow ne sont chargés que si on rend réellement.
"""

from __future__ import annotations

import base64
from io import BytesIO

MAX_RENDER_PAGES = 10  # un deck principal reste court


def render_pdf_to_pngs(
    data: bytes, *, max_pages: int = MAX_RENDER_PAGES, scale: float = 1.5
) -> list[bytes]:
    """PDF (octets) → liste de PNG (un par page, bornée à `max_pages`)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    pngs: list[bytes] = []
    try:
        for i in range(min(len(doc), max_pages)):
            bitmap = doc[i].render(scale=scale)
            buf = BytesIO()
            bitmap.to_pil().save(buf, format="PNG")
            pngs.append(buf.getvalue())
    finally:
        doc.close()
    return pngs


def png_to_data_url(png: bytes) -> str:
    """PNG → data URL base64 (format attendu par les API vision compatibles OpenAI)."""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
