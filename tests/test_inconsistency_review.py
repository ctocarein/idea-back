"""Relecture humaine — la garantie que rien ne se publie sans avoir été vu."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.inconsistencies.review import (
    Decision,
    ReviewError,
    apply_decisions,
    build_rows,
    ensure_publishable,
    finding_id,
    kept_findings,
    pending_count,
    read_review,
    rejection_notes,
    to_csv,
    write_review,
)

QUOTE_A = "1 200 producteurs sont abonnés à 5 000 FCFA par mois"
QUOTE_B = "environ 400 000 FCFA de chiffre d'affaires mensuel"


def _finding(type_: str = "arithmetic", severity: str = "high", quote_a: str = QUOTE_A) -> dict:
    return {
        "type": type_,
        "severity": severity,
        "quote_a": quote_a,
        "quote_b": QUOTE_B,
        "explanation": "1200 × 5000 = 6 000 000, pas 400 000.",
        "merged_types": [],
    }


def _audit(*analyses: dict) -> dict:
    return {"generated_at": "2026-07-19T00:00:00Z", "analyses": list(analyses)}


AUDIT = _audit(
    {"reference": "D-01", "findings": [_finding(), _finding("market", "low", "Notre cible modeste")]},
    {"reference": "D-02", "findings": []},
)


class TestIdentifiant:
    def test_stable_entre_deux_appels(self) -> None:
        assert finding_id("D-01", _finding()) == finding_id("D-01", _finding())

    def test_distinct_par_dossier(self) -> None:
        assert finding_id("D-01", _finding()) != finding_id("D-02", _finding())

    def test_distinct_par_citation(self) -> None:
        assert finding_id("D-01", _finding()) != finding_id("D-01", _finding(quote_a="autre chose"))


class TestExport:
    def test_une_ligne_par_constat(self) -> None:
        assert len(build_rows(AUDIT)) == 2

    def test_les_plus_graves_en_premier(self) -> None:
        # Le relecteur doit rencontrer d'abord ce qui engage le plus la crédibilité du rapport.
        assert [row.severity for row in build_rows(AUDIT)] == ["high", "low"]

    def test_les_deux_citations_sont_dans_le_fichier(self) -> None:
        # Sans elles, l'humain ne peut pas trancher : il validerait à l'aveugle.
        csv_text = to_csv(AUDIT)
        assert QUOTE_A in csv_text
        assert QUOTE_B in csv_text

    def test_separateur_point_virgule_pour_les_tableurs_francophones(self) -> None:
        assert to_csv(AUDIT).splitlines()[0].count(";") == 8

    def test_tout_est_pending_au_depart(self) -> None:
        assert pending_count(AUDIT) == 2

    def test_ecriture_avec_bom_pour_excel(self, tmp_path: Path) -> None:
        path = tmp_path / "relecture.csv"
        assert write_review(path, AUDIT) == 2
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")


class TestRelecture:
    def _reviewed(self, tmp_path: Path, decisions: dict[str, str], notes: dict[str, str] | None = None) -> dict:
        path = tmp_path / "relecture.csv"
        write_review(path, AUDIT)
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        rebuilt = [lines[0]]
        for line in lines[1:]:
            key = line.split(";")[0]
            parts = line.split(";")
            parts[4] = decisions.get(key, "")
            parts[5] = (notes or {}).get(key, "")
            rebuilt.append(";".join(parts))
        path.write_text("\n".join(rebuilt) + "\n", encoding="utf-8-sig")
        return apply_decisions(AUDIT, read_review(path))

    def test_aller_retour_complet(self, tmp_path: Path) -> None:
        rows = build_rows(AUDIT)
        decisions = {rows[0].finding_id: "keep", rows[1].finding_id: "drop"}
        reviewed = self._reviewed(tmp_path, decisions)
        assert pending_count(reviewed) == 0
        assert len(kept_findings(reviewed)["analyses"][0]["findings"]) == 1

    def test_alias_francais_acceptes(self, tmp_path: Path) -> None:
        # Le relecteur tape « oui » / « non » : refuser serait de la pédanterie.
        rows = build_rows(AUDIT)
        reviewed = self._reviewed(tmp_path, {rows[0].finding_id: "oui", rows[1].finding_id: "non"})
        assert pending_count(reviewed) == 0

    def test_decision_incomprise_est_signalee(self, tmp_path: Path) -> None:
        rows = build_rows(AUDIT)
        with pytest.raises(ReviewError, match="non comprise"):
            self._reviewed(tmp_path, {rows[0].finding_id: "peut-être"})

    def test_constat_absent_du_fichier_reste_pending(self, tmp_path: Path) -> None:
        # Ne jamais supposer qu'un constat oublié est validé.
        rows = build_rows(AUDIT)
        reviewed = self._reviewed(tmp_path, {rows[0].finding_id: "keep"})
        assert pending_count(reviewed) == 1

    def test_les_motifs_de_rejet_sont_recuperables(self, tmp_path: Path) -> None:
        # Ils disent POURQUOI le modèle s'est trompé : matière pour corriger le prompt.
        rows = build_rows(AUDIT)
        reviewed = self._reviewed(
            tmp_path,
            {rows[0].finding_id: "keep", rows[1].finding_id: "drop"},
            notes={rows[1].finding_id: "repère B2C appliqué à un prix B2B"},
        )
        assert rejection_notes(reviewed) == [("market", "repère B2C appliqué à un prix B2B")]

    def test_fichier_introuvable(self, tmp_path: Path) -> None:
        with pytest.raises(ReviewError, match="introuvable"):
            read_review(tmp_path / "absent.csv")

    def test_fichier_qui_nest_pas_une_relecture(self, tmp_path: Path) -> None:
        path = tmp_path / "autre.csv"
        path.write_text("a;b\n1;2\n", encoding="utf-8")
        with pytest.raises(ReviewError, match="finding_id"):
            read_review(path)


class TestGarantieDePublication:
    def test_publication_refusee_tant_quun_constat_est_pending(self) -> None:
        # LA garantie du produit : aucun constat ne part chez un client sans avoir été vu.
        with pytest.raises(ReviewError, match="non tranché"):
            ensure_publishable(AUDIT)

    def test_le_message_derreur_dit_quoi_faire(self) -> None:
        with pytest.raises(ReviewError) as exc:
            ensure_publishable(AUDIT)
        assert "keep / drop" in str(exc.value)

    def test_kept_findings_refuse_aussi(self) -> None:
        with pytest.raises(ReviewError):
            kept_findings(AUDIT)

    def test_audit_entierement_rejete_est_publiable_et_vide(self) -> None:
        # Cas réel et acceptable : le modèle s'est trompé partout, le lot est propre.
        rows = build_rows(AUDIT)
        reviewed = apply_decisions(AUDIT, {row.finding_id: (Decision.DROP, "") for row in rows})
        result = kept_findings(reviewed)
        assert all(not analysis["findings"] for analysis in result["analyses"])

    def test_audit_sans_aucun_constat_est_publiable(self) -> None:
        # Un lot entièrement sain n'a rien à relire : il ne doit pas bloquer la publication.
        ensure_publishable(_audit({"reference": "D-01", "findings": []}))
