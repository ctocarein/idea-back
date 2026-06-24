"""Post-mortem de pitch — rendu HTML/CSS → PDF (charte « Aube »).

`render_postmortem_html` est PUR (stdlib) : testable hors-ligne. `render_postmortem_pdf`
convertit via WeasyPrint (extra `pdf`) ; son absence remonte une ImportError que l'appelant
dégrade en 503. Ton exigeant mais bienveillant — Fond = score, Forme = indicatif.
"""

from __future__ import annotations

from html import escape

from app.pitchsim.schemas import PostMortemOut

_INK = "#1C1633"
_CORAL = "#FF7A4D"
_TEAL = "#1FB0A0"


def _bar(value: float, color: str) -> str:
    width = max(0, min(100, round(value * 10)))
    return (
        f'<div style="background:#EEE;border-radius:6px;height:10px;overflow:hidden">'
        f'<span style="display:block;height:10px;width:{width}%;background:{color}"></span></div>'
    )


def render_postmortem_html(pm: PostMortemOut) -> str:
    s = pm.scores
    lvl = s["level"]
    rows = []
    for ax in pm.radar:
        score = ax["score"]
        txt = f"{score}/10" if score is not None else "— (Mode Caméra)"
        rows.append(f"<tr><td>{escape(ax['label'])}</td><td>{txt}</td></tr>")
    radar = "".join(rows)

    strengths = "".join(f"<li>✅ {escape(w['label'])} ({w['score']}/10)</li>" for w in pm.strengths)
    weaknesses = "".join(f"<li>⚠️ {escape(w['label'])} ({w['score']}/10)</li>" for w in pm.weaknesses)
    plan = "".join(f"<li>{escape(p['label'])}</li>" for p in pm.training_plan)
    progression = " → ".join(f"{p['global']}" for p in pm.progression)

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  body {{ font-family: "Segoe UI", Roboto, sans-serif; color: {_INK}; font-size: 12px; }}
  h1 {{ color: {_INK}; }} h2 {{ color: {_CORAL}; font-size: 14px; margin-top: 18px; }}
  .big {{ font-size: 28px; font-weight: 700; }}
  .badge {{ font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 4px 6px; border-bottom: 1px solid #EEE; }}
  ul {{ margin: 4px 0; padding-left: 18px; }}
</style></head><body>
  <h1>Rapport post-mortem — {escape(pm.committee_key)}</h1>
  <p class="big">{s["global_100"]}/100 <span class="badge">{lvl["badge"]} {escape(lvl["title"])}</span></p>
  <p>Fond (credential) : <b>{s["fond"]}/10</b> &nbsp;·&nbsp; Forme (indicatif) : {s["forme"]}/10</p>
  {_bar(s["fond"], _TEAL)}
  <h2>Radar de pitch</h2>
  <table>{radar}</table>
  <h2>Forces</h2><ul>{strengths or "<li>—</li>"}</ul>
  <h2>À travailler</h2><ul>{weaknesses or "<li>—</li>"}</ul>
  <h2>Progression</h2><p>{progression}</p>
  <h2>Plan d'entraînement</h2><ul>{plan}</ul>
</body></html>"""


def render_postmortem_pdf(html: str) -> bytes:
    # WeasyPrint optionnel (extra `pdf`) ; absence → ImportError (dégradée en 503 par l'appelant).
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
