"""Rapport de pré-diagnostic — rendu HTML/CSS → PDF (grille v2 : 4 piliers / 12 dims / 10).

`render_bilan_html` est PUR (stdlib) : testable hors-ligne. `render_bilan_pdf` convertit via
WeasyPrint (extra `pdf`). Couleurs charte « Aube » ; ton pédagogique et non culpabilisant.
Le `report` (couche structurée, cf. `RAPPORT_PREDIAGNOSTIC.md`) est optionnel : chaque section
ne s'affiche que si elle a du contenu (dégradation gracieuse).
"""

from __future__ import annotations

from html import escape

# Bandes d'affichage /10 — 3 niveaux.
_READINGS = [(8, "Fort", "strong"), (5, "Moyen", "watch"), (0, "Faible", "fragile")]

# Niveaux qualitatifs (risques / menace) → (libellé, ton).
_LEVELS = {
    "critical": ("Critique", "fragile"),
    "high": ("Élevée", "fragile"),
    "medium": ("Moyenne", "watch"),
    "low": ("Faible", "strong"),
}
_VERDICTS = {
    "go": ("Go", "strong"),
    "conditional": ("Sous conditions", "watch"),
    "nogo": ("À retravailler", "fragile"),
}


def reading(value: int) -> tuple[str, str]:
    for threshold, label, tone in _READINGS:
        if value >= threshold:
            return label, tone
    return "Faible", "fragile"


def _level(value: str | None) -> tuple[str, str]:
    return _LEVELS.get((value or "medium").lower(), ("Moyenne", "watch"))


def _bar(value: int, tone: str, scale_max: int) -> str:
    width = max(0, min(100, round(value * 100 / scale_max))) if scale_max else 0
    return f'<div class="bar"><span class="fill t-{tone}" style="width:{width}%"></span></div>'


def _money(value: object) -> str:
    if value in (None, "", 0):
        return "—"
    try:
        return f"{int(value):,}".replace(",", " ") + " FCFA"  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return escape(str(value))


def _e(value: object) -> str:
    return escape(str(value)) if value else ""


