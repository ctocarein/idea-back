"""Rendu HTML d'un deck de pitch — la SOURCE de vérité du design (V1.3).

Le HTML est autonome (Chart.js via CDN, images par mot-clé) et rendu tel quel
dans le navigateur (aperçu) ou converti en PDF/PPTX via Chromium (Playwright).
Fonction PURE (stdlib) : testable hors-ligne.
"""

from __future__ import annotations

import json
from html import escape

from app.pitch.models import Pitch

# --- Thèmes (templates). Un thème = un jeu de variables CSS. ---
TEMPLATES: dict[str, dict] = {
    "base": {"label": "Base", "ink": "#1C1633", "accent": "#FF7A4D", "bg": "#FFFFFF", "muted": "#6B6580", "band": "#F4F1FB"},
    "midnight": {"label": "Midnight", "ink": "#EAeaf5", "accent": "#7C6BFF", "bg": "#141026", "muted": "#A9A3C4", "band": "#1E1838"},
    "editorial": {"label": "Éditorial", "ink": "#23201A", "accent": "#C2410C", "bg": "#FBF8F1", "muted": "#7A7263", "band": "#F0E9DB"},
}


def _img(keyword: str | None) -> str:
    kw = (keyword or "startup business").strip().replace(" ", ",")
    # Stand-in Unsplash sans clé (mot-clé → photo). Swappable vers l'API Unsplash.
    return f"https://loremflickr.com/1200/900/{kw}"


def _slide(s: dict, t: dict, idx: int) -> str:
    layout = s.get("layout", "bullets")
    title = escape(str(s.get("title", "")))
    subtitle = escape(str(s.get("subtitle", "")))
    bullets = [escape(str(b)) for b in (s.get("bullets") or []) if str(b).strip()]
    caption = escape(str(s.get("caption", "")))

    if layout == "cover":
        return f"""<section class="slide cover" style="background-image:linear-gradient(120deg,{t['ink']}CC,{t['ink']}55),url('{_img(s.get('image_keyword'))}')">
          <div class="cover-in">
            <h1>{title}</h1>
            <p class="lead">{subtitle}</p>
          </div></section>"""

    if layout == "stat":
        stat = s.get("stat") or {}
        return f"""<section class="slide stat">
          <div class="stat-in">
            <div class="big-num">{escape(str(stat.get('value','')))}</div>
            <div class="stat-label">{escape(str(stat.get('label','')))}</div>
            <p class="ctx">{subtitle or (bullets[0] if bullets else '')}</p>
          </div></section>"""

    if layout == "chart":
        chart = s.get("chart") or {}
        cid = f"chart{idx}"
        data = json.dumps({"type": chart.get("type", "bar"), "labels": chart.get("labels", []), "values": chart.get("values", [])})
        return f"""<section class="slide chart">
          <div class="pad">
            <span class="eyebrow">{escape(str(chart.get('type','')).upper())}</span>
            <h2>{title}</h2>
            <div class="chart-wrap"><canvas id="{cid}" data-chart='{data}'></canvas></div>
          </div></section>"""

    if layout == "image":
        return f"""<section class="slide image">
          <div class="img-half" style="background-image:url('{_img(s.get('image_keyword'))}')"></div>
          <div class="img-txt"><h2>{title}</h2><p>{caption or subtitle}</p></div>
        </section>"""

    # bullets (défaut)
    lis = "".join(f"<li>{b}</li>" for b in bullets[:3]) or "<li>—</li>"
    img = f"<div class=\"b-img\" style=\"background-image:url('{_img(s.get('image_keyword'))}')\"></div>" if s.get("image_keyword") else ""
    return f"""<section class="slide bullets">
      <div class="pad"><h2>{title}</h2>{f'<p class="lead">{subtitle}</p>' if subtitle else ''}<ul>{lis}</ul></div>
      {img}</section>"""


