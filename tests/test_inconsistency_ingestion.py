"""Ingestion d'un lot — le désordre des dossiers réels, absorbé sans perte silencieuse."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from app.inconsistencies.ingestion import (
    MIN_NARRATIVE_LENGTH,
    IngestionError,
    anonymous_reference,
    load,
    load_csv,
    load_directory,
    normalize_narrative,
)

LONG = (
    "AgriLink met en relation les producteurs de cacao avec des acheteurs vérifiés. "
    "Nous avons lancé il y a un an et 1 200 producteurs sont abonnés à 5 000 FCFA par mois, "
    "pour environ 400 000 FCFA de revenu mensuel. L'équipe est composée de deux personnes."
)


class TestNormalisation:
    def test_retours_chariot_windows_et_mac(self) -> None:
        assert normalize_narrative("a\r\nb\rc") == "a\nb\nc"

    def test_paragraphes_preserves(self) -> None:
        # Les paragraphes portent la structure du dossier et les citations doivent y rester
        # retrouvables : on ne les écrase pas.
        assert normalize_narrative("Un\n\nDeux") == "Un\n\nDeux"

    def test_lignes_vides_excessives_reduites(self) -> None:
        assert normalize_narrative("Un\n\n\n\n\nDeux") == "Un\n\nDeux"

    def test_espaces_multiples_et_tabulations(self) -> None:
        assert normalize_narrative("Un    deux\tTrois") == "Un deux Trois"

    def test_caracteres_de_controle_issus_de_pdf(self) -> None:
        assert normalize_narrative("Un\x0bdeux\x00trois") == "Undeuxtrois"

    def test_bom_retire(self) -> None:
        assert normalize_narrative("﻿Projet") == "Projet"


class TestReferenceAnonyme:
    def test_stable_dun_run_a_lautre(self) -> None:
        assert anonymous_reference("dossier-042") == anonymous_reference("dossier-042")

    def test_distincte_par_source(self) -> None:
        assert anonymous_reference("a") != anonymous_reference("b")

    def test_ne_contient_pas_la_source(self) -> None:
        assert "MartinDupont" not in anonymous_reference("MartinDupont")


def _csv(rows: list[list[str]], delimiter: str = ",") -> str:
    """Écrit un CSV correctement échappé, comme le ferait un vrai export."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


