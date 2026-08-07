"""Rapport d'audit d'incohérences — IDX-RAPPORT-02/03/04.

Trame de référence : `docs/kit-audit-retrospectif.md` §3. Quatre règles non négociables, et
elles sont ici des contraintes de code, pas des consignes de rédaction :

1. **Aucune note, aucun classement, aucune recommandation.** Dès qu'on note, on redevient
   contestable et on perd ce qui fait la force du produit : le constat vérifiable.
2. **Toujours dire ce qui n'a PAS été trouvé.** « 273 dossiers sur 300 ne présentent aucune
   incohérence détectée » est la phrase qui distingue un audit d'une machine à accuser.
3. **Toujours énoncer les limites** (§ « ce que nous n'avons pas cherché »). Ça protège
   juridiquement et ça installe la confiance : un auditeur qui dit ses angles morts est plus
   crédible qu'un oracle.
4. **Jamais un constat non relu** — garanti par `review.kept_findings`, qui refuse de produire
   quoi que ce soit tant qu'un constat reste `pending`.

`render_audit_html` est PUR (stdlib) : testable hors-ligne et servable directement au
navigateur. La conversion PDF est isolée dans `render_audit_pdf` (WeasyPrint, extra `pdf`).
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from html import escape

from app.inconsistencies.review import kept_findings

_TYPE_LABELS = {
    "arithmetic": "Arithmétique",
    "temporal": "Temporel",
    "capacity": "Capacité",
    "market": "Marché",
    "internal": "Interne",
    "regulatory": "Réglementaire",
}
_SEVERITY_LABELS = {"high": "Haute", "medium": "Moyenne", "low": "Basse"}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

CLIENT_CSV_COLUMNS = ("dossier", "type", "gravite", "citation_a", "citation_b", "constat")


def _e(value: object) -> str:
    return escape(str(value or ""))


def _label(mapping: dict[str, str], key: str) -> str:
    return mapping.get(key, key or "—")


def _collect(audit: dict) -> tuple[list[dict], dict]:
    """Constats retenus (les plus graves d'abord) et décompte pour la synthèse."""
    published = kept_findings(audit)
    analyses = published.get("analyses", [])

    rows: list[dict] = []
    for analysis in analyses:
        for finding in analysis.get("findings", []):
            rows.append({**finding, "dossier": analysis.get("reference", "")})
    rows.sort(key=lambda row: (_SEVERITY_ORDER.get(str(row.get("severity")), 9), str(row.get("dossier"))))

    failed = [a for a in analyses if a.get("error")]
    analyzed = [a for a in analyses if not a.get("error")]
    stats = {
        "analyzed": len(analyzed),
        "with_findings": sum(1 for a in analyzed if a.get("findings")),
        "clean": sum(1 for a in analyzed if not a.get("findings")),
        "failed": len(failed),
        "not_analyzable": len(audit.get("not_analyzable", [])),
        "by_type": Counter(str(row.get("type")) for row in rows),
    }
    return rows, stats


def _context_line(audit: dict) -> str:
    countries = {
        str((a.get("context") or {}).get("country"))
        for a in audit.get("analyses", [])
        if (a.get("context") or {}).get("country")
    }
    return ", ".join(sorted(countries)) if countries else "non déterminé"


_STYLE = """
:root{--ink:#14181f;--soft:#4b5563;--faint:#7c8794;--rule:#dfe3e8;--paper:#fff;
--high:#a3302a;--medium:#8a5a12;--low:#5f6b7a;--accent:#0b6e6b}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Segoe UI",system-ui,-apple-system,sans-serif;font-size:11pt;line-height:1.55}
.wrap{max-width:760px;margin:0 auto;padding:32px 28px 56px}
h1{font-family:Georgia,"Times New Roman",serif;font-size:23pt;font-weight:400;margin:0 0 4px}
h2{font-family:Georgia,"Times New Roman",serif;font-size:14pt;font-weight:400;
margin:30px 0 12px;padding-bottom:6px;border-bottom:1.5px solid var(--ink)}
.eyebrow{font-size:8.5pt;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
.meta{color:var(--faint);font-size:9.5pt;margin:0 0 4px}
.tally{width:100%;border-collapse:collapse;margin:14px 0 6px}
.tally td{border:1px solid var(--rule);padding:9px 12px;font-size:10.5pt}
.tally td:first-child{color:var(--soft)}
.tally td:last-child{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tally tr.key td{background:#f4f7f6;font-weight:500}
.note{border:1px solid var(--rule);border-left:3px solid var(--accent);
background:#f8fafa;padding:13px 16px;margin:14px 0;font-size:10.5pt}
.note p{margin:0 0 8px}.note p:last-child{margin:0}
.finding{border:1px solid var(--rule);border-left:3px solid var(--low);
padding:13px 16px;margin:12px 0;page-break-inside:avoid}
.finding.high{border-left-color:var(--high)}
.finding.medium{border-left-color:var(--medium)}
.fhead{display:flex;justify-content:space-between;gap:12px;font-size:9pt;
letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin-bottom:9px}
.fhead .sev{font-weight:500}
.fhead .sev.high{color:var(--high)}.fhead .sev.medium{color:var(--medium)}
blockquote{margin:0 0 7px;padding:7px 12px;background:#f6f7f9;border-left:2px solid var(--rule);
font-size:10.5pt;color:var(--ink)}
.verdict{margin:9px 0 0;font-size:10.5pt;color:var(--soft)}
ul{margin:8px 0;padding-left:18px}li{margin-bottom:6px;color:var(--soft)}
.empty{border:1px solid var(--rule);padding:16px;text-align:center;color:var(--soft)}
@media print{.wrap{max-width:none;padding:0}h2{page-break-after:avoid}}
"""


def render_audit_html(audit: dict, *, client: str | None = None, reference: str | None = None) -> str:
    """Rend le rapport. Lève `ReviewError` si un constat n'a pas été tranché par un humain."""
    rows, stats = _collect(audit)
    submitted = stats["analyzed"] + stats["failed"] + stats["not_analyzable"]

    title = _e(client) if client else "Rapport d'audit"
    head = [
        '<div class="wrap">',
        '<p class="eyebrow">Audit d\'incohérences · rapport</p>',
        f"<h1>{title}</h1>",
        f'<p class="meta">Lot de {submitted} dossier(s) · contexte détecté : {_e(_context_line(audit))}</p>',
    ]
    if reference:
        head.append(f'<p class="meta">Référence : {_e(reference)}</p>')

    # --- A. Synthèse. La ligne « sans incohérence » est mise en avant : c'est elle qui fait
    # la différence entre un audit et une machine à accuser.
    tally = [
        "<h2>Synthèse</h2>",
        '<table class="tally">',
        f"<tr><td>Dossiers soumis</td><td>{submitted}</td></tr>",
        f"<tr><td>Dossiers analysés</td><td>{stats['analyzed']}</td></tr>",
        f"<tr><td>Présentant au moins une incohérence</td><td>{stats['with_findings']}</td></tr>",
        f'<tr class="key"><td>Ne présentant aucune incohérence détectée</td><td>{stats["clean"]}</td></tr>',
    ]
    if stats["not_analyzable"]:
        tally.append(
            f"<tr><td>Non analysables (dossier vide ou trop court)</td>"
            f"<td>{stats['not_analyzable']}</td></tr>"
        )
    if stats["failed"]:
        tally.append(f"<tr><td>En échec technique</td><td>{stats['failed']}</td></tr>")
    tally.append(f"<tr><td>Constats retenus</td><td>{len(rows)}</td></tr>")
    tally.append("</table>")

    if stats["by_type"]:
        breakdown = " · ".join(
            f"{_label(_TYPE_LABELS, key)} : {count}" for key, count in stats["by_type"].most_common()
        )
        tally.append(f'<p class="meta">Répartition : {_e(breakdown)}</p>')

    # --- B. Comment lire.
    how = [
        "<h2>Comment lire ce rapport</h2>",
        '<div class="note">',
        "<p>Nous constatons, nous ne jugeons pas. Chaque constat cite <strong>deux passages du "
        "dossier</strong> qui ne peuvent pas être vrais en même temps. Vous vérifiez vous-même, "
        "sans avoir à nous croire sur parole.</p>",
        "<p><strong>L'absence de constat ne signifie pas qu'un dossier est bon</strong> — seulement "
        "qu'il est cohérent avec lui-même.</p>",
        "</div>",
    ]

    # --- C. Les constats.
    body = ["<h2>Constats</h2>"]
    if not rows:
        body.append('<div class="empty">Aucune incohérence retenue sur ce lot.</div>')
    for row in rows:
        severity = str(row.get("severity", "low"))
        body += [
            f'<div class="finding {_e(severity)}">',
            '<div class="fhead">',
            f"<span>Dossier {_e(row.get('dossier'))} · {_e(_label(_TYPE_LABELS, str(row.get('type'))))}</span>",
            f'<span class="sev {_e(severity)}">Gravité {_e(_label(_SEVERITY_LABELS, severity))}</span>',
            "</div>",
            f"<blockquote>{_e(row.get('quote_a'))}</blockquote>",
            f"<blockquote>{_e(row.get('quote_b'))}</blockquote>",
            f'<p class="verdict">{_e(row.get("explanation"))}</p>',
            "</div>",
        ]

    # --- D. Limites. Section OBLIGATOIRE : elle protège et elle crédibilise.
    limits = [
        "<h2>Ce que nous n'avons pas cherché</h2>",
        "<ul>",
        "<li>Nous n'évaluons <strong>pas la qualité</strong> du projet, ni ses chances de succès.</li>",
        "<li>Nous ne vérifions <strong>rien contre des sources externes</strong> : ni registre, ni "
        "bilan, ni terrain. Une affirmation fausse mais cohérente avec le reste du dossier "
        "<strong>ne sera pas détectée</strong>.</li>",
        "<li>Nous ne détectons que les incohérences <strong>internes au texte fourni</strong>.</li>",
        "</ul>",
    ]

    method = [
        "<h2>Méthode</h2>",
        "<ul>",
        "<li>Détection automatique du pays et de la devise, pour juger prix et obligations dans le bon contexte.</li>",
        "<li>Analyse en deux passes complémentaires par dossier.</li>",
        "<li>Chaque citation est <strong>recoupée automatiquement dans le dossier source</strong> : "
        "un extrait introuvable est écarté.</li>",
        "<li><strong>Chaque constat a été relu et validé manuellement</strong> avant publication.</li>",
        "</ul>",
        "</div>",
    ]

    document_title = f"Rapport d'audit — {title}" if client else "Rapport d'audit"
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        f"<title>{document_title}</title>"
        f"<style>{_STYLE}</style></head><body>"
        + "".join(head + tally + how + body + limits + method)
        + "</body></html>"
    )


def render_audit_pdf(html: str) -> bytes:
    """Convertit le rapport en PDF (WeasyPrint, extra `pdf` — comme le bilan porteur)."""
    from weasyprint import HTML  # import paresseux : la dépendance est optionnelle

    return HTML(string=html).write_pdf()


def to_client_csv(audit: dict) -> str:
    """Export tableur des constats retenus, pour l'évaluateur qui veut trier lui-même."""
    rows, _ = _collect(audit)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CLIENT_CSV_COLUMNS, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "dossier": row.get("dossier", ""),
                "type": _label(_TYPE_LABELS, str(row.get("type"))),
                "gravite": _label(_SEVERITY_LABELS, str(row.get("severity"))),
                "citation_a": row.get("quote_a", ""),
                "citation_b": row.get("quote_b", ""),
                "constat": row.get("explanation", ""),
            }
        )
    return buffer.getvalue()
