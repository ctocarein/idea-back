"""Rapport d'audit — les règles de la trame sont des contraintes de code, pas des consignes."""

from __future__ import annotations

from html import escape

import pytest

from app.inconsistencies.report import render_audit_html, to_client_csv
from app.inconsistencies.review import Decision, ReviewError, apply_decisions, build_rows

QUOTE_A = "1 200 producteurs sont abonnés à 5 000 FCFA par mois"
QUOTE_B = "environ 400 000 FCFA de chiffre d'affaires mensuel"


def _finding(type_: str = "arithmetic", severity: str = "high", quote_a: str = QUOTE_A) -> dict:
    return {
        "type": type_,
        "severity": severity,
        "quote_a": quote_a,
        "quote_b": QUOTE_B,
        "explanation": "1200 × 5000 = 6 000 000, pas 400 000.",
    }


RAW = {
    "not_analyzable": [{"reference": "D-99", "reason": "récit vide"}],
    "analyses": [
        {
            "reference": "D-01",
            "context": {"country": "Côte d'Ivoire", "currency": "XOF"},
            "findings": [_finding(), _finding("market", "low", "Notre cible, les familles modestes")],
        },
        {"reference": "D-02", "context": {"country": "France"}, "findings": []},
        {"reference": "D-03", "context": None, "findings": [], "error": "toutes les passes ont échoué"},
    ],
}


def _reviewed(*, keep: set[str] | None = None) -> dict:
    rows = build_rows(RAW)
    keep = keep if keep is not None else {row.finding_id for row in rows}
    return apply_decisions(
        RAW, {row.finding_id: (Decision.KEEP if row.finding_id in keep else Decision.DROP, "") for row in rows}
    )


class TestGardeDePublication:
    def test_rapport_refuse_si_un_constat_nest_pas_relu(self) -> None:
        # La garantie du produit, câblée : impossible de rendre un rapport non relu.
        with pytest.raises(ReviewError, match="non tranché"):
            render_audit_html(RAW)

    def test_les_constats_rejetes_napparaissent_pas(self) -> None:
        rows = build_rows(RAW)
        html = render_audit_html(_reviewed(keep={rows[0].finding_id}))
        assert QUOTE_A in html
        assert "Notre cible, les familles modestes" not in html


class TestSynthese:
    def test_le_nombre_de_dossiers_sans_incoherence_est_affiche(self) -> None:
        # LA phrase qui distingue un audit d'une machine à accuser.
        html = render_audit_html(_reviewed())
        assert "Ne présentant aucune incohérence détectée" in html

    def test_les_dossiers_non_analysables_sont_declares(self) -> None:
        # Rien ne disparaît en silence : 30 soumis ≠ 30 analysés.
        assert "Non analysables" in render_audit_html(_reviewed())

    def test_les_echecs_techniques_sont_declares(self) -> None:
        assert "En échec technique" in render_audit_html(_reviewed())

    def test_le_contexte_detecte_est_expose_donc_contestable(self) -> None:
        html = render_audit_html(_reviewed())
        assert "Côte d&#x27;Ivoire" in html or "Côte d'Ivoire" in html
        assert "France" in html


class TestConstats:
    def test_chaque_constat_porte_ses_deux_citations(self) -> None:
        # Sans les deux, le client ne peut pas vérifier : le constat n'a aucune valeur.
        # Les citations sont échappées (elles viennent de dossiers clients et d'un LLM).
        html = render_audit_html(_reviewed())
        assert escape(QUOTE_A) in html
        assert escape(QUOTE_B) in html

    def test_les_plus_graves_en_premier(self) -> None:
        html = render_audit_html(_reviewed())
        assert html.index("Gravité Haute") < html.index("Gravité Basse")

    def test_lot_sans_constat_retenu_reste_un_rapport_valide(self) -> None:
        # Cas fréquent et parfaitement livrable : il ne doit pas être traité comme une erreur.
        html = render_audit_html(_reviewed(keep=set()))
        assert "Aucune incohérence retenue" in html
        assert "Ne présentant aucune incohérence détectée" in html


class TestReglesNonNegociables:
    def test_la_section_des_limites_est_toujours_presente(self) -> None:
        # Elle protège juridiquement et crédibilise : jamais optionnelle.
        html = render_audit_html(_reviewed())
        assert "Ce que nous n&#x27;avons pas cherché" in html or "Ce que nous n'avons pas cherché" in html
        assert "ne sera pas détectée" in html

    def test_la_relecture_humaine_est_annoncee_au_client(self) -> None:
        assert "relu et validé manuellement" in render_audit_html(_reviewed())

    def test_aucune_note_aucun_classement_aucune_recommandation(self) -> None:
        # Dès qu'on note, on redevient contestable et on perd le constat vérifiable.
        html = render_audit_html(_reviewed()).lower()
        for interdit in ("score", "recommandation", "nous recommandons", "classement", "/10"):
            assert interdit not in html

    def test_le_contenu_du_modele_est_echappe(self) -> None:
        # Les citations viennent de dossiers clients et d'un LLM : jamais de HTML brut.
        audit = {"analyses": [{"reference": "D-01", "findings": [_finding(quote_a="<script>alert(1)</script>")]}]}
        rows = build_rows(audit)
        reviewed = apply_decisions(audit, {rows[0].finding_id: (Decision.KEEP, "")})
        html = render_audit_html(reviewed)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestExportClient:
    def test_colonnes_en_clair_pour_le_tableur(self) -> None:
        csv_text = to_client_csv(_reviewed())
        assert csv_text.splitlines()[0] == "dossier;type;gravite;citation_a;citation_b;constat"

    def test_seuls_les_constats_valides_sont_exportes(self) -> None:
        assert len(to_client_csv(_reviewed(keep=set())).splitlines()) == 1

    def test_libelles_lisibles_et_non_techniques(self) -> None:
        assert "Arithmétique" in to_client_csv(_reviewed())
