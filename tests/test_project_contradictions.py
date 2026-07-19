"""Contradictions en mémoire projet — IDX-MEM-02/03/05.

L'enjeu de ces tests n'est pas la qualité de détection (c'est le rôle du banc et du corpus),
mais le fait que la chaîne aval — déjà construite et jamais alimentée — s'allume bien, et
qu'un dossier honnête ne soit JAMAIS pénalisé.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.inconsistencies.dedup import Finding, InconsistencyType, Severity
from app.project_memory.contradictions import (
    DIMENSION_BY_TYPE,
    deduplication_key,
    persist_findings,
)
from app.project_memory.evaluation import build_dimension_projections, select_adaptive_questions
from app.project_memory.models import EvidenceState, MemoryItemType, ProvenanceType

AXES = [
    {"key": f"d{i}", "code": f"D{i}", "label": f"Axe {i}", "pillar": "sens", "guiding_questions": ["Q ?"]}
    for i in range(1, 13)
]


def _finding(type_: InconsistencyType = InconsistencyType.ARITHMETIC, quote_a: str = "A" * 30) -> Finding:
    return Finding(
        type=type_,
        quote_a=quote_a,
        quote_b="B" * 30,
        explanation="1200 × 5000 = 6 000 000, pas 400 000.",
        severity=Severity.HIGH,
    )


class FakeMemoryRepository:
    """Double du dépôt : on vérifie ce qui est ÉCRIT, sans base de données."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self._keys: set[str] = set()

    async def get_by_deduplication_key(self, project_id, key):
        return object() if key in self._keys else None

    async def create(self, **kwargs):
        self.created.append(kwargs)
        if kwargs.get("deduplication_key"):
            self._keys.add(kwargs["deduplication_key"])
        return object()


class FakeItem:
    """Item de mémoire minimal, suffisant pour la projection."""

    def __init__(self, dimension: str, attributes: dict | None = None) -> None:
        self.id = uuid4()
        self.dimension = dimension
        self.item_type = MemoryItemType.CONTRADICTION
        self.evidence_state = EvidenceState.DECLARED
        self.statement = "constat"
        self.attributes = attributes or {}
        self.expires_at = None
        self.is_active = True


class FakeScoreRun:
    def __init__(self) -> None:
        self.id = uuid4()
        self.axes = {f"d{i}": 8 for i in range(1, 13)}
        self.spread = {f"d{i}": 0 for i in range(1, 13)}  # passes parfaitement concordantes
        self.confidence = 1.0
        self.justifications = {}
        self.source = None
        self.created_at = None


class TestCorrespondanceDesDimensions:
    def test_chaque_type_a_une_dimension(self) -> None:
        # Sans correspondance, la persistance lèverait un KeyError en production.
        assert set(DIMENSION_BY_TYPE) == set(InconsistencyType)

    @pytest.mark.parametrize("dimension", DIMENSION_BY_TYPE.values())
    def test_les_dimensions_sont_valides(self, dimension: str) -> None:
        # La table `project_memory_items` porte une contrainte CHECK sur d1..d12.
        assert dimension in {f"d{i}" for i in range(1, 13)}