def render_bilan_html(
    *,
    project_title: str,
    category: str,
    grid_pillars: list[dict],
    grid_axes: list[dict],
    scores: dict[str, int],
    pillar_scores: dict[str, int],
    overall: int,
    scale_max: int = 10,
    grid_version: str,
    generated_at: str,
    n_passes: int = 1,
    confidence: float | None = None,
    report: dict | None = None,
    next_actions: list | None = None,
) -> str:
    overall_label, overall_tone = reading(overall)
    r = report or {}
    acts = next_actions or []

    # --- Radar (4 piliers / 12 dimensions) ---
    pillar_blocks: list[str] = []
    for pillar in grid_pillars:
        pscore = int(pillar_scores.get(pillar["key"], 0))
        plabel, ptone = reading(pscore)
        axis_rows: list[str] = []
        for axis in grid_axes:
            if axis.get("pillar") != pillar["key"]:
                continue
            ascore = int(scores.get(axis["key"], 0))
            _, atone = reading(ascore)
            axis_rows.append(
                f'<div class="axis"><span class="axis-name">{_e(axis.get("code"))} · {escape(axis["label"])}</span>'
                f'{_bar(ascore, atone, scale_max)}<span class="axis-val">{ascore}</span></div>'
            )
        pillar_blocks.append(
            f'<section class="lens"><header><h3>{escape(pillar["label"])}</h3>'
            f'<span class="chip t-{ptone}">{plabel} · {pscore}/{scale_max}</span></header>'
            f'<p class="lq">{escape(pillar.get("question", ""))}</p>{"".join(axis_rows)}</section>'
        )

    conf_chip = (
        f'<span class="meta-chip">Analyse consolidée · {n_passes} passes · confiance {confidence:.2f}</span>'
        if confidence is not None
        else ""
    )

    # --- Résumé + maturité ---
    resume_block = ""
    if r.get("summary"):
        mat = r.get("maturity")
        mat_chip = f'<span class="chip t-strong">Maturité · {_e(mat)}</span>' if mat else ""
        rat = f'<p class="lq">{_e(r.get("maturity_rationale"))}</p>' if r.get("maturity_rationale") else ""
        resume_block = (
            f'<section class="resume"><header><h3>Résumé du diagnostic</h3>{mat_chip}</header>'
            f'<p class="lead">{_e(r.get("summary"))}</p>{rat}</section>'
        )

    # --- Ta prochaine étape (routage déterministe, le CTA n°1) ---
    actions_block = ""
    if acts:
        primary = acts[0]
        others = "".join(f"<li>{escape(str(a.get('label', '')))}</li>" for a in acts[1:])
        others_html = f'<ul class="ns-list">{others}</ul>' if others else ""
        actions_block = (
            '<div class="sec">Ta prochaine étape</div>'
            '<section class="nextstep"><span class="ns-tag">À renforcer en priorité</span>'
            f'<div class="ns-label">{escape(str(primary.get("label", "")))}</div>'
            f'<div class="ns-sub">{_e(primary.get("code"))} · {_e(primary.get("dimension"))} '
            f"— {primary.get('score', 0)}/{scale_max}</div>{others_html}</section>"
        )

    # --- Description ---
    desc = r.get("description") or {}
    desc_pairs = [
        ("Problème résolu", desc.get("problem")),
        ("Solution proposée", desc.get("solution")),
        ("Client cible", desc.get("target_client")),
        ("Modèle économique", desc.get("business_model")),
    ]
    desc_cards = "".join(
        f'<div class="card"><div class="card-label">{escape(label)}</div><div class="card-value">{_e(val)}</div></div>'
        for label, val in desc_pairs
        if val
    )
    desc_block = (
        f'<div class="sec">Description du projet</div><div class="cards2">{desc_cards}</div>' if desc_cards else ""
    )

    # --- Verdict ---
    verdict = r.get("verdict") or {}
    verdict_block = ""
    if verdict.get("analysis") or verdict.get("label"):
        vlabel, vtone = _VERDICTS.get((verdict.get("status") or "conditional").lower(), ("Sous conditions", "watch"))
        head = verdict.get("label") or vlabel
        verdict_block = (
            f'<div class="sec">Verdict</div>'
            f'<section class="verdict t-border-{vtone}"><div class="vstatus t-text-{vtone}">{escape(head)}</div>'
            f'<p class="vtext">{_e(verdict.get("analysis"))}</p></section>'
        )

    # --- Forces ---
    strengths = [s for s in (r.get("strengths") or []) if isinstance(s, dict) and s.get("text")]
    forces_block = ""
    if strengths:
        rows = "".join(
            f'<tr><td>{i}</td><td>{_e(s.get("text"))}</td><td class="dim">{_e(s.get("dimension")).upper()}</td></tr>'
            for i, s in enumerate(strengths, 1)
        )
        forces_block = (
            '<div class="sec">Forces identifiées</div>'
            '<table class="data"><thead><tr><th>#</th><th>Force</th><th>Dim.</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    # --- Risques (matrice) ---
    risks = [x for x in (r.get("risks") or []) if isinstance(x, dict) and x.get("text")]
    risks_block = ""
    if risks:
        rows = ""
        for i, x in enumerate(risks, 1):
            pl, pt = _level(x.get("probability"))
            sl, st = _level(x.get("severity"))
            rows += (
                f"<tr><td>{i}</td><td>{_e(x.get('text'))}</td>"
                f'<td><span class="chip t-{pt}">{pl}</span></td>'
                f'<td><span class="chip t-{st}">{sl}</span></td></tr>'
            )
        risks_block = (
            '<div class="sec">Risques identifiés</div>'
            '<table class="data"><thead><tr><th>#</th><th>Risque</th><th>Prob.</th><th>Gravité</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    # --- Concurrence ---
    competition = [c for c in (r.get("competition") or []) if isinstance(c, dict) and c.get("name")]
    comp_block = ""
    if competition:
        rows = ""
        for c in competition:
            tl, tt = _level(c.get("threat"))
            rows += (
                f"<tr><td>{_e(c.get('name'))}</td><td>{_e(c.get('type'))}</td>"
                f'<td>{_e(c.get("description"))}</td><td><span class="chip t-{tt}">{tl}</span></td></tr>'
            )
        comp_block = (
            '<div class="sec">Paysage concurrentiel</div>'
            '<table class="data"><thead><tr><th>Concurrent</th><th>Type</th><th>Description</th><th>Menace</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    # --- Avancement ---
    prog = r.get("progress") or {}
    prog_metrics = [
        ("Stade", _e(prog.get("stage")) or "—"),
        ("Équipe", f"{prog['team_size']} pers." if prog.get("team_size") else "—"),
        ("Clients", str(prog["customers"]) if prog.get("customers") else "—"),
        ("Revenus", _money(prog.get("revenue"))),
        ("Financements", _money(prog.get("funding"))),
    ]
    prog_block = ""
    if any(prog.get(k) for k in ("stage", "team_size", "customers", "revenue", "funding")):
        cards = "".join(
            f'<div class="card center"><div class="card-label">{escape(lbl)}</div>'
            f'<div class="card-value">{val}</div></div>'
            for lbl, val in prog_metrics
        )
        prog_block = f'<div class="sec">Niveau d\'avancement</div><div class="metrics">{cards}</div>'

    # --- Recommandations ---
    recos = sorted(
        (x for x in (r.get("recommendations") or []) if isinstance(x, dict) and x.get("title")),
        key=lambda x: x.get("priority", 9),
    )
    reco_block = ""
    if recos:
        items = ""
        for x in recos:
            pr = int(x.get("priority", 3))
            cls = "high" if pr == 1 else "medium" if pr == 2 else "low"
            items += (
                f'<div class="reco"><div class="reco-p {cls}">{pr}</div>'
                f'<div class="reco-t"><strong>{_e(x.get("title"))}</strong><br>{_e(x.get("description"))}</div></div>'
            )
        reco_block = f'<div class="sec">Recommandations prioritaires</div>{items}'

    # --- Prochaines étapes ---
    steps = [s for s in (r.get("next_steps") or []) if isinstance(s, dict) and s.get("action")]
    steps_block = ""
    if steps:
        rows = "".join(
            f"<tr><td><strong>{_e(s.get('deadline'))}</strong></td><td>{_e(s.get('action'))}</td></tr>" for s in steps
        )
        steps_block = (
            '<div class="sec">Prochaines étapes</div>'
            '<table class="data"><thead><tr><th>Échéance</th><th>Action</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 16mm 15mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1C1633; margin: 0; font-size: 12px; }}
  .seal {{ height: 6px; background: linear-gradient(105deg, #FF7A4D, #F4B740); border-radius: 6px; }}
  header.top {{ display: flex; justify-content: space-between; align-items: flex-start; margin: 16px 0 6px; }}
  h1 {{ font-size: 22px; margin: 0; letter-spacing: -.2px; }}
  .sub {{ color: #6F6A86; font-size: 12.5px; margin-top: 4px; }}
  .score-ring {{ text-align: center; min-width: 96px; }}
  .score-ring .n {{ font-size: 36px; font-weight: 800; line-height: 1; color: #1FB0A0; }}
  .score-ring .l {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #1FB0A0; }}
  .meta {{ margin: 10px 0 12px; }}
  .meta-chip {{ display: inline-block; background: #F7F6FB; color: #6F6A86; font-size: 11px; padding: 4px 11px; border-radius: 999px; }}
  .nextstep {{ border: 1px solid #ffd9cb; background: #fff6f1; border-left: 4px solid #FF7A4D; border-radius: 12px; padding: 11px 15px; }}
  .ns-tag {{ font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #b1431f; }}
  .ns-label {{ font-size: 15px; font-weight: 800; margin: 3px 0 2px; }}
  .ns-sub {{ font-size: 11.5px; color: #6F6A86; }}
  .ns-list {{ margin: 8px 0 0; padding-left: 16px; }} .ns-list li {{ font-size: 11.5px; color: #3a3550; margin: 2px 0; }}
  .sec {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: #9a96ad; margin: 16px 0 8px; }}
  .resume {{ border: 1px solid #E7E4F0; border-left: 4px solid #FF7A4D; border-radius: 12px; padding: 12px 16px; margin-bottom: 6px; }}
  .resume header {{ display: flex; justify-content: space-between; align-items: center; }}
  .resume h3, .lens h3 {{ font-size: 15px; margin: 0; }}
  .lead {{ font-size: 13px; margin: 8px 0 0; line-height: 1.45; }}
  .lq {{ color: #6F6A86; font-size: 12px; margin: 4px 0 8px; }}
  .lens {{ border: 1px solid #E7E4F0; border-radius: 12px; padding: 12px 15px; margin-bottom: 9px; }}
  .lens header {{ display: flex; justify-content: space-between; align-items: center; }}
  .axis {{ display: flex; align-items: center; gap: 10px; margin: 5px 0; font-size: 12px; }}
  .axis-name {{ width: 195px; flex: none; }}
  .axis-val {{ width: 20px; text-align: right; font-weight: 600; }}
  .bar {{ flex: 1; height: 7px; background: #EEF1F5; border-radius: 999px; overflow: hidden; }}
  .fill {{ display: block; height: 100%; border-radius: 999px; }}
  .chip {{ font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 999px; }}
  .t-strong {{ background: #1FB0A0; }} .chip.t-strong {{ background: #e1f4f1; color: #14796d; }}
  .t-watch {{ background: #F4B740; }} .chip.t-watch {{ background: #fcf2da; color: #936708; }}
  .t-fragile {{ background: #FF7A4D; }} .chip.t-fragile {{ background: #ffe7dd; color: #b1431f; }}
  .cards2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
  .card {{ background: #F7F6FB; border: 1px solid #E7E4F0; border-radius: 8px; padding: 8px 11px; }}
  .card.center {{ text-align: center; }}
  .card-label {{ font-size: 9.5px; text-transform: uppercase; letter-spacing: .5px; color: #9a96ad; margin-bottom: 2px; }}
  .card-value {{ font-size: 12px; font-weight: 600; }}
  table.data {{ width: 100%; border-collapse: collapse; font-size: 11.5px; }}
  table.data th {{ text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .4px; color: #6F6A86; padding: 5px 6px; border-bottom: 1px solid #E7E4F0; background: #F7F6FB; }}
  table.data td {{ padding: 5px 6px; border-bottom: 1px solid #EEF1F5; vertical-align: top; }}
  table.data td.dim {{ font-weight: 700; color: #6F6A86; }}
  .verdict {{ background: #F7F6FB; border-left: 4px solid #1C1633; border-radius: 0 8px 8px 0; padding: 10px 14px; }}
  .verdict.t-border-strong {{ border-left-color: #1FB0A0; }}
  .verdict.t-border-watch {{ border-left-color: #F4B740; }}
  .verdict.t-border-fragile {{ border-left-color: #FF7A4D; }}
  .vstatus {{ font-size: 12px; font-weight: 800; margin-bottom: 3px; }}
  .t-text-strong {{ color: #14796d; }} .t-text-watch {{ color: #936708; }} .t-text-fragile {{ color: #b1431f; }}
  .vtext {{ font-size: 12px; color: #3a3550; line-height: 1.5; margin: 0; }}
  .metrics {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }}
  .reco {{ display: flex; gap: 9px; align-items: flex-start; margin-bottom: 7px; padding: 7px 10px; border-radius: 8px; background: #F7F6FB; }}
  .reco-p {{ width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; color: #fff; flex-shrink: 0; }}
  .reco-p.high {{ background: #FF7A4D; }} .reco-p.medium {{ background: #F4B740; }} .reco-p.low {{ background: #1FB0A0; }}
  .reco-t {{ font-size: 11.5px; color: #3a3550; }} .reco-t strong {{ color: #1C1633; }}
  .mentions {{ font-size: 9px; color: #9a96ad; line-height: 1.4; margin-top: 14px; padding-top: 6px; border-top: 1px solid #E7E4F0; }}
  footer {{ margin-top: 12px; color: #9a96ad; font-size: 10px; display: flex; justify-content: space-between; }}
</style></head><body>
  <div class="seal"></div>
  <header class="top">
    <div><h1>Rapport de pré-diagnostic</h1>
      <div class="sub">{escape(project_title)} · catégorie {escape(category)} · {escape(generated_at)}</div></div>
    <div class="score-ring"><div class="n">{overall}<span style="font-size:14px;">/{scale_max}</span></div>
      <div class="l">{overall_label}</div></div>
  </header>
  <div class="meta">{conf_chip}</div>
  {resume_block}
  {actions_block}
  {desc_block}
  <div class="sec">Radar — 4 piliers · 12 dimensions</div>
  {"".join(pillar_blocks)}
  {verdict_block}
  {forces_block}
  {risks_block}
  {comp_block}
  {prog_block}
  {reco_block}
  {steps_block}
  <div class="mentions">Pré-diagnostic généré par I.D.E.A — non contractuel. Ne constitue pas un conseil
    en investissement ni une garantie de financement. Droits RGPD : rgpd@ideaxion.com.</div>
  <footer>
    <span>Grille {escape(grid_version)} · l'IA propose, un regard humain affine.</span>
    <span>Confidentiel — Ideaxion</span>
  </footer>
</body></html>"""


def render_bilan_pdf(html: str) -> bytes:
    # WeasyPrint optionnel (extra `pdf`) ; absence → ImportError remontée (dégradation appelant).
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
