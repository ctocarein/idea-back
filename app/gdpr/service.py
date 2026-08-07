"""Service RGPD — export (portabilité) + effacement (droit à l'oubli).

Export : toutes les données personnelles du porteur, en JSON. Effacement : suppression du
compte → cascade SQL (projets/diagnostics/bilans/documents…) DANS une transaction, puis nettoyage
best-effort des objets MinIO. L'audit (actor_id non contraint par FK) survit à la suppression.
"""

from __future__ import annotations

from typing import Any

from app.audit.service import AuditService
from app.core.storage import ObjectStorage
from app.documents.repository import DocumentRepository
from app.iam.dependencies import AuthContext
from app.iam.repository import UserRepository
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository


class GdprService:
    def __init__(
        self,
        *,
        users: UserRepository,
        projects: ProjectRepository,
        reports: ReportRepository,
        documents: DocumentRepository,
        auditor: AuditService,
        storage: ObjectStorage | None,
    ) -> None:
        self.users = users
        self.projects = projects
        self.reports = reports
        self.documents = documents
        self.auditor = auditor
        self.storage = storage
        self.session = users.session

    async def export(self, ctx: AuthContext) -> dict[str, Any]:
        u = ctx.user
        projects = await self.projects.list_for_owner(u.id)
        reports = await self.reports.list_for_owner(u.id)
        documents = await self.documents.list_for_owner(u.id)
        return {
            "account": {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "status": u.status.value,
                "consent_at": u.consent_at,
                "created_at": u.created_at,
            },
            "projects": [
                {
                    "id": p.id,
                    "title": p.title,
                    "sector": p.sector,
                    "archetype": p.archetype.value,
                    "stage": p.stage.value,
                    "diagnostic_status": p.diagnostic_status.value,
                    "review_status": p.review_status.value,
                    "created_at": p.created_at,
                }
                for p in projects
            ],
            "reports": [
                {
                    "id": r.id,
                    "project_id": r.project_id,
                    "status": r.status.value,
                    "radar_score": r.radar_score,
                    "created_at": r.created_at,
                }
                for r in reports
            ],
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "status": d.status.value,
                    "created_at": d.created_at,
                }
                for d in documents
            ],
        }

    async def delete_me(self, ctx: AuthContext) -> None:
        user = await self.users.get_by_id(ctx.user.id)
        if user is None:
            return
        # Clés MinIO à nettoyer APRÈS la suppression DB (best-effort).
        object_keys = [d.object_key for d in await self.documents.list_for_owner(user.id)]
        # Audit AVANT suppression (actor_id non contraint par FK → la trace survit).
        await self.auditor.record(actor_id=user.id, action="user.deleted", entity="user", entity_id=user.id)
        await self.session.delete(user)  # cascade SQL (projets, bilans, documents…)
        await self.session.commit()
        if self.storage is not None:
            for key in object_keys:
                try:
                    await self.storage.aremove_object(key)
                except Exception:  # noqa: BLE001
                    pass
