"""Accès données Academy — sessions de module et fiches de besoin."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.academy.models import GuidedSession, NeedFiche


class AcademyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Sessions de module ---

    async def create_session(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        section: str,
        dimension: str | None = None,
        phase: str = "context",
    ) -> GuidedSession:
        gs = GuidedSession(
            owner_id=owner_id,
            project_id=project_id,
            section=section,
            dimension=dimension,
            phase=phase,
            turns=[],
        )
        self.session.add(gs)
        await self.session.flush()
        return gs

    async def get_session(self, session_id: UUID) -> GuidedSession | None:
        return await self.session.get(GuidedSession, session_id)

    async def get_module_session(self, owner_id: UUID, dimension: str) -> GuidedSession | None:
        """Retourne la session de module la plus récente pour un porteur/dimension."""
        result = await self.session.execute(
            select(GuidedSession)
            .where(
                GuidedSession.owner_id == owner_id,
                GuidedSession.dimension == dimension,
            )
            .order_by(GuidedSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_started_dimensions(self, owner_id: UUID) -> list[tuple[str, str, UUID, int | None]]:
        """Retourne [(dimension, phase, session_id, axis_score_after)] par module."""
        result = await self.session.execute(
            select(
                GuidedSession.dimension,
                GuidedSession.phase,
                GuidedSession.id,
                GuidedSession.axis_score_after,
            )
            .where(
                GuidedSession.owner_id == owner_id,
                GuidedSession.dimension.is_not(None),
            )
            .order_by(GuidedSession.created_at.desc())
        )
        seen: set[str] = set()
        rows = []
        for dim, phase, sid, after in result:
            if dim not in seen:
                seen.add(dim)
                rows.append((dim, phase, sid, after))
        return rows

    # --- Fiches de besoin ---

    async def create_fiche(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        session_id: UUID | None,
        dimension: str,
        need_type: str,
        title: str,
        description: str,
        details: dict,
    ) -> NeedFiche:
        fiche = NeedFiche(
            owner_id=owner_id,
            project_id=project_id,
            session_id=session_id,
            dimension=dimension,
            need_type=need_type,
            title=title,
            description=description,
            details=details,
        )
        self.session.add(fiche)
        await self.session.flush()
        return fiche

    async def list_fiches_for_owner(self, owner_id: UUID) -> list[NeedFiche]:
        result = await self.session.execute(
            select(NeedFiche).where(NeedFiche.owner_id == owner_id).order_by(NeedFiche.created_at.desc())
        )
        return list(result.scalars())

    async def list_fiches_for_session(self, session_id: UUID) -> list[NeedFiche]:
        result = await self.session.execute(
            select(NeedFiche).where(NeedFiche.session_id == session_id).order_by(NeedFiche.created_at)
        )
        return list(result.scalars())

    async def get_fiche(self, fiche_id: UUID) -> NeedFiche | None:
        return await self.session.get(NeedFiche, fiche_id)

    async def get_fiche_by_token_hash(self, token_hash: str) -> NeedFiche | None:
        result = await self.session.execute(select(NeedFiche).where(NeedFiche.share_token_hash == token_hash))
        return result.scalar_one_or_none()
