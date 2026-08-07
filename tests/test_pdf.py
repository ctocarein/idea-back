"""Tests du rapport de pré-diagnostic (rendu HTML pur, hors-ligne) — grille v2 + sections."""

from __future__ import annotations

from app.reports.pdf import reading, render_bilan_html
from app.scoring.constants import AXES, GRID_VERSION_V2, PILLARS

_SCORES = {
    "d1": 8,
    "d2": 7,
    "d3": 9,
    "d4": 8,
    "d5": 7,
    "d6": 4,
    "d7": 5,
    "d8": 8,
    "d9": 6,
    "d10": 5,
    "d11": 6,
    "d12": 6,
}
_PILLARS = {"sens": 8, "viabilite": 6, "scalabilite": 6, "execution": 6}

_REPORT = {
    "summary": "Positionnement clair ; la solidité dépend du modèle économique.",
    "maturity": "Prototype",
    "maturity_rationale": "Preuve d'usage amorcée, monétisation non validée.",
    "description": {
        "problem": "Pertes et litiges des tontines manuelles.",
        "solution": "Traçabilité via mobile money.",
        "target_client": "Groupes d'épargne de quartier.",
        "business_model": "Commission par tour de tontine.",
    },
    "strengths": [{"text": "Problème réel et fréquent", "dimension": "d1"}],
    "risks": [{"text": "Unit economics à prouver", "probability": "high", "severity": "critical"}],
    "competition": [{"name": "Acteur A", "type": "direct", "description": "Leader segment", "threat": "high"}],
    "progress": {"stage": "Prototype", "team_size": 3, "customers": 12, "revenue": 0, "funding": 0},
    "verdict": {
        "status": "conditional",
        "label": "Projet à potentiel sous conditions",
        "analysis": "Atouts réels ; la viabilité dépend de la preuve du modèle.",
    },
    "recommendations": [{"priority": 1, "title": "Chiffrer le modèle", "description": "Prix, marge, CAC."}],
    "next_steps": [{"deadline": "1 semaine", "action": "Interviewer 20 clients cibles."}],
}


_ACTIONS = [
    {
        "key": "d6",
        "code": "D6",
        "dimension": "Modèle économique",
        "score": 4,
        "severity": "faible",
        "lever_type": "academy",
        "topic": "modele_economique",
        "label": "Apprends : modèle économique",
        "primary": True,
    },
    {
        "key": "d10",
        "code": "D10",
        "dimension": "Équipe & Compétences",
        "score": 5,
        "severity": "moyen",
        "lever_type": "mentor",
        "topic": "equipe",
        "label": "Fais-toi accompagner : équipe & compétences",
        "primary": False,
    },
]


def _html(report: dict | None = _REPORT, actions: list | None = _ACTIONS) -> str:
    return render_bilan_html(
        project_title="Tontine+",
        category="fintech",
        grid_pillars=PILLARS,
        grid_axes=AXES,
        scores=_SCORES,
        pillar_scores=_PILLARS,
        overall=6,
        scale_max=10,
        grid_version=GRID_VERSION_V2,
        generated_at="23/06/2026",
        n_passes=3,
        confidence=0.86,
        report=report,
        next_actions=actions,
    )


def test_reading_bands_ten_scale() -> None:
    assert reading(8) == ("Fort", "strong")
    assert reading(6) == ("Moyen", "watch")
    assert reading(3) == ("Faible", "fragile")


def test_radar_pillars_and_dims() -> None:
    html = _html()
    assert "Bilan de diagnostic entrepreneurial" in html
    assert "Radar 12 dimensions" in html and "Performance détaillée par axe" in html
    assert "D6 · Modèle économique" in html and "/10" in html
    assert 'class="bar-fill red" style="width:40%"' in html  # d6 = 4 → à renforcer


def test_all_report_sections_render() -> None:
    html = _html()
    assert "Éléments clés" in html and "Commission par tour de tontine." in html
    assert "Score global" in html and "Prototype" in html
    assert "Projet à potentiel sous conditions" in html
    assert "Risques détectés" in html and "Unit economics à prouver" in html
    assert "Recommandations prioritaires" in html and "Chiffrer le modèle" in html
    assert "Prochaines étapes" in html and "Interviewer 20 clients cibles." in html
    assert "Non contractuel" in html  # mentions RGPD


def test_next_step_block_renders_primary_action() -> None:
    html = _html()
    assert "Ta prochaine priorité" in html and "À renforcer en priorité" in html
    assert "Apprends : modèle économique" in html  # action primaire (CTA)
    assert "D6 · Modèle économique — 4/10" in html
    # L'action secondaire apparaît dans la liste.
    assert "Fais-toi accompagner : équipe &amp; compétences" in html


def test_no_actions_no_block() -> None:
    html = _html(actions=[])
    assert "Ta prochaine priorité" not in html


def test_report_optional_degrades_gracefully() -> None:
    # Aucun rapport structuré → le bilan scoré reste complet (sections qualitatives absentes).
    html = _html(report=None)
    assert "Bilan de diagnostic entrepreneurial" in html and "Radar 12 dimensions" in html
    assert "Projet à potentiel sous conditions" not in html
    assert "Données non renseignées" in html and "<li>—</li>" in html


def test_diagnostic_report_schema_tolerant() -> None:
    from app.reports.schemas import DiagnosticReport

    # Champs manquants → défauts ; extra → ignoré ; risque partiel → valeurs par défaut.
    rep = DiagnosticReport.model_validate({"summary": "ok", "inconnu": 1, "risks": [{"text": "r"}]})
    assert rep.summary == "ok"
    assert rep.risks[0].probability == "medium" and rep.risks[0].severity == "medium"
    assert rep.competition == [] and rep.verdict.status == "conditional"
