"""Déduplication des constats — cas réels observés sur le corpus de calibration."""

from __future__ import annotations

from app.inconsistencies.dedup import (
    Finding,
    InconsistencyType,
    Severity,
    deduplicate,
    parse_finding,
    parse_findings,
)

# Citations réelles du cas `coupdepouce-france`, où le modèle a signalé TROIS fois le même
# constat (arithmetic, market, internal) avec les mêmes passages.
TARGET = (
    "Notre cible, ce sont les familles bénéficiaires des minima sociaux, "
    "celles qui ne peuvent pas financer de cours particuliers."
)
PRICE = "L'abonnement est à 149 € par mois et par enfant."


def _finding(type_: InconsistencyType, a: str = TARGET, b: str = PRICE, severity: Severity = Severity.HIGH) -> Finding:
    return Finding(type=type_, quote_a=a, quote_b=b, explanation="…", severity=severity)


def test_triple_signalement_reduit_a_un_seul_constat() -> None:
    findings = [
        _finding(InconsistencyType.ARITHMETIC),
        _finding(InconsistencyType.MARKET),
        _finding(InconsistencyType.INTERNAL),
    ]
    result = deduplicate(findings)
    assert len(result) == 1


def test_le_type_le_plus_verifiable_est_conserve() -> None:
    # `internal` est le fourre-tout : `market` informe davantage l'évaluateur.
    result = deduplicate([_finding(InconsistencyType.INTERNAL), _finding(InconsistencyType.MARKET)])
    assert result[0].type is InconsistencyType.MARKET
    assert result[0].merged_types == (InconsistencyType.INTERNAL,)


def test_arithmetique_prime_sur_tout_le_reste() -> None:
    result = deduplicate([_finding(InconsistencyType.CAPACITY), _finding(InconsistencyType.ARITHMETIC)])
    assert result[0].type is InconsistencyType.ARITHMETIC


def test_citations_inversees_sont_le_meme_constat() -> None:
    # L'ordre A/B n'est pas stable d'une passe à l'autre.
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET, a=TARGET, b=PRICE),
            _finding(InconsistencyType.INTERNAL, a=PRICE, b=TARGET),
        ]
    )
    assert len(result) == 1


def test_citation_tronquee_rejoint_la_citation_complete() -> None:
    # Le modèle tronque à des longueurs variables — cas observé sur `tontine-fintech`.
    truncated = TARGET[:70]
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET, a=TARGET),
            _finding(InconsistencyType.INTERNAL, a=truncated),
        ]
    )
    assert len(result) == 1
    assert result[0].type is InconsistencyType.MARKET


def test_accents_casse_et_ponctuation_nempechent_pas_le_rapprochement() -> None:
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET, a="L'abonnement est à 149 € par mois !"),
            _finding(InconsistencyType.INTERNAL, a="l abonnement est a 149  par mois"),
        ]
    )
    assert len(result) == 1


def test_prefixe_court_ne_fusionne_pas() -> None:
    # Deux constats distincts peuvent partager leurs premiers mots : sans longueur minimale,
    # on fusionnerait à tort et on ferait DISPARAÎTRE un vrai constat.
    longue = "Notre cible, ce sont les familles bénéficiaires des minima sociaux."
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET, a="Notre cible"),
            _finding(InconsistencyType.CAPACITY, a=longue),
        ]
    )
    assert len(result) == 2


def test_constats_reellement_differents_sont_preserves() -> None:
    autre = "Nous avons lancé le service en janvier dernier"
    encore = "Nos trois années de données montrent une progression"
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET),
            _finding(InconsistencyType.TEMPORAL, a=autre, b=encore),
        ]
    )
    assert len(result) == 2


def test_la_gravite_la_plus_haute_du_groupe_est_retenue() -> None:
    result = deduplicate(
        [
            _finding(InconsistencyType.MARKET, severity=Severity.LOW),
            _finding(InconsistencyType.INTERNAL, severity=Severity.HIGH),
        ]
    )
    assert result[0].severity is Severity.HIGH


def test_ordre_dentree_preserve() -> None:
    autre = "Nous avons lancé le service en janvier dernier"
    result = deduplicate(
        [
            _finding(InconsistencyType.TEMPORAL, a=autre, b="Nos trois années de données"),
            _finding(InconsistencyType.MARKET),
        ]
    )
    assert [finding.type for finding in result] == [InconsistencyType.TEMPORAL, InconsistencyType.MARKET]


def test_liste_vide_reste_vide() -> None:
    assert deduplicate([]) == []


class TestParsing:
    def test_cles_francaises_du_modele_sont_traduites(self) -> None:
        finding = parse_finding(
            {
                "type": "réglementaire",
                "passage_a": TARGET,
                "passage_b": PRICE,
                "explication": "raison",
                "gravite": "haute",
            }
        )
        assert finding is not None
        assert finding.type is InconsistencyType.REGULATORY
        assert finding.severity is Severity.HIGH
        assert finding.explanation == "raison"

    def test_cles_anglaises_sont_acceptees(self) -> None:
        finding = parse_finding(
            {"type": "market", "quote_a": TARGET, "quote_b": PRICE, "severity": "low"}
        )
        assert finding is not None
        assert finding.type is InconsistencyType.MARKET
        assert finding.severity is Severity.LOW

    def test_constat_sans_deux_citations_est_ecarte(self) -> None:
        # Sans ses deux citations, un constat n'est pas vérifiable par le client :
        # il n'a aucune valeur d'audit et ne doit jamais atteindre le rapport.
        assert parse_finding({"type": "market", "passage_a": TARGET, "passage_b": "  "}) is None
        assert parse_finding({"type": "market"}) is None

    def test_type_inconnu_retombe_sur_internal(self) -> None:
        finding = parse_finding({"type": "farfelu", "passage_a": TARGET, "passage_b": PRICE})
        assert finding is not None
        assert finding.type is InconsistencyType.INTERNAL

    def test_type_de_repli_utilise_quand_absent(self) -> None:
        finding = parse_finding({"passage_a": TARGET, "passage_b": PRICE}, fallback_type="temporelle")
        assert finding is not None
        assert finding.type is InconsistencyType.TEMPORAL

    def test_parse_findings_ecarte_les_inexploitables(self) -> None:
        raws = [
            {"type": "market", "passage_a": TARGET, "passage_b": PRICE},
            {"type": "market", "passage_a": TARGET},
        ]
        assert len(parse_findings(raws)) == 1