class TestPersistance:
    @pytest.mark.asyncio
    async def test_un_constat_devient_un_item_contradiction(self) -> None:
        repo = FakeMemoryRepository()
        created = await persist_findings(repo, project_id=uuid4(), findings=[_finding()])
        assert created == 1
        item = repo.created[0]
        assert item["item_type"] is MemoryItemType.CONTRADICTION
        assert item["provenance_type"] is ProvenanceType.NARRATIVE
        assert item["dimension"] == "d6"  # arithmétique → modèle économique

    @pytest.mark.asyncio
    async def test_les_deux_citations_sont_conservees(self) -> None:
        # Sans elles, le porteur lit une accusation sans preuve.
        repo = FakeMemoryRepository()
        await persist_findings(repo, project_id=uuid4(), findings=[_finding()])
        attributes = repo.created[0]["attributes"]
        assert attributes["quote_a"] == "A" * 30
        assert attributes["quote_b"] == "B" * 30
        assert attributes["inconsistency_type"] == "arithmetic"

    @pytest.mark.asyncio
    async def test_aucun_auteur_humain(self) -> None:
        repo = FakeMemoryRepository()
        await persist_findings(repo, project_id=uuid4(), findings=[_finding()])
        assert repo.created[0]["created_by_id"] is None

    @pytest.mark.asyncio
    async def test_un_rescoring_ne_duplique_pas(self) -> None:
        # Le porteur relance un diagnostic : il ne doit pas voir le constat en double.
        repo = FakeMemoryRepository()
        project_id = uuid4()
        await persist_findings(repo, project_id=project_id, findings=[_finding()])
        created = await persist_findings(repo, project_id=project_id, findings=[_finding()])
        assert created == 0
        assert len(repo.created) == 1

    @pytest.mark.asyncio
    async def test_aucun_constat_nécrit_rien(self) -> None:
        repo = FakeMemoryRepository()
        assert await persist_findings(repo, project_id=uuid4(), findings=[]) == 0
        assert repo.created == []

    def test_la_cle_de_deduplication_est_stable(self) -> None:
        assert deduplication_key(_finding()) == deduplication_key(_finding())

    def test_deux_constats_distincts_ont_des_cles_distinctes(self) -> None:
        assert deduplication_key(_finding()) != deduplication_key(_finding(quote_a="C" * 30))


class TestEffetSurLaProjection:
    def _project(self, items: list[FakeItem]):
        return build_dimension_projections(
            axes=AXES, score_run=FakeScoreRun(), memory_items=items, next_actions=[], scale_max=10
        )

    def test_la_confiance_NE_depend_PAS_des_contradictions(self) -> None:
        """Comportement réel, épinglé pour éviter qu'on le suppose à nouveau.

        `_axis_confidence` ne lit QUE l'étendue entre passes de scoring. Le
        `contradiction_gap = 0.5` vit dans `select_adaptive_questions` et ne pilote que la
        priorité des questions. Conséquence : **un dossier contredit garde une confiance
        élevée** — la non-discrimination du Radar n'est donc PAS réparée par S9.
        Décision assumée ou à corriger : voir IDX-MEM-06.
        """
        propre = {p.dimension: p for p in self._project([])}
        contredit = {p.dimension: p for p in self._project([FakeItem("d6")])}
        assert contredit["d6"].confidence == propre["d6"].confidence

    def test_une_contradiction_declenche_une_demande_de_clarification(self) -> None:
        # L'effet RÉEL sur la dimension : elle réclame une information, même bien notée.
        contredit = {p.dimension: p for p in self._project([FakeItem("d6")])}
        assert contredit["d6"].missing_information != ""

    def test_une_contradiction_remonte_la_dimension_dans_les_questions(self) -> None:
        # C'est là qu'agit `contradiction_gap` : la dimension contredite passe devant.
        projections = self._project([FakeItem("d6")])
        questions = select_adaptive_questions(projections, limit=3)
        assert questions[0].dimension == "d6"
        assert questions[0].reason == "contradiction à éclaircir"

    def test_un_dossier_honnete_nest_pas_penalise(self) -> None:
        # Protection non négociable : côté porteur, un faux positif coûte sa confiance.
        contredit = {p.dimension: p for p in self._project([FakeItem("d6")])}
        assert contredit["d4"].contradictions == []
        questions = select_adaptive_questions(self._project([]), limit=3)
        assert all(q.reason != "contradiction à éclaircir" for q in questions)

    def test_les_citations_remontent_dans_le_contrat(self) -> None:
        # L'extension de contrat annoncée au front : quote_a / quote_b sur chaque constat.
        item = FakeItem("d6", {"quote_a": "citation A", "quote_b": "citation B", "severity": "high"})
        projection = {p.dimension: p for p in self._project([item])}["d6"]
        contradiction = projection.contradictions[0]
        assert contradiction["quote_a"] == "citation A"
        assert contradiction["quote_b"] == "citation B"
        assert contradiction["severity"] == "high"

    def test_une_contradiction_sans_attributs_reste_lisible(self) -> None:
        # Contradiction saisie à la main : pas de citations, mais le contrat ne casse pas.
        projection = {p.dimension: p for p in self._project([FakeItem("d6")])}["d6"]
        contradiction = projection.contradictions[0]
        assert contradiction["statement"] == "constat"
        assert "quote_a" not in contradiction
