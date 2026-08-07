"""Accès données documents."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: UUID,
        project_id: UUID | None,
        filename: str,
        content_type: str,
        size: int,
        object_key: str,
    ) -> Document:
        doc = Document(
            owner_id=owner_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            size=size,
            object_key=object_key,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def list_for_owner(self, owner_id: UUID) -> list[Document]:
        result = await self.session.execute(
            select(Document).where(Document.owner_id == owner_id).order_by(Document.created_at.desc())
        )
        return list(result.scalars())

    async def list_for_project(self, project_id: UUID) -> list[Document]:
        result = await self.session.execute(
            select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())
        )
        return list(result.scalars())

    async def confirm(self, doc: Document) -> None:
        doc.status = DocumentStatus.CONFIRMED
        await self.session.flush()

    async def delete(self, doc: Document) -> None:
        await self.session.delete(doc)
        await self.session.flush()
