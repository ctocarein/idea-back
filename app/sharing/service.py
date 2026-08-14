"""Service de partage — fiche projet B2B, gated par le consentement, révocable.

La fiche publique est une *projection* du bilan pensée jury/incubateur : score (le credential)
+ synthèse + forces. Jamais les internes (risques détaillés, notes privées).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.errors import BusinessRuleError, NotFoundError
from app.iam.dependencies import AuthContext, guard_owner_access
from app.projects.repository import ProjectRepository
from app.reports.models import Report, ReportStatus
from app.reports.repository import ReportRepository
from app.sharing.models import SHARE_DEFAULT_TTL_DAYS
from app.sharing.repository import ShareRepository
from app.sharing.schemas import ProjectVisibilityOut, SharedProjectOut, ShareOut, ShareStatsOut


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ShareService:
    def __init__(self, repo: ShareRepository, projects: ProjectRepository, reports: ReportRepository) -> None:
        self.repo = repo
        self.projects = projects
        self.reports = reports
        self.session = repo.session

    async def _latest_ready_report(self, project_id: UUID) -> Report | None:
        reports = await self.reports.list_for_project(project_id)
        return next((r for r in reports if r.status == ReportStatus.READY), None)

    async def create_share(self, ctx: AuthContext, project_id: UUID, consent: bool) -> ShareOut:
        if not consent:
            raise BusinessRuleError("Le partage nécessite votre consentement explicite.")
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        if await self._latest_ready_report(project_id) is None:
            raise BusinessRuleError("Aucun bilan prêt à partager.")
        token = secrets.token_urlsafe(24)
        now = datetime.now(UTC)
        await self.repo.create(
            project_id=project_id,
            owner_id=ctx.user.id,
            token_hash=_hash(token),
            consent_at=now,
            expires_at=now + timedelta(days=SHARE_DEFAULT_TTL_DAYS),
        )
        await self.session.commit()
        return ShareOut(token=token, path=f"/shared/{token}")

    async def revoke(self, ctx: AuthContext, project_id: UUID) -> None:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        await self.repo.revoke_for_project(project_id, ctx.user.id)
        await self.session.commit()

    async def list_my_shares(self, ctx: AuthContext) -> list[ShareStatsOut]:
        rows = await self.repo.list_by_owner_with_title(ctx.user.id)
        result = []
        for share, project_title in rows:
            result.append(
                ShareStatsOut(
                    id=share.id,
                    project_id=share.project_id,
                    project_title=project_title,
                    # Le token brut n'est révélé qu'à la création et n'est jamais
                    # persisté. Un lien perdu doit être révoqué puis régénéré.
                    share_url="",
                    is_active=share.is_active,
                    expires_at=share.expires_at,
                    view_count=share.view_count,
                    last_viewed_at=share.last_viewed_at,
                    created_at=share.created_at,
                )
            )
        return result

    async def set_visibility(self, ctx: AuthContext, project_id: UUID, is_public: bool) -> None:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("project")
        guard_owner_access(owner_id=project.owner_id, ctx=ctx)
        await self.projects.set_visibility(project, is_public)
        await self.session.commit()

    async def get_my_project_visibility(self, ctx: AuthContext) -> ProjectVisibilityOut | None:
        project = await self.projects.get_latest_for_owner(ctx.user.id)
        if project is None:
            return None
        return ProjectVisibilityOut(
            project_id=project.id,
            project_title=project.title,
            is_public=project.is_public,
        )

    async def get_fiche(self, token: str) -> SharedProjectOut:
        token_hash = _hash(token)
        share = await self.repo.get_active_by_hash(token_hash)
        if share is None:
            raise NotFoundError("share")  # lien invalide ou révoqué
        project = await self.projects.get_by_id(share.project_id)
        report = await self._latest_ready_report(share.project_id)
        if project is None or report is None:
            raise NotFoundError("fiche")
        # Enregistre la vue (best-effort).
        try:
            await self.repo.increment_view(token_hash)
            await self.session.commit()
        except Exception:  # noqa: BLE001
            await self.session.rollback()
        insights = report.insights or {}
        comprehension = report.comprehension or {}
        strengths = [s.get("text", "") for s in insights.get("strengths", []) if isinstance(s, dict)]
        return SharedProjectOut(
            project_title=project.title,
            sector=project.sector,
            maturity=insights.get("maturity"),
            overall_100=round(float(comprehension.get("overall") or 0) * 10),
            summary=insights.get("summary", ""),
            strengths=[s for s in strengths if s][:3],
        )
