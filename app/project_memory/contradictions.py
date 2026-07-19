"""Pont entre le détecteur d'incohérences et la mémoire projet — IDX-MEM-02.

La chaîne aval existe depuis `0020_project_memory` et n'a jamais servi : collecte des items
`CONTRADICTION`, chute de confiance (`contradiction_gap = 0.5`), remontée dans l'état de
dimension. Le détecteur n'était pas absent — il n'avait pas de capteur. Ce module est le capteur.

**Correspondance type d'incohérence → dimension Radar.** `ProjectMemoryItem` exige une
dimension `d1..d12` : il faut donc rattacher chaque constat à un axe. Le choix n'est pas neutre,
puisque c'est la confiance de CET axe qui va chuter. Cinq types se rattachent naturellement ;
`internal` est le fourre-tout et reste une approximation assumée (voir ci-dessous).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import UUID

from app.core.logging import get_logger
from app.inconsistencies.dedup import Finding, InconsistencyType
from app.project_memory.domain import default_state_for_item
from app.project_memory.models import MemoryItemType, ProvenanceType
from app.project_memory.repository import ProjectMemoryRepository

logger = get_logger("project_memory")

# Une contradiction oppose souvent deux affirmations relevant d'axes DIFFÉRENTS : la rattacher
# à un seul est intrinsèquement réducteur. On retient l'axe que le constat met le plus en cause.
DIMENSION_BY_TYPE: dict[InconsistencyType, str] = {
    InconsistencyType.ARITHMETIC: "d6",  # Modèle économique — revenus et marges déclarés
    InconsistencyType.MARKET: "d4",  # Marché — cible et accessibilité
    InconsistencyType.CAPACITY: "d10",  # Équipe & Compétences — moyens face aux prétentions
    InconsistencyType.TEMPORAL: "d11",  # Niveau d'avancement — ancienneté et historique
    InconsistencyType.REGULATORY: "d12",  # Risques & Freins — obligations niées
    # `internal` est générique. Les cas observés portaient majoritairement sur des prétentions
    # de traction non étayées (« 15 000 utilisateurs » vs « nos premiers pilotes »), d'où d7.
    # APPROXIMATION ASSUMÉE : à affiner en faisant qualifier l'axe par le modèle, ce qui
    # exigera de re-mesurer le corpus.
    InconsistencyType.INTERNAL: "d7",  # Traction & Preuves
}


def deduplication_key(finding: Finding) -> str:
    """Clé stable : re-lancer un diagnostic ne doit pas empiler les mêmes contradictions."""
    material = "|".join([finding.type.value, finding.quote_a, finding.quote_b])
    return f"contradiction:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


async def persist_findings(
    memory: ProjectMemoryRepository,
    *,
    project_id: UUID,
    findings: Sequence[Finding],
) -> int:
    """Écrit les constats en mémoire projet. Retourne le nombre d'items réellement créés.

    À appeler AVANT la projection : le projecteur relit la mémoire pour construire l'état des
    dimensions, donc une contradiction écrite après lui resterait invisible jusqu'au prochain run.
    """
    created = 0
    for finding in findings:
        key = deduplication_key(finding)
        if await memory.get_by_deduplication_key(project_id, key) is not None:
            continue  # déjà connue : un re-scoring ne duplique pas les constats
        await memory.create(
            project_id=project_id,
            dimension=DIMENSION_BY_TYPE[finding.type],
            item_type=MemoryItemType.CONTRADICTION,
            evidence_state=default_state_for_item(MemoryItemType.CONTRADICTION),
            statement=finding.explanation,
            provenance_type=ProvenanceType.NARRATIVE,
            created_by_id=None,  # produit par le système, pas par un utilisateur
            deduplication_key=key,
            # Les DEUX citations sont l'essentiel : sans elles le porteur lit une accusation
            # sans preuve. Elles voyagent dans `attributes` jusqu'au contrat d'API.
            attributes={
                "inconsistency_type": finding.type.value,
                "severity": finding.severity.value,
                "quote_a": finding.quote_a,
                "quote_b": finding.quote_b,
            },
        )
        created += 1

    if findings:
        logger.info(
            "contradictions_persisted",
            project_id=str(project_id),
            detected=len(findings),
            created=created,
        )
    return created