def render_deck_html(
    pitch: Pitch,
    project_title: str | None = None,
    *,
    standalone: bool = True,
    export: bool = False,
) -> str:
    """Rend le deck en HTML. `export=True` = mode capture (Playwright) :
    slides flush (pas de fond gris, pas d'ombre, pas de zoom-fit) — chaque
    slide occupe EXACTEMENT 960x540, prête à être capturée telle quelle.
    """
    t = TEMPLATES.get(pitch.template_id, TEMPLATES["base"])
    slides = pitch.slides or []
    if not slides:
        slides = [{"layout": "cover", "title": project_title or pitch.title or "Ton deck", "subtitle": "Génère ton deck pour démarrer."}]
    body = "".join(_slide(s, t, i) for i, s in enumerate(slides))

    deck_layout = (
        ".deck { display:flex; flex-direction:column; }"
        ".slide { width:960px; height:540px; background:var(--bg); overflow:hidden; display:flex; position:relative; }"
        "body { background: var(--bg); }"
        if export
        else ".deck { display:flex; flex-direction:column; gap:20px; padding:20px; align-items:center; }"
        ".slide { width:960px; height:540px; background:var(--bg); border-radius:14px; overflow:hidden;"
        " box-shadow:0 6px 24px rgba(20,16,40,.12); display:flex; position:relative; }"
        "body { background:#E9E7F0; }"
    )

    css = f"""
    :root {{ --ink:{t['ink']}; --accent:{t['accent']}; --bg:{t['bg']}; --muted:{t['muted']}; --band:{t['band']}; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:'Segoe UI',Roboto,system-ui,sans-serif; color:var(--ink); }}
    {deck_layout}
    .pad {{ padding:56px 64px; width:100%; display:flex; flex-direction:column; justify-content:center; }}
    h1 {{ font-size:52px; line-height:1.05; font-weight:800; }}
    h2 {{ font-size:38px; font-weight:800; margin-bottom:18px; }}
    .lead {{ font-size:22px; color:var(--muted); margin-top:10px; }}
    .eyebrow {{ color:var(--accent); font-size:13px; letter-spacing:2px; font-weight:800; text-transform:uppercase; }}
    ul {{ list-style:none; display:flex; flex-direction:column; gap:14px; margin-top:8px; }}
    li {{ font-size:24px; padding-left:28px; position:relative; }}
    li::before {{ content:''; position:absolute; left:0; top:11px; width:12px; height:12px; border-radius:4px; background:var(--accent); }}
    .cover {{ align-items:flex-end; color:#fff; background-size:cover; background-position:center; }}
    .cover-in {{ padding:64px; }} .cover h1 {{ color:#fff; }} .cover .lead {{ color:#ffffffcc; }}
    .stat {{ background:var(--band); align-items:center; justify-content:center; }}
    .stat-in {{ text-align:center; padding:40px; }}
    .big-num {{ font-size:150px; font-weight:800; color:var(--accent); line-height:1; }}
    .stat-label {{ font-size:28px; font-weight:600; margin-top:8px; }}
    .ctx {{ font-size:20px; color:var(--muted); margin-top:18px; max-width:640px; }}
    .chart-wrap {{ flex:1; position:relative; margin-top:16px; min-height:0; }}
    .bullets .b-img {{ width:38%; background-size:cover; background-position:center; }}
    .bullets .pad {{ width:62%; }}
    .image {{ padding:0; }}
    .img-half {{ width:50%; background-size:cover; background-position:center; }}
    .img-txt {{ width:50%; padding:64px; display:flex; flex-direction:column; justify-content:center; }}
    .img-txt p {{ font-size:22px; color:var(--muted); margin-top:12px; }}
    """

    # Zoom-fit : utile en aperçu (largeur variable) ; inutile/gênant en export
    # (Playwright fixe déjà le viewport à la taille exacte d'une slide).
    zoom_fit = (
        ""
        if export
        else """
      function fitDeck() {
        const deck = document.querySelector('.deck');
        if (!deck) return;
        // 960 (slide) + 40 (padding) = 1000 ; on adapte à la largeur dispo (max 1).
        const z = Math.min(1, (document.documentElement.clientWidth) / 1000);
        deck.style.zoom = z;
      }
      window.addEventListener('resize', fitDeck);
      fitDeck();
    """
    )
    # Animation Chart.js désactivée en export : le graphe doit être fini au
    # premier paint, pas de délai à deviner avant la capture Playwright.
    chart_animation = "false" if export else "undefined"

    scripts = f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script>
      {zoom_fit}
      window.addEventListener('load', () => {{
        {'fitDeck();' if not export else ''}
        const canvases = document.querySelectorAll('canvas[data-chart]');
        let pending = canvases.length;
        function done() {{ pending--; if (pending <= 0) document.body.setAttribute('data-deck-ready', '1'); }}
        if (canvases.length === 0) document.body.setAttribute('data-deck-ready', '1');
        canvases.forEach(c => {{
          const d = JSON.parse(c.dataset.chart);
          new Chart(c, {{ type: d.type || 'bar',
            data: {{ labels: d.labels, datasets: [{{ label: '', data: d.values,
              backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
              borderColor: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(), borderWidth: 2, fill: false }}] }},
            options: {{ responsive:true, maintainAspectRatio:false, animation:{chart_animation},
              plugins:{{legend:{{display:false}}}} }} }});
          done();
        }});
      }});
    </script>"""

    inner = f'<div class="deck">{body}</div>'
    if not standalone:
        return f"<style>{css}</style>{inner}{scripts}"
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Deck</title>
<style>{css}</style></head><body>{inner}{scripts}</body></html>"""
