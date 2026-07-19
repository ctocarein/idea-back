"""Ancrage des citations — un constat non recoupable ne doit jamais atteindre le rapport."""

from __future__ import annotations

from app.inconsistencies.dedup import Finding, InconsistencyType, Severity
from app.inconsistencies.verification import is_grounded, keep_grounded, quote_is_grounded

NARRATIVE = (
    "LivraisonPlus. Je livre pour des restaurants et des petits commerces à Abidjan depuis "
    "deux ans. Nous faisons environ 40 courses par jour, facturées 1 500 FCFA en moyenne au "
    "commerçant, sur lesquelles nous prenons 20 %."
)

# Le bloc de contexte injecté dans le prompt — le modèle l'a cité comme s'il venait du récit.
CONTEXT_LINE = "Le revenu mensuel d'un ménage modeste ≈ environ 100 000 à 150 000 XOF."


def _finding(quote_a: str, quote_b: str) -> Finding:
    return Finding(
        type=InconsistencyType.MARKET,
        quote_a=quote_a,
        quote_b=quote_b,
        explanation="…",
        severity=Severity.HIGH,
    )


class TestQuoteIsGrounded:
    def test_extrait_litteral_est_ancre(self) -> None:
        assert quote_is_grounded("facturées 1 500 FCFA en moyenne au commerçant", NARRATIVE)

    def test_casse_accents_et_ponctuation_ne_font_pas_echouer(self) -> None:
        assert quote_is_grounded("FACTUREES 1500 FCFA, en moyenne au commercant !", NARRATIVE)

    def test_bloc_de_contexte_nest_pas_ancre(self) -> None:
        # Le défaut mesuré : le modèle cite sa donnée de référence comme un passage du dossier.
        assert not quote_is_grounded(CONTEXT_LINE, NARRATIVE)

    def test_calcul_fabrique_nest_pas_ancre(self) -> None:
        # « 1 200 × 5 000 = 6 000 000 » est un raisonnement, pas une citation : il va dans
        # l'explication, jamais dans une citation.
        assert not quote_is_grounded("1 200 producteurs × 5 000 FCFA = 6 000 000 FCFA", NARRATIVE)

    def test_citation_trop_courte_est_rejetee(self) -> None:
        # Trop courte pour qu'un lecteur la retrouve : sans valeur d'audit.
        assert not quote_is_grounded("Abidjan", NARRATIVE)

    def test_citation_vide_est_rejetee(self) -> None:
        assert not quote_is_grounded("", NARRATIVE)


class TestIsGrounded:
    def test_les_deux_citations_doivent_etre_ancrees(self) -> None:
        good = _finding("Je livre pour des restaurants et des petits commerces à Abidjan", "nous prenons 20 %")
        assert is_grounded(good, NARRATIVE)

    def test_une_seule_citation_ancree_ne_suffit_pas(self) -> None:
        half = _finding("Nous faisons environ 40 courses par jour", CONTEXT_LINE)
        assert not is_grounded(half, NARRATIVE)


class TestKeepGrounded:
    def test_separe_les_recevables_des_ecartes(self) -> None:
        ok = _finding("Nous faisons environ 40 courses par jour", "nous prenons 20 %")
        ko = _finding(CONTEXT_LINE, "Nous faisons environ 40 courses par jour")
        kept, dropped = keep_grounded([ok, ko], NARRATIVE)
        assert kept == [ok]
        assert dropped == [ko]

    def test_les_ecartes_sont_remontes_et_non_perdus(self) -> None:
        # Un taux d'écart qui grimpe signale une dérive du prompt ou du modèle : l'appelant
        # doit pouvoir le journaliser, jamais l'ignorer en silence.
        ko = _finding(CONTEXT_LINE, CONTEXT_LINE)
        kept, dropped = keep_grounded([ko], NARRATIVE)
        assert kept == []
        assert len(dropped) == 1

    def test_liste_vide(self) -> None:
        assert keep_grounded([], NARRATIVE) == ([], [])
