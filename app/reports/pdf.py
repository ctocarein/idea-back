"""Rapport de pré-diagnostic — rendu HTML multi-pages → PDF.

Design system Ideaxion (Aube) : Bricolage Grotesque + Inter, palette coral/gold/teal.
`render_bilan_html` est PUR (stdlib) : testable hors-ligne, sert directement le navigateur.
`render_bilan_pdf` convertit via WeasyPrint (extra `pdf`, optionnel).
Multi-pages avec saut de page print : page 1 cover, page 2 analyse expert, page 3 radar.
"""

from __future__ import annotations

import math
from html import escape

_READINGS = [(8, "Fort", "strong"), (5, "Moyen", "watch"), (0, "Faible", "fragile")]
_LEVELS = {
    "critical": ("Critique", "red"),
    "high": ("Élevée", "red"),
    "medium": ("Moyenne", "gold"),
    "low": ("Faible", "teal"),
}
_VERDICTS = {
    "go": ("Go", "go"),
    "conditional": ("Sous conditions", "conditional"),
    "nogo": ("À retravailler", "nogo"),
}


def reading(value: int) -> tuple[str, str]:
    for threshold, label, tone in _READINGS:
        if value >= threshold:
            return label, tone
    return "Faible", "fragile"


def _level(value: str | None) -> tuple[str, str]:
    return _LEVELS.get((value or "medium").lower(), ("Moyenne", "gold"))


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


def _bar_cls(score: int, scale_max: int) -> str:
    pct = score / scale_max if scale_max else 0
    if pct >= 0.8:
        return "teal"
    if pct >= 0.5:
        return "gold"
    return "red"


# Libellés courts pour les 12 dimensions standards du radar
_AXIS_SHORT: dict[str, str] = {
    "d1": "Problème", "d2": "Solution", "d3": "Valeur",
    "d4": "Marché", "d5": "Concurrence", "d6": "Modèle éco",
    "d7": "Traction", "d8": "Croissance", "d9": "Go-to-Market",
    "d10": "Équipe", "d11": "Avancement", "d12": "Risques",
}


def _axis_short(axis: dict) -> str:
    key = axis.get("key", "")
    if key in _AXIS_SHORT:
        return _AXIS_SHORT[key]
    # Fallback générique : premier segment avant " & "
    label = axis.get("label", key)
    part = label.split(" & ")[0].strip()
    words = part.split()
    if len(words) <= 2:
        return part[:14]
    # Sauter les prépositions "de/du/d'"
    if words[1].lower() in ("de", "du", "des") or words[1].lower().startswith("d'"):
        return (words[2] if len(words) > 2 else words[1][2:])[:14]
    return " ".join(words[:2])[:14]


