"""Service documents — upload presigned, confirmation, listing, suppression.

Le storage est injecté (testable sans MinIO). L'API ne transporte jamais les octets :
elle émet une URL PUT signée, le client uploade directement, puis confirme.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.storage import ObjectStorage
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    ALLOWED_CONTENT_TYPES,
    DocumentOut,
    UploadUrlIn,
    UploadUrlOut,
)
from app.iam.dependencies import AuthContext, guard_owner_access


class DocumentService:
    def __init__(self, repo: DocumentRepository, storage: ObjectStorage | None) -> None:
        self.repo = repo
        self.storage = storage
        self.session = repo.session

    def _require_storage(self) -> ObjectStorage:
        if self.storage is None:
            raise BusinessRuleError("Stockage de documents non configuré (MinIO).")
        return self.storage

    async def request_upload_url(self, ctx: AuthContext, data: UploadUrlIn) -> UploadUrlOut:
        if data.content_type not in ALLOWED_CONTENT_TYPES:
            raise BusinessRuleError(f"Type de fichier non autorisé : {data.content_type}")
        storage = self._require_storage()
        # Clé objet unique, indépendante de l'id en base (préfixe uuid).
        object_key = f"documents/{uuid4()}/{data.filename}"
        doc = await self.repo.create(
            owner_id=ctx.user.id,
            project_id=data.project_id,
            filename=data.filename,
            content_type=data.content_type,
            size=data.size,
            object_key=object_key,
        )
        url = storage.presigned_put(object_key)
        await self.session.commit()
        return UploadUrlOut(document_id=doc.id, upload_url=url, object_key=object_key)

    async def confirm_upload(self, ctx: AuthContext, document_id: UUID) -> DocumentOut:
        doc = await self.repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundError("document")
        guard_owner_access(owner_id=doc.owner_id, ctx=ctx)
        await self.repo.confirm(doc)
        await self.session.commit()
        return DocumentOut.model_validate(doc)

    async def list_mine(self, ctx: AuthContext) -> list[DocumentOut]:
        rows = await self.repo.list_for_owner(ctx.user.id)
        return [DocumentOut.model_validate(d) for d in rows]

    async def delete(self, ctx: AuthContext, document_id: UUID) -> None:
        doc = await self.repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundError("document")
        guard_owner_access(owner_id=doc.owner_id, ctx=ctx)
        # Suppression de l'objet MinIO best-effort (ne bloque pas la suppression métadonnées).
        if self.storage is not None:
            try:
                self.storage.remove_object(doc.object_key)
            except Exception:  # noqa: BLE001
                pass
        await self.repo.delete(doc)
        await self.session.commit()
