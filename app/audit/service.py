"""Service d'audit — un helper unique appelé dans la transaction de l'action.

`record(...)` n'ouvre PAS de transaction et ne commite PAS : il ajoute la ligne à la
session courante (autobegin). C'est l'appelant (le service métier) qui commite —
l'audit est donc persisté atomiquement avec l'action, ou pas du tout.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


def _to_jsonable(value: Any) -> Any:
    # Normalise une valeur (enum, UUID, etc.) pour le stockage JSONB.
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "value"):  # Enum
        return {"value": value.value}
    return {"value": str(value)}


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity: str,
        entity_id: UUID | None = None,
        old_value: Any = None,
        new_value: Any = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        # N.B. : pas de commit ici — on s'inscrit dans la transaction de l'appelant.
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                old_value=_to_jsonable(old_value),
                new_value=_to_jsonable(new_value),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.flush()
