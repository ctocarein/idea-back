"""Fiche de besoin — rendu HTML/CSS → PDF (charte « Aube »).

`render_fiche_html` est PUR (stdlib) : testable hors-ligne. `render_fiche_pdf`
convertit via WeasyPrint (extra `pdf`) ; son absence remonte une ImportError
que l'appelant dégrade en 503.
"""

from __future__ import annotations

from html import escape

from app.academy.models import NeedFiche

_INK = "#1C1633"
_CORAL = "#FF7A4D"
_MUTED = "#6B6580"

_TYPE_LABELS = {
    "dev": "Développeur",
    "expert": "Expert",
    "cofondateur": "Cofondateur",
    "partenaire": "Partenaire",
    "outil": "Outil",
    "financement": "Financement",
    "formation": "Formation",
    "autre": "Autre",
}

_PRIORITY_LABELS = {"high": "Priorité haute", "medium": "Priorité moyenne", "low": "Priorité basse"}


def _field(label: str, value: str) -> str:
    if not value:
        return ""
    return f'<div class="field"><span class="k">{escape(label)}</span><span class="v">{escape(value)}</span></div>'


def _list_block(label: str, items: list) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{escape(str(i))}</li>" for i in items)
    return f"<h2>{escape(label)}</h2><ul>{lis}</ul>"


def render_fiche_html(fiche: NeedFiche, project_title: str | None = None) -> str:
    details = fiche.details or {}
    type_label = _TYPE_LABELS.get(fiche.need_type, fiche.need_type)
    priority = _PRIORITY_LABELS.get(str(details.get("priority", "medium")), "")
    raw_skills = details.get("skills")
    skills = raw_skills if isinstance(raw_skills, list) else []
    raw_deliverables = details.get("deliverables")
    deliverables = raw_deliverables if isinstance(raw_deliverables, list) else []
    projet = escape(project_title) if project_title else "Projet"
    skills_block = ""
    if skills:
        chips = "".join(f"<span>{escape(str(skill))}</span>" for skill in skills)
        skills_block = f'<h2>Compétences attendues</h2><div class="chips">{chips}</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  body {{ font-family: "Segoe UI", Roboto, sans-serif; color: {_INK}; font-size: 12px; padding: 8px 0; }}
  .eyebrow {{ color: {_CORAL}; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; font-weight: 700; }}
  h1 {{ color: {_INK}; font-size: 22px; margin: 4px 0 2px; }}
  .sub {{ color: {_MUTED}; font-size: 12px; margin: 0 0 14px; }}
  h2 {{ color: {_CORAL}; font-size: 13px; margin: 16px 0 6px; }}
  p {{ line-height: 1.5; }}
  .field {{ display: flex; justify-content: space-between; border-bottom: 1px solid #EEE; padding: 5px 0; }}
  .field .k {{ color: {_MUTED}; }}
  .field .v {{ font-weight: 600; text-align: right; }}
  .chips span {{ display: inline-block; border: 1px solid #DDD; border-radius: 12px;
    padding: 2px 10px; font-size: 11px; margin: 0 4px 4px 0; }}
  ul {{ margin: 4px 0; padding-left: 18px; }}
  .foot {{ color: {_MUTED}; font-size: 10px; margin-top: 24px; border-top: 1px solid #EEE; padding-top: 8px; }}
</style></head><body>
  <div class="eyebrow">Fiche de besoin · {escape(type_label)}{f" · {escape(priority)}" if priority else ""}</div>
  <h1>{escape(fiche.title)}</h1>
  <div class="sub">{projet}</div>
  {f"<p>{escape(fiche.description)}</p>" if fiche.description else ""}
  {_field("Profil recherché", str(details.get("profile", "")))}
  {_field("Budget estimatif", str(details.get("budget", "")))}
  {_field("Délai souhaité", str(details.get("timeline", "")))}
  {_field("Type d'engagement", str(details.get("engagement_type", "")))}
  {skills_block}
  {_list_block("Livrables attendus", deliverables)}
  <div class="foot">Généré par IDEAXION · fiche de besoin issue du Workshop.</div>
</body></html>"""


def render_fiche_pdf(html: str) -> bytes:
    # WeasyPrint optionnel (extra `pdf`) ; absence → ImportError (dégradée en 503 par l'appelant).
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
