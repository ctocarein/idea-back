"""« Raconte, on structure » — extraction synchrone du récit libre en 12 dimensions.

Le porteur raconte son idée ; on repère, pour chaque dimension de la grille, si l'info est déjà
là (preuve) ou s'il faut la demander (question courte). On n'invente rien : pas d'info = manque.
Service isolé (un seul appel LLM, request-time) — ne touche pas au pipeline de scoring asynchrone.

Supporte deux entrées :
- `extract(idea, project_name)` : texte libre saisi par le porteur
- `extract_file(data, content_type, filename)` : PDF ou DOCX → texte → même pipeline
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

from app.diagnostics.schemas import ExtractedDimension, IdeaExtractOut
from app.llm.base import LLMProvider
from app.llm.prompt import build_extraction_prompt
from app.scoring.constants import AXES

_MAX_TEXT = 5000  # limite identique à IdeaExtractIn.idea
_MAX_PAGES = 15  # PDF : on ne lit pas au-delà pour économiser la mémoire


def _extract_pdf_text(data: bytes) -> str:
    try:
        import pypdfium2 as pdfium  # déjà dans les extras pitch
    except ImportError:
        return ""
    try:
        doc = pdfium.PdfDocument(data)
    except Exception:
        return ""
    parts: list[str] = []
    for i in range(min(len(doc), _MAX_PAGES)):
        page = doc[i]
        tp = page.get_textpage()
        parts.append(tp.get_text_range())
        tp.close()
        page.close()
    doc.close()
    return "\n".join(parts)


def _extract_docx_text(data: bytes) -> str:
    # DOCX = ZIP + word/document.xml. Zéro dépendance supplémentaire.
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            with zf.open("word/document.xml") as f:
                tree = ET.parse(f)
    except Exception:
        return ""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs: list[str] = []
    for para in tree.iter(f"{{{ns}}}p"):
        texts = [t.text for t in para.iter(f"{{{ns}}}t") if t.text]
        if texts:
            paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


def extract_text_from_file(data: bytes, content_type: str, filename: str) -> str:
    """Extrait le texte d'un fichier PDF ou DOCX. Retourne "" si illisible."""
    ct = content_type.lower()
    fn = filename.lower()
    if "pdf" in ct or fn.endswith(".pdf"):
        return _extract_pdf_text(data)
    if "docx" in ct or "wordprocessingml" in ct or fn.endswith(".docx"):
        return _extract_docx_text(data)
    return ""


class IdeaExtractionService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def extract(
        self, idea: str, project_name: str | None, lang: str = "fr", currency: str = "XOF"
    ) -> IdeaExtractOut:
        prompt = build_extraction_prompt(idea=idea, axes=AXES, project_name=project_name, lang=lang, currency=currency)
        # 12 dimensions × (evidence + question + suggestion) : le défaut 1024 tronque le JSON
        # (→ LLMParseError). On relève le plafond pour cette sortie longue spécifiquement.
        raw = await self.provider.analyze_json(prompt, max_tokens=3072)
        by_key = raw.get("dimensions")
        by_key = by_key if isinstance(by_key, dict) else {}

        dims: list[ExtractedDimension] = []
        for axis in AXES:
            d = by_key.get(axis["key"]) or {}
            captured = bool(d.get("captured"))
            dims.append(
                ExtractedDimension(
                    key=axis["key"],
                    label=axis["label"],
                    captured=captured,
                    evidence=(str(d.get("evidence") or "") if captured else ""),
                    question=("" if captured else str(d.get("question") or "")),
                    suggestion=("" if captured else str(d.get("suggestion") or "")),
                )
            )

        name = raw.get("project_name") or project_name
        if isinstance(name, str):
            name = name.strip() or None
        else:
            name = None

        return IdeaExtractOut(
            project_name=name,
            captured_count=sum(1 for d in dims if d.captured),
            total=len(dims),
            dimensions=dims,
            gaps=[d for d in dims if not d.captured],
            source_text=idea[:_MAX_TEXT],
        )
