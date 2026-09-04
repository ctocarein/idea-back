"""Tests du rapport de pré-diagnostic (rendu HTML pur, hors-ligne) — grille v2 + sections."""

from __future__ import annotations

from app.reports.pdf import reading, reading_overall, render_bilan_html
from app.scoring.constants import AXES, GRID_VERSION_ACTIVE, PILLARS

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


def _html(
    report: dict | None = _REPORT,
    actions: list | None = _ACTIONS,
    *,
    sector_calibrated: bool = True,
) -> str:
    return render_bilan_html(
        project_title="Tontine+",
        category="finance",
        grid_pillars=PILLARS,
        grid_axes=AXES,
        scores=_SCORES,
        pillar_scores=_PILLARS,
        overall=62,  # global NORMALISÉ /100, servi par le back
        scale_max=10,  # échelle d'une dimension
        sector_calibrated=sector_calibrated,
        grid_version=GRID_VERSION_ACTIVE,
        generated_at="23/06/2026",
        n_passes=3,
        confidence=0.86,
        report=report,
        next_actions=actions,
    )


def test_reading_bands_ten_scale() -> None:
    # Lecture d'une DIMENSION, /10.
    assert reading(8) == ("Fort", "strong")
    assert reading(6) == ("Moyen", "watch")
    assert reading(3) == ("Faible", "fragile")


def test_reading_overall_bands_hundred_scale() -> None:
    """Lecture du GLOBAL, /100 — mêmes bandes transposées (SPEC C3).

    Confondre les deux échelles affichait « Faible » sur un projet à 60.
    """
    assert reading_overall(80) == ("Fort", "strong")
    assert reading_overall(62) == ("Moyen", "watch")
    assert reading_overall(30) == ("Faible", "fragile")


def test_overall_rendered_as_served_without_conversion() -> None:
    # Le nombre affiché est EXACTEMENT celui que le back a persisté (SPEC C3).
    html = _html()
    assert "62<span>%</span>" in html
    assert "62/100" in html


def test_method_note_explains_pillar_vs_overall_divergence() -> None:
    # La divergence pilier/global est expliquée à l'écran, pas laissée à la déduction (C5).
    html = _html()
    assert "ne s&#x27;additionnent pas au total" in html or "ne s'additionnent pas au total" in html


def test_uncalibrated_sector_is_stated_in_the_bilan() -> None:
    # Neutralité assumée ET dite (C2).
    assert "non calibrée" in _html(sector_calibrated=False)
    assert "non calibrée" not in _html(sector_calibrated=True)


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
