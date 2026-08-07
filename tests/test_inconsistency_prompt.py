"""Prompts de détection d'incohérences — contrat de sortie et adaptation au contexte."""

from __future__ import annotations

import pytest

from app.inconsistencies.dedup import InconsistencyType, parse_analysis
from app.llm.prompt import (
    INCONSISTENCY_GROUPS,
    build_context_prompt,
    build_inconsistency_prompt,
)

NARRATIVE = "Nous vendons 1 200 abonnements à 5 000 FCFA, pour 400 000 FCFA de revenu mensuel."


def _prompt(group: str = "quantitative", context: dict | None = None) -> str:
    return build_inconsistency_prompt(
        narrative=NARRATIVE,
        group=group,
        category="agritech",
        archetype="field",
        context=context,
    )


class TestGroupes:
    def test_les_deux_groupes_couvrent_tous_les_types_sans_recouvrement(self) -> None:
        # Un type oublié ne serait jamais cherché ; un type en double coûterait un appel
        # et produirait des constats concurrents à dédupliquer.
        covered = [t for types in INCONSISTENCY_GROUPS.values() for t in types]
        assert sorted(covered, key=lambda t: t.value) == sorted(InconsistencyType, key=lambda t: t.value)
        assert len(covered) == len(set(covered))

    @pytest.mark.parametrize("group", list(INCONSISTENCY_GROUPS))
    def test_chaque_type_du_groupe_a_sa_procedure(self, group: str) -> None:
        prompt = _prompt(group)
        for type_ in INCONSISTENCY_GROUPS[group]:
            assert f"- {type_.value} :" in prompt
            assert "PROCÉDURE" in prompt

    def test_les_types_des_autres_groupes_ne_fuient_pas(self) -> None:
        prompt = _prompt("quantitative")
        for type_ in INCONSISTENCY_GROUPS["textual"]:
            assert f"- {type_.value} :" not in prompt

    def test_groupe_inconnu_leve(self) -> None:
        with pytest.raises(KeyError):
            _prompt("farfelu")


class TestContrat:
    def test_les_cles_json_sont_en_anglais(self) -> None:
        prompt = _prompt()
        for key in ("analysis", "found", "quote_a", "quote_b", "explanation", "severity"):
            assert key in prompt
        # Les anciennes clés françaises ne doivent plus être demandées au modèle. On vise la
        # forme CITÉE (`"explication"`) et non le mot : la prose française du prompt emploie
        # légitimement « explication », « gravité » ou « passage ».
        for legacy in ('"passage_a"', '"passage_b"', '"gravite"', '"explication"', '"analyse"'):
            assert legacy not in prompt

    def test_la_liste_sappelle_contradictions_et_pas_findings(self) -> None:
        # Régression mesurée : renommer `contradictions` en `findings` a fait exploser les faux
        # positifs. « contradictions » contraint sémantiquement — on ne peut pas y ranger une
        # vérification qui passe ; « findings » est neutre et accueille n'importe quelle
        # observation. Le nom du champ EST une garde anti-faux-positif.
        prompt = _prompt()
        assert '"contradictions"' in prompt
        assert '"findings"' not in prompt

    def test_le_bloc_de_contexte_est_declare_non_citable(self) -> None:
        # Le modèle a cité le repère de pouvoir d'achat comme s'il venait du récit.
        prompt = _prompt(context={"country": "Sénégal", "currency": "XOF", "modest_household_income": "80000"})
        assert "ne fait PAS partie du" in prompt
        assert "Ne le cite JAMAIS" in prompt

    def test_le_modele_ne_doit_pas_rendre_compte_de_sa_methode(self) -> None:
        # Défaut mesuré trois fois : le modèle rapporte son propre raisonnement comme un
        # constat (« le calcul est cohérent », « ce repère ne s'applique pas au B2B »).
        # Toute consigne sur laquelle il peut rendre compte doit dire « et n'en dis rien ».
        prompt = _prompt()
        assert "NE RENDS JAMAIS COMPTE DE TA MÉTHODE" in prompt
        assert "le SILENCE" in prompt

    def test_les_arrondis_declares_sont_tolerés(self) -> None:
        # Un porteur qui écrit « environ » arrondit : sans cette tolérance, le détecteur
        # produirait un faux positif sur presque tous les dossiers réels.
        prompt = _prompt("quantitative")
        assert "à peu près" in prompt
        assert "arrondi" in prompt

    def test_le_recit_est_injecte(self) -> None:
        assert NARRATIVE in _prompt()

    def test_la_regle_anti_faux_positif_est_presente(self) -> None:
        # C'est la propriété commerciale non négociable : sans elle, le contrôle propre casse.
        prompt = _prompt()
        assert "un MANQUE d'information n'est PAS une contradiction" in prompt
        assert "n'est PAS" in prompt and "FAIBLESSE" in prompt


class TestContexte:
    def test_sans_contexte_le_modele_est_prie_de_ne_pas_juger_le_pouvoir_dachat(self) -> None:
        prompt = _prompt(context=None)
        assert "pays indéterminé" in prompt
        assert "Ne juge PAS le pouvoir d'achat" in prompt

    def test_contexte_vide_equivaut_a_pas_de_contexte(self) -> None:
        assert "pays indéterminé" in _prompt(context={"country": None})

    def test_le_contexte_detecte_est_injecte_avec_son_repere(self) -> None:
        prompt = _prompt(
            context={"country": "France", "currency": "EUR", "modest_household_income": "1200 EUR"}
        )
        assert "pays = France" in prompt
        assert "devise = EUR" in prompt
        assert "1200 EUR" in prompt

    def test_repere_de_revenu_absent_reste_lisible(self) -> None:
        prompt = _prompt(context={"country": "Sénégal", "currency": "XOF"})
        assert "non déterminé" in prompt


class TestPromptContexte:
    def test_demande_des_cles_anglaises_et_interdit_dinventer(self) -> None:
        prompt = build_context_prompt(narrative=NARRATIVE)
        for key in ("country", "currency", "signals", "modest_household_income"):
            assert key in prompt
        assert "n'invente pas" in prompt
        assert NARRATIVE in prompt


class TestParsingDeLaSortie:
    def test_la_sortie_attendue_se_parse(self) -> None:
        payload = {
            "analysis": [
                {"type": "arithmetic", "found": False, "findings": []},
                {
                    "type": "market",
                    "found": True,
                    "findings": [
                        {
                            "quote_a": "Notre cible, ce sont les familles les plus modestes du quartier",
                            "quote_b": "L'abonnement est à 149 € par mois",
                            "explanation": "prix incompatible avec la cible",
                            "severity": "high",
                        }
                    ],
                },
            ]
        }
        findings = parse_analysis(payload)
        assert len(findings) == 1
        assert findings[0].type is InconsistencyType.MARKET

    def test_les_entrees_vides_sont_normales(self) -> None:
        # Le modèle DOIT se prononcer sur chaque type, y compris pour ne rien signaler.
        payload = {"analysis": [{"type": t.value, "found": False, "findings": []} for t in InconsistencyType]}
        assert parse_analysis(payload) == []

    def test_sortie_malformee_ne_leve_pas(self) -> None:
        assert parse_analysis({}) == []
        assert parse_analysis({"analysis": None}) == []
        assert parse_analysis({"analysis": ["bruit"]}) == []
