"""Accès données brouillons de diagnostic.

Séparé de `DiagnosticRepository` : le brouillon n'a rien à voir avec le pipeline de
diagnostic, et les mélanger inviterait à faire fuiter de la logique métier vers lui.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diagnostics.models import DiagnosticDraft, EntryMode


class DiagnosticDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, owner_id: UUID) -> DiagnosticDraft | None:
        """Le brouillon VIVANT du porteur. Les brouillons soumis restent en base pour
        l'analyse, mais ne sont plus servis : ils ne sont pas reprenables."""
        result = await self.session.execute(
            select(DiagnosticDraft).where(
                DiagnosticDraft.owner_id == owner_id,
                DiagnosticDraft.submitted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        owner_id: UUID,
        answers: dict,
        payload: dict,
        mode: EntryMode,
        last_dimension: str | None,
    ) -> DiagnosticDraft:
        """Crée ou remplace le brouillon actif. IDEMPOTENT : l'appel est répété à chaque
        sauvegarde, et le corps porte l'état complet — pas un delta, donc rien à diverger."""
        draft = await self.get_active(owner_id)
        if draft is None:
            draft = DiagnosticDraft(owner_id=owner_id)
            self.session.add(draft)
        draft.answers = answers
        draft.payload = payload
        draft.mode = mode
        draft.last_dimension = last_dimension
        await self.session.flush()
        # `created_at`/`updated_at` sont calculés PAR LE SERVEUR (server_default / onupdate) :
        # après le flush, SQLAlchemy les marque à recharger et le moindre accès déclencherait
        # un SELECT paresseux — impossible hors contexte greenlet, donc une erreur au moment
        # de sérialiser la réponse. On les charge explicitement, tout de suite.
        await self.session.refresh(draft)
        return draft

    async def delete_active(self, owner_id: UUID) -> bool:
        draft = await self.get_active(owner_id)
        if draft is None:
            return False
        await self.session.delete(draft)
        await self.session.flush()
        return True

    async def mark_submitted(self, owner_id: UUID) -> DiagnosticDraft | None:
        """Clôt le brouillon actif. NO-OP si aucun n'existe : une soumission ne doit jamais
        échouer à cause d'un brouillon absent (parcours direct, upload de document)."""
        draft = await self.get_active(owner_id)
        if draft is None:
            return None
        draft.submitted_at = datetime.now(UTC)
        await self.session.flush()
        return draft

    async def purge_stale(self, *, ttl_days: int) -> int:
        """Supprime les brouillons ABANDONNÉS au-delà du TTL. Les soumis sont conservés :
        ils portent la trajectoire de saisie, qui est la donnée qu'on cherchait."""
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        result = await self.session.execute(
            delete(DiagnosticDraft).where(
                DiagnosticDraft.submitted_at.is_(None),
                DiagnosticDraft.updated_at < cutoff,
            )
        )
        return int(result.rowcount or 0)

    async def list_for_owner(self, owner_id: UUID) -> list[DiagnosticDraft]:
        # Export RGPD : tout ce que le porteur a laissé, soumis compris.
        result = await self.session.execute(
            select(DiagnosticDraft)
            .where(DiagnosticDraft.owner_id == owner_id)
            .order_by(DiagnosticDraft.created_at.desc())
        )
        return list(result.scalars())