def _radar_svg(scores: dict[str, int], axes: list[dict], scale_max: int) -> str:
    """SVG radar 12 dimensions avec labels lisibles et scores colorés."""
    n = min(12, len(axes))
    R = 160          # rayon de la grille
    CX, CY = 310, 310
    LR = R + 58      # rayon des étiquettes
    step = 2 * math.pi / n

    def pt(i: int, radius: float) -> tuple[float, float]:
        a = -math.pi / 2 + i * step
        return CX + radius * math.cos(a), CY + radius * math.sin(a)

    # Anneaux de grille (25 % / 50 % / 75 % / 100 %)
    rings = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{pt(i, R * frac)[0]:.1f},{pt(i, R * frac)[1]:.1f}" for i in range(n))
        sw, sc = ("1.5", "#c8c4dc") if frac == 1.0 else ("0.8", "#e7e4f0")
        rings.append(f'<polygon points="{pts}" fill="none" stroke="{sc}" stroke-width="{sw}"/>')

    # Petits repères chiffrés sur l'axe vertical (50 % = 5, 100 % = 10)
    ax5, ay5 = pt(0, R * 0.5)
    ax10, ay10 = pt(0, R * 1.0)
    scale_ticks = (
        f'<text x="{ax5 + 5:.1f}" y="{ay5 + 4:.1f}" font-size="9" fill="#b0abc8" '
        f'font-family="system-ui,sans-serif">5</text>'
        f'<text x="{ax10 + 5:.1f}" y="{ay10 + 4:.1f}" font-size="9" fill="#b0abc8" '
        f'font-family="system-ui,sans-serif">10</text>'
    )

    # Rayons
    spokes = "".join(
        f'<line x1="{CX}" y1="{CY}" x2="{pt(i, R)[0]:.1f}" y2="{pt(i, R)[1]:.1f}" '
        f'stroke="#e7e4f0" stroke-width="0.8"/>'
        for i in range(n)
    )

    # Polygone de données + points colorés
    data_pts: list[str] = []
    dots: list[str] = []
    for i, axis in enumerate(axes[:n]):
        score = int(scores.get(axis["key"], 0))
        x, y = pt(i, score / scale_max * R if scale_max else 0)
        data_pts.append(f"{x:.1f},{y:.1f}")
        dot_c = "#1fb0a0" if score >= 8 else "#f4b740" if score >= 5 else "#e0473b"
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{dot_c}" stroke="#fff" stroke-width="2"/>'
        )

    poly_pts = " ".join(data_pts)
    poly = (
        f'<polygon points="{poly_pts}" fill="rgba(255,122,77,.18)" stroke="none"/>'
        f'<polygon points="{poly_pts}" fill="none" stroke="#ff7a4d" stroke-width="2.5" '
        f'stroke-linejoin="round"/>'
    )

    # Étiquettes bi-lignes : nom court (bold) + score coloré
    labels: list[str] = []
    for i, axis in enumerate(axes[:n]):
        angle = -math.pi / 2 + i * step
        lx = CX + LR * math.cos(angle)
        ly = CY + LR * math.sin(angle)

        short = _e(_axis_short(axis))
        score = int(scores.get(axis.get("key", ""), 0))
        score_c = "#1fb0a0" if score >= 8 else "#f4b740" if score >= 5 else "#e0473b"

        # Ancrage horizontal
        anchor = "middle" if abs(lx - CX) < 22 else ("start" if lx > CX else "end")

        # Décalage vertical : texte centré verticalement autour du point de label
        # Moitié supérieure : texte au-dessus → première ligne au-dessus du point
        # Moitié inférieure : texte en-dessous → première ligne au point
        if ly < CY - 35:   # secteur haut
            dy1, dy2 = "-13", "13"
        elif ly > CY + 35:  # secteur bas
            dy1, dy2 = "4", "13"
        else:               # côtés gauche/droit
            dy1, dy2 = "-5", "13"

        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-family="system-ui,sans-serif">'
            f'<tspan x="{lx:.1f}" dy="{dy1}" font-size="12.5" '
            f'fill="#1c1633" font-weight="700">{short}</tspan>'
            f'<tspan x="{lx:.1f}" dy="{dy2}" font-size="11" '
            f'fill="{score_c}" font-weight="700">{score}/10</tspan>'
            f'</text>'
        )

    return (
        '<svg width="100%" viewBox="0 0 620 620" role="img" '
        'aria-label="Radar 12 dimensions Ideaxion">'
        f'{"".join(rings)}{spokes}{scale_ticks}{poly}'
        f'{"".join(dots)}{"".join(labels)}'
        '</svg>'
    )


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
    overall_100 = round(overall * 100 / scale_max) if scale_max else 0
    overall_label, _ = reading(overall)
    r = report or {}
    acts = next_actions or []

    mat = r.get("maturity") or overall_label

    # Données structurées
    strengths = [s for s in (r.get("strengths") or []) if isinstance(s, dict) and s.get("text")]
    risks = [x for x in (r.get("risks") or []) if isinstance(x, dict) and x.get("text")]
    recos = sorted(
        [x for x in (r.get("recommendations") or []) if isinstance(x, dict) and x.get("title")],
        key=lambda x: x.get("priority", 9),
    )
    steps = [s for s in (r.get("next_steps") or []) if isinstance(s, dict) and s.get("action")]
    desc = r.get("description") or {}
    competition = [c for c in (r.get("competition") or []) if isinstance(c, dict) and c.get("name")]

    # --- Verdict ---
    verdict = r.get("verdict") or {}
    v_status = (verdict.get("status") or "conditional").lower()
    _, v_cls = _VERDICTS.get(v_status, ("Sous conditions", "conditional"))
    v_head = verdict.get("label") or _VERDICTS.get(v_status, ("Sous conditions", "conditional"))[0]

    # --- Carte Forces ---
    forces_items = "".join(f"<li>{_e(s.get('text'))}</li>" for s in strengths) or "<li>—</li>"
    forces_card = (
        '<div class="card success"><h3>Forces identifiées</h3>'
        f'<ul class="list">{forces_items}</ul></div>'
    )

    # --- Carte Risques ---
    risks_items = "".join(f"<li>{_e(x.get('text'))}</li>" for x in risks) or "<li>—</li>"
    risks_card = (
        '<div class="card danger"><h3>Risques détectés</h3>'
        f'<ul class="list">{risks_items}</ul></div>'
    )

    # --- Carte Description / À clarifier ---
    desc_items: list[str] = []
    if desc.get("solution"):
        desc_items.append(f"<li><strong>Solution :</strong> {_e(desc['solution'])}</li>")
    if desc.get("target_client"):
        desc_items.append(f"<li><strong>Cible :</strong> {_e(desc['target_client'])}</li>")
    if desc.get("business_model"):
        desc_items.append(f"<li><strong>Modèle éco :</strong> {_e(desc['business_model'])}</li>")
    if not desc_items:
        desc_items = ["<li>Données non renseignées</li>"]
    desc_card = (
        '<div class="card warning"><h3>Éléments clés</h3>'
        f'<ul class="list">{"".join(desc_items)}</ul></div>'
    )

    # --- Verdict box ---
    verdict_box = ""
    if verdict.get("label") or verdict.get("analysis"):
        verdict_box = (
            f'<div class="verdict-box {v_cls}">'
            f'<div class="v-label">{escape(v_head)}</div>'
            f'<p class="v-text">{_e(verdict.get("analysis"))}</p>'
            f"</div>"
        )

    # --- Recommandations (roadmap) ---
    reco_block = ""
    if recos:
        items = ""
        for x in recos:
            pr = int(x.get("priority", 3))
            tag_cls = "red" if pr == 1 else "gold" if pr == 2 else "teal"
            tag_lbl = "Urgent" if pr == 1 else "Priorité haute" if pr == 2 else "Action recommandée"
            items += (
                f'<div class="step"><div>'
                f'<h3>{_e(x.get("title"))}</h3>'
                f'<p>{_e(x.get("description"))}</p>'
                f'</div><span class="tag {tag_cls}">{tag_lbl}</span></div>'
            )
        reco_block = f'<div style="margin-top:20px;"><div class="eyebrow" style="margin-bottom:14px;">Recommandations prioritaires</div><div class="roadmap">{items}</div></div>'

    # --- Prochaines étapes ---
    steps_block = ""
    if steps:
        rows = "".join(
            f"<tr><td><strong>{_e(s.get('deadline'))}</strong></td><td>{_e(s.get('action'))}</td></tr>"
            for s in steps
        )
        steps_block = (
            '<div style="margin-top:20px;"><div class="eyebrow" style="margin-bottom:10px;">Prochaines étapes</div>'
            '<table class="data-table"><thead><tr><th>Échéance</th><th>Action</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>"
        )

    # --- Radar SVG ---
    radar_svg = _radar_svg(scores, grid_axes, scale_max)

    # --- Barres par dimension ---
    dim_bars_html = ""
    for axis in grid_axes:
        score = int(scores.get(axis["key"], 0))
        pct = round(score / scale_max * 100) if scale_max else 0
        cls = _bar_cls(score, scale_max)
        dim_bars_html += (
            f'<div class="dimension">'
            f'<div class="dimension-head">'
            f'<span class="dimension-title">{_e(axis.get("code"))} · {escape(axis["label"])}</span>'
            f'<span class="dimension-score">{score}/{scale_max}</span>'
            f"</div>"
            f'<div class="bar-wrap"><div class="bar-fill {cls}" style="width:{pct}%"></div></div>'
            f"</div>"
        )

    # --- Métriques résumé ---
    n_strong = sum(1 for v in scores.values() if v >= 8)
    n_medium = sum(1 for v in scores.values() if 5 <= v < 8)
    n_weak = sum(1 for v in scores.values() if v < 5)
    summary_strip = (
        '<div class="summary-strip">'
        '<div class="metric"><div class="metric-number">12</div><div class="metric-label">dimensions analysées</div></div>'
        f'<div class="metric"><div class="metric-number">{n_strong}</div><div class="metric-label">dimensions fortes</div></div>'
        f'<div class="metric"><div class="metric-number">{n_medium}</div><div class="metric-label">axes à consolider</div></div>'
        f'<div class="metric"><div class="metric-number">{n_weak}</div><div class="metric-label">axes à renforcer</div></div>'
        "</div>"
    )

    # --- Legend tags page 1 ---
    legend_tags = ""
    if strengths:
        legend_tags += f'<span class="tag teal">Forces : {len(strengths)} identifiées</span>'
    if risks:
        legend_tags += f'<span class="tag red">Risques : {len(risks)} détectés</span>'
    if recos:
        legend_tags += f'<span class="tag gold">Actions : {len(recos)} recommandations</span>'

    # --- Description courte pour cover ---
    cover_desc = _e((desc.get("problem") or r.get("summary") or "")[:240])

    # --- Page next actions ---
    next_page = ""
    if acts:
        primary = acts[0]
        other_items = "".join(f"<li>{_e(str(a.get('label', '')))}</li>" for a in acts[1:4])
        next_page = (
            '<section class="page">'
            '<div class="page-inner">'
            '<div class="topbar"><div>'
            '<div class="eyebrow">Fil rouge</div>'
            "<h2>Ta prochaine priorité</h2></div></div>"
            '<div class="nextstep-box">'
            '<div class="ns-tag">À renforcer en priorité</div>'
            f'<div class="ns-title">{_e(str(primary.get("label", "")))}</div>'
            f'<div class="ns-sub">{_e(primary.get("code"))} · {_e(primary.get("dimension"))} — {primary.get("score", 0)}/{scale_max}</div>'
            + (f'<ul class="ns-list">{other_items}</ul>' if other_items else "")
            + "</div></div>"
            '<div class="footer-bar"><span>Ideaxion · Plan d\'action personnalisé</span><span>Page 4</span></div>'
            "</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Bilan RADAR · {escape(project_title)} · Ideaxion</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --ink: #1c1633; --ink-soft: #2a2147; --paper: #f7f6fb;
      --coral: #ff7a4d; --coral-strong: #ea5a2c;
      --gold: #f4b740; --teal: #1fb0a0;
      --muted-ink: #6f6a86; --line: #e7e4f0;
      --danger-ink: #e0473b; --white: #ffffff;
      --success-bg: rgba(31,176,160,.10); --gold-bg: rgba(244,183,64,.14);
      --coral-bg: rgba(255,122,77,.12); --danger-bg: rgba(224,71,59,.10);
      --shadow: 0 20px 50px rgba(28,22,51,.10);
      --r-lg: 24px; --r-md: 16px; --r-sm: 10px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, rgba(255,122,77,.12), transparent 30rem),
                  radial-gradient(circle at top right, rgba(31,176,160,.10), transparent 28rem),
                  var(--paper);
      color: var(--ink); font-family: "Inter", system-ui, sans-serif;
      font-size: 14px; line-height: 1.55;
    }}
    h1,h2,h3 {{ font-family: "Bricolage Grotesque","Inter",sans-serif; letter-spacing: -.03em; margin: 0; }}
    h1 {{ font-size: 36px; line-height: 1.05; }}
    h2 {{ font-size: 22px; line-height: 1.12; margin-bottom: 14px; }}
    h3 {{ font-size: 15px; line-height: 1.2; margin-bottom: 5px; }}
    p {{ margin: 0; }}
    .document {{ width: min(1080px, calc(100% - 40px)); margin: 26px auto 68px; }}
    .page {{ background: rgba(255,255,255,.92); border: 1px solid var(--line); box-shadow: var(--shadow); border-radius: var(--r-lg); overflow: hidden; margin-bottom: 26px; }}
    .page-inner {{ padding: 32px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 24px; }}
    .eyebrow {{ color: var(--muted-ink); text-transform: uppercase; letter-spacing: .22em; font-weight: 700; font-size: 11px; margin-bottom: 8px; }}
    .brand-card {{ min-width: 190px; background: var(--ink); color: var(--white); border-radius: 18px; padding: 18px; text-align: right; flex-shrink: 0; }}
    .brand-card .logo {{ font-family: "Bricolage Grotesque","Inter",sans-serif; font-weight: 800; font-size: 20px; letter-spacing: -.04em; }}
    .brand-card .small {{ opacity: .70; margin-top: 5px; font-size: 11.5px; }}
    .hero-grid {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px; align-items: stretch; }}
    .score-panel {{ background: linear-gradient(145deg, var(--ink), var(--ink-soft)); color: var(--white); border-radius: var(--r-lg); padding: 26px; position: relative; overflow: hidden; min-height: 280px; }}
    .score-panel::after {{ content:""; position:absolute; width:240px; height:240px; background:radial-gradient(circle,rgba(255,122,77,.35),transparent 68%); bottom:-90px; right:-60px; pointer-events:none; }}
    .score-lbl {{ color:rgba(255,255,255,.62); text-transform:uppercase; letter-spacing:.18em; font-size:11px; font-weight:700; }}
    .score-big {{ font-family:"Bricolage Grotesque","Inter",sans-serif; font-size:90px; line-height:.9; letter-spacing:-.07em; margin-top:14px; }}
    .score-big span {{ color:var(--coral); font-size:40px; letter-spacing:-.05em; }}
    .maturity-pill {{ display:inline-flex; align-items:center; gap:7px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.18); padding:7px 12px; border-radius:999px; margin-top:18px; font-weight:700; font-size:12.5px; }}
    .dot-g {{ width:8px; height:8px; border-radius:999px; display:inline-block; background:var(--gold); box-shadow:0 0 0 4px rgba(244,183,64,.18); }}
    .score-comment {{ color:rgba(255,255,255,.68); margin-top:16px; font-size:12.5px; line-height:1.5; position:relative; z-index:1; }}
    .project-card {{ background:var(--white); border:1px solid var(--line); border-radius:var(--r-lg); padding:24px; }}
    .meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:16px; }}
    .meta {{ border:1px solid var(--line); border-radius:var(--r-sm); padding:10px 12px; background:var(--paper); }}
    .meta .label {{ font-size:11px; color:var(--muted-ink); margin-bottom:2px; text-transform:uppercase; letter-spacing:.04em; }}
    .meta .value {{ font-weight:700; color:var(--ink); font-size:12.5px; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:16px; }}
    .tag {{ display:inline-flex; padding:4px 9px; border-radius:999px; background:var(--paper); color:var(--muted-ink); font-weight:700; font-size:11.5px; white-space:nowrap; }}
    .tag.teal {{ background:var(--success-bg); color:#148276; }}
    .tag.gold {{ background:var(--gold-bg); color:#9f6d00; }}
    .tag.coral {{ background:var(--coral-bg); color:var(--coral-strong); }}
    .tag.red {{ background:var(--danger-bg); color:var(--danger-ink); }}
    .section-grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; }}
    .card {{ background:var(--white); border:1px solid var(--line); border-radius:var(--r-md); padding:18px; position:relative; overflow:hidden; }}
    .card::before {{ content:""; display:block; width:36px; height:4px; border-radius:999px; background:var(--coral); margin-bottom:12px; }}
    .card.success::before {{ background:var(--teal); }}
    .card.warning::before {{ background:var(--gold); }}
    .card.danger::before {{ background:var(--danger-ink); }}
    .list {{ margin:0; padding-left:16px; color:var(--muted-ink); font-size:12.5px; }}
    .list li {{ margin-bottom:6px; }}
    .verdict-box {{ background:linear-gradient(135deg,#f7f6fb,#fff); border:1px solid var(--line); border-left:5px solid var(--gold); border-radius:var(--r-md); padding:18px 22px; margin-top:18px; }}
    .verdict-box.go {{ border-left-color:var(--teal); }}
    .verdict-box.nogo {{ border-left-color:var(--danger-ink); }}
    .verdict-box .v-label {{ font-family:"Bricolage Grotesque","Inter",sans-serif; font-size:18px; font-weight:800; margin-bottom:7px; color:var(--ink); }}
    .verdict-box.go .v-label {{ color:#148276; }}
    .verdict-box.nogo .v-label {{ color:var(--danger-ink); }}
    .verdict-box .v-text {{ font-size:13px; color:#3a3550; line-height:1.6; }}
    .roadmap {{ display:grid; gap:10px; counter-reset:step; }}
    .step {{ display:grid; grid-template-columns:46px 1fr 155px; gap:14px; align-items:center; background:var(--white); border:1px solid var(--line); border-radius:16px; padding:14px; }}
    .step::before {{ counter-increment:step; content:counter(step); width:38px; height:38px; border-radius:12px; background:var(--ink); color:var(--white); display:grid; place-items:center; font-weight:800; font-family:"Bricolage Grotesque","Inter",sans-serif; font-size:18px; }}
    .step h3 {{ margin-bottom:2px; font-size:13.5px; }}
    .step p {{ color:var(--muted-ink); font-size:12px; }}
    .data-table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
    .data-table th {{ text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted-ink); padding:6px 8px; border-bottom:1px solid var(--line); background:var(--paper); }}
    .data-table td {{ padding:6px 8px; border-bottom:1px solid #f0eef8; vertical-align:top; }}
    .radar-wrap {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start; }}
    .radar-card {{ background:linear-gradient(180deg,#fff,#faf9fd); border:1px solid var(--line); border-radius:var(--r-lg); padding:16px; display:flex; justify-content:center; align-items:center; min-height:480px; }}
    .radar-card svg {{ display:block; width:100%; height:auto; }}
    .dimension-list {{ display:grid; grid-template-columns:1fr; gap:9px; }}
    .dimension {{ border:1px solid var(--line); border-radius:12px; padding:10px 13px; background:var(--white); }}
    .dimension-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:7px; gap:10px; }}
    .dimension-title {{ font-weight:600; font-size:12.5px; }}
    .dimension-score {{ font-weight:800; font-size:12.5px; }}
    .bar-wrap {{ height:7px; border-radius:999px; background:var(--line); overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; background:var(--coral); transition:width .3s; }}
    .bar-fill.teal {{ background:var(--teal); }}
    .bar-fill.gold {{ background:var(--gold); }}
    .bar-fill.red {{ background:var(--danger-ink); }}
    .summary-strip {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:18px; }}
    .metric {{ border:1px solid var(--line); background:var(--white); border-radius:14px; padding:14px; }}
    .metric-number {{ font-family:"Bricolage Grotesque","Inter",sans-serif; font-size:28px; color:var(--ink); font-weight:800; }}
    .metric-label {{ color:var(--muted-ink); font-size:11.5px; margin-top:2px; }}
    .nextstep-box {{ border:1px solid #ffd9cb; background:#fff6f1; border-left:5px solid var(--coral); border-radius:var(--r-md); padding:18px 22px; }}
    .ns-tag {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:#b1431f; margin-bottom:6px; }}
    .ns-title {{ font-family:"Bricolage Grotesque","Inter",sans-serif; font-size:18px; font-weight:800; margin-bottom:5px; }}
    .ns-sub {{ font-size:12.5px; color:var(--muted-ink); }}
    .ns-list {{ margin:10px 0 0; padding-left:16px; font-size:12.5px; color:#3a3550; }}
    .ns-list li {{ margin-bottom:4px; }}
    .print-btn {{ position:fixed; right:20px; bottom:20px; border:none; background:var(--coral-strong); color:var(--white); font-weight:800; border-radius:999px; padding:12px 18px; box-shadow:0 10px 26px rgba(234,90,44,.28); cursor:pointer; z-index:20; font-size:13px; font-family:"Inter",sans-serif; }}
    .footer-bar {{ display:flex; justify-content:space-between; gap:14px; color:var(--muted-ink); font-size:11.5px; border-top:1px solid var(--line); padding:14px 32px; background:rgba(247,246,251,.72); }}
    .mentions {{ font-size:10px; color:var(--muted-ink); line-height:1.4; margin-top:14px; padding-top:8px; border-top:1px solid var(--line); }}
    @media (max-width:900px) {{
      .hero-grid,.radar-wrap,.section-grid,.summary-strip {{ grid-template-columns:1fr; }}
      .step {{ grid-template-columns:42px 1fr; }}
    }}
    @media print {{
      body {{ background:var(--paper); }}
      .document {{ width:100%; margin:0; }}
      .page {{ border-radius:0; box-shadow:none; border:none; min-height:100vh; page-break-after:always; margin:0; }}
      .print-btn {{ display:none; }}
    }}
  </style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">Imprimer / PDF</button>
  <main class="document">

    <!-- PAGE 1 — Cover & Score -->
    <section class="page">
      <div class="page-inner">
        <div class="topbar">
          <div>
            <div class="eyebrow">Bilan de diagnostic entrepreneurial</div>
            <h1>Score RADAR Ideaxion</h1>
            <p style="color:var(--muted-ink);font-size:15px;margin-top:10px;max-width:620px;">
              Analyse en 12 dimensions · Maturité, forces, risques et recommandations
            </p>
          </div>
          <div class="brand-card">
            <div class="logo">Ideaxion</div>
            <div class="small">De l'idée brute à l'entreprise fiable</div>
          </div>
        </div>
        <div class="hero-grid">
          <div class="score-panel">
            <div class="score-lbl">Score global</div>
            <div class="score-big">{overall_100}<span>%</span></div>
            <div class="maturity-pill"><span class="dot-g"></span>{escape(mat)}</div>
            <p class="score-comment">{_e(r.get("summary")) or "Analyse multi-dimensionnelle de la maturité entrepreneuriale du projet."}</p>
          </div>
          <div class="project-card">
            <div class="eyebrow">Projet analysé</div>
            <h2>{escape(project_title)}</h2>
            <p style="color:var(--muted-ink);font-size:12.5px;margin-top:8px;line-height:1.5;">{cover_desc}</p>
            <div class="meta-grid">
              <div class="meta"><div class="label">Catégorie</div><div class="value">{escape(category) or "—"}</div></div>
              <div class="meta"><div class="label">Date du bilan</div><div class="value">{escape(generated_at)}</div></div>
              <div class="meta"><div class="label">Grille</div><div class="value">{escape(grid_version)}</div></div>
              <div class="meta"><div class="label">Score global</div><div class="value">{overall_100}/100</div></div>
            </div>
            <div class="legend">{legend_tags}</div>
          </div>
        </div>
      </div>
      <div class="footer-bar">
        <span>Ideaxion · Bilan RADAR — Document confidentiel</span>
        <span>Page 1</span>
      </div>
    </section>

    <!-- PAGE 2 — Analyse d'expert -->
    <section class="page">
      <div class="page-inner">
        <div class="topbar">
          <div>
            <div class="eyebrow">Point de vue Ideaxion</div>
            <h2>Analyse et recommandations</h2>
          </div>
        </div>
        <div class="section-grid">
          {forces_card}
          {risks_card}
          {desc_card}
        </div>
        {verdict_box}
        {reco_block}
        {steps_block}
        <div class="mentions">Ce rapport est généré par I.D.E.A (Intelligence Diagnostique d'Expertise Appliquée) — Ideaxion.
        Non contractuel. Ne constitue pas un conseil en investissement ni une garantie de financement. RGPD : rgpd@ideaxion.com.</div>
      </div>
      <div class="footer-bar">
        <span>Ideaxion · Analyse IA — le regard humain affine</span>
        <span>Page 2</span>
      </div>
    </section>

    <!-- PAGE 3 — Radar 12 dimensions -->
    <section class="page">
      <div class="page-inner">
        <div class="topbar">
          <div>
            <div class="eyebrow">Radar 12 dimensions</div>
            <h2>Performance détaillée par axe</h2>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;margin-top:20px;">
            <span class="tag teal">Fort ≥ 8/10</span>
            <span class="tag gold">Moyen 5-7</span>
            <span class="tag red">À renforcer &lt; 5</span>
          </div>
        </div>
        <div class="radar-wrap">
          <div class="radar-card">{radar_svg}</div>
          <div class="dimension-list">{dim_bars_html}</div>
        </div>
        {summary_strip}
      </div>
      <div class="footer-bar">
        <span>Score RADAR · Grille {escape(grid_version)} · {escape(generated_at)}</span>
        <span>Page 3</span>
      </div>
    </section>

    {next_page}

  </main>
</body>
</html>"""


def render_bilan_pdf(html: str) -> bytes:
    # WeasyPrint optionnel (extra `pdf`) ; absence → ImportError remontée (dégradation appelant).
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