class TestCsv:
    def _write(self, tmp_path: Path, content: str, name: str = "lot.csv", encoding: str = "utf-8") -> Path:
        path = tmp_path / name
        path.write_text(content, encoding=encoding)
        return path

    def test_colonne_detectee_automatiquement(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, _csv([["id", "description"], ["A-1", LONG]]))
        result = load_csv(path)
        assert len(result.dossiers) == 1
        assert result.dossiers[0].reference == "A-1"

    def test_separateur_point_virgule_des_exports_excel(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, _csv([["id", "presentation du projet"], ["A-1", LONG]], delimiter=";"))
        result = load_csv(path)
        assert len(result.dossiers) == 1

    def test_encodage_windows_cp1252(self, tmp_path: Path) -> None:
        # Cas fréquent : un export Excel français n'est pas en UTF-8.
        path = self._write(
            tmp_path, _csv([["id", "description"], ["A-1", f"{LONG} Café"]]), encoding="cp1252"
        )
        result = load_csv(path)
        assert "Café" in result.dossiers[0].narrative

    def test_recit_non_echappe_est_recolle_et_non_tronque(self, tmp_path: Path) -> None:
        # Export mal formé : le récit contient des virgules sans guillemets. Sans garde, il
        # serait AMPUTÉ en silence — et l'audit rendrait moins de constats sans que personne
        # ne s'en aperçoive.
        path = self._write(tmp_path, f"id,description\nA-1,{LONG}\n")
        result = load_csv(path)
        assert len(result.dossiers) == 1
        assert result.dossiers[0].narrative.endswith("deux personnes.")

    def test_ligne_mal_echappee_hors_derniere_colonne_est_ecartee(self, tmp_path: Path) -> None:
        # Ici on ne peut pas recoller sans risque : on écarte AVEC motif plutôt que d'analyser
        # un texte douteux.
        path = self._write(tmp_path, f"id,description,statut\nA-1,{LONG},actif\n")
        result = load_csv(path)
        assert result.dossiers == []
        assert "tronqué" in result.skipped[0].reason

    def test_colonne_avec_suffixe_est_reconnue(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, _csv([["id", "presentation_du_projet_2024"], ["A-1", LONG]]))
        assert len(load_csv(path).dossiers) == 1

    def test_colonne_explicite_prime(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, _csv([["description", "autre"], ["ignoré", LONG]]))
        result = load_csv(path, narrative_column="autre")
        assert result.dossiers[0].narrative.startswith("AgriLink")

    def test_colonne_introuvable_donne_un_message_actionnable(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "colonne_a,colonne_b\n1,2\n")
        with pytest.raises(IngestionError) as exc:
            load_csv(path)
        # Le message doit lister les colonnes disponibles, pas juste échouer.
        assert "colonne_a" in str(exc.value)
        assert "--column" in str(exc.value)

    def test_reference_generee_si_absente(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, f"description\n{LONG}\n")
        assert load_csv(path).dossiers[0].reference == "lot-0001"

    def test_recit_trop_court_est_ecarte_avec_motif(self, tmp_path: Path) -> None:
        # Un texte court ne peut pas se contredire : le déclarer « propre » serait trompeur.
        path = self._write(tmp_path, f"id,description\nA-1,trop court\nA-2,{LONG}\n")
        result = load_csv(path)
        assert len(result.dossiers) == 1
        assert len(result.skipped) == 1
        assert result.skipped[0].reference == "A-1"
        assert str(MIN_NARRATIVE_LENGTH) in result.skipped[0].reason

    def test_recit_vide_est_ecarte(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "id,description\nA-1,\n")
        assert load_csv(path).skipped[0].reason == "récit vide"

    def test_total_vu_couvre_retenus_et_ecartes(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, f"id,description\nA-1,court\nA-2,{LONG}\n")
        assert load_csv(path).total_seen == 2

    def test_anonymisation_optionnelle(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, f"id,description\nMartinDupont,{LONG}\n")
        result = load_csv(path, anonymize=True)
        assert result.dossiers[0].reference.startswith("D-")
        assert "MartinDupont" not in result.dossiers[0].reference

    def test_secteur_repris_du_fichier(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, f"id,secteur,description\nA-1,agritech,{LONG}\n")
        assert load_csv(path).dossiers[0].category == "agritech"


class TestRepertoire:
    def test_un_fichier_par_dossier(self, tmp_path: Path) -> None:
        (tmp_path / "dossier-a.txt").write_text(LONG, encoding="utf-8")
        (tmp_path / "dossier-b.md").write_text(LONG, encoding="utf-8")
        result = load_directory(tmp_path)
        assert [d.reference for d in result.dossiers] == ["dossier-a", "dossier-b"]

    def test_fichiers_non_texte_ignores(self, tmp_path: Path) -> None:
        (tmp_path / "dossier.txt").write_text(LONG, encoding="utf-8")
        (tmp_path / "photo.png").write_bytes(b"\x89PNG")
        assert len(load_directory(tmp_path).dossiers) == 1

    def test_repertoire_sans_texte_est_une_erreur_claire(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionError):
            load_directory(tmp_path)


class TestLoad:
    def test_dispatch_repertoire(self, tmp_path: Path) -> None:
        (tmp_path / "d.txt").write_text(LONG, encoding="utf-8")
        assert len(load(tmp_path).dossiers) == 1

    def test_dispatch_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "lot.csv"
        path.write_text(f"id,description\nA-1,{LONG}\n", encoding="utf-8")
        assert len(load(path).dossiers) == 1

    def test_chemin_absent(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionError, match="Introuvable"):
            load(tmp_path / "nulle-part.csv")

    def test_format_non_pris_en_charge(self, tmp_path: Path) -> None:
        path = tmp_path / "lot.xlsx"
        path.write_bytes(b"PK")
        with pytest.raises(IngestionError, match="Format non pris en charge"):
            load(path)
