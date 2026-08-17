"""Classement sectoriel par l'extraction : le LLM propose, il ne décide pas.

La règle défendue ici : une sortie hors vocabulaire ne doit JAMAIS devenir une
valeur stockée. Elle retombe sur `AUTRE` avec une confiance nulle, ce qui déclenche
la question au porteur — au lieu d'inscrire une hallucination dans le corpus.
"""

from __future__ import annotations

from app.core.sector import Sector, SectorSource
from app.diagnostics.extraction import _parse_sector, _sector_options
from app.llm.prompt import EXTRACTION_PROMPT_VERSION, build_extraction_prompt
from app.scoring.constants import AXES


def test_prompt_options_cover_the_whole_closed_list() -> None:
    options = _sector_options()
    assert {option["key"] for option in options} == {sector.value for sector in Sector}
    assert all(option["label"] and option["hint"] for option in options)


def test_prompt_injects_the_keys_and_the_json_contract() -> None:
    prompt = build_extraction_prompt(idea="je vends de l'attiéké", axes=AXES, sectors=_sector_options())
    assert "SECTEUR :" in prompt
    assert "- agro (" in prompt
    assert "attiéké" in prompt  # l'exemple guide le classement
    assert '"sector_confidence"' in prompt
    assert '"sector_candidates"' in prompt


def test_prompt_without_sectors_stays_unchanged() -> None:
    """Le paramètre est optionnel : les appels existants ne changent pas de forme."""
    prompt = build_extraction_prompt(idea="mon idée", axes=AXES)
    assert "SECTEUR :" not in prompt


def test_valid_output_is_kept_with_its_confidence() -> None:
    proposal = _parse_sector(
        {"sector": "agro", "sector_confidence": 0.82, "sector_candidates": ["commerce", "restauration"]},
        model="mistral-small-latest",
        prompt_version=EXTRACTION_PROMPT_VERSION,
    )
    assert proposal.sector is Sector.AGRO
    assert proposal.label == "Agriculture & agro-transformation"
    assert proposal.confidence == 0.82
    assert proposal.candidates == [Sector.COMMERCE, Sector.RESTAURATION]
    assert proposal.source is SectorSource.LLM
    assert proposal.model == "mistral-small-latest"
    assert proposal.prompt_version == EXTRACTION_PROMPT_VERSION
    assert proposal.needs_confirmation is True


def test_hallucinated_key_falls_back_with_zero_confidence() -> None:
    """Confiance nulle : on demandera au porteur plutôt que de deviner."""
    proposal = _parse_sector(
        {"sector": "spacetech", "sector_confidence": 0.99},
        model="m",
        prompt_version="v",
    )
    assert proposal.sector is Sector.AUTRE
    assert proposal.confidence == 0.0


def test_missing_sector_falls_back() -> None:
    proposal = _parse_sector({}, model="m", prompt_version="v")
    assert proposal.sector is Sector.AUTRE
    assert proposal.confidence == 0.0
    assert proposal.candidates == []


def test_alias_from_the_model_is_resolved() -> None:
    """Le modèle peut répondre `fintech` : la table d'alias le ramène sur `finance`."""
    proposal = _parse_sector({"sector": "fintech", "sector_confidence": 0.7}, model="m", prompt_version="v")
    assert proposal.sector is Sector.FINANCE


def test_confidence_is_clamped_and_never_crashes() -> None:
    for raw, expected in [(1.7, 1.0), (-0.5, 0.0), ("pas un nombre", 0.0), (None, 0.0)]:
        proposal = _parse_sector({"sector": "agro", "sector_confidence": raw}, model="m", prompt_version="v")
        assert proposal.confidence == expected


def test_candidates_are_cleaned_and_capped() -> None:
    """Trois options au porteur, pas treize : on garde 2 candidats, sans le secteur retenu."""
    proposal = _parse_sector(
        {
            "sector": "agro",
            "sector_candidates": ["agro", "inventé", "commerce", "restauration", "sante"],
        },
        model="m",
        prompt_version="v",
    )
    assert proposal.candidates == [Sector.COMMERCE, Sector.RESTAURATION]
