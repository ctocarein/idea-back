"""Routes d'audit (back-office) — journal filtrable."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.audit.dependencies import get_audit_repo
from app.audit.repository import AuditRepository
from app.audit.schemas import AuditLogOut
from app.iam.dependencies import AuthContext, require
from app.iam.permissions import Permission

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    actor_id: UUID | None = None,
    action: str | None = None,
    entity: str | None = None,
    ctx: AuthContext = Depends(require(Permission.AUDIT_READ)),
    audit: AuditRepository = Depends(get_audit_repo),
) -> list[AuditLogOut]:
    rows = await audit.list_filtered(actor_id=actor_id, action=action, entity=entity)
    return [AuditLogOut.model_validate(a) for a in rows]
