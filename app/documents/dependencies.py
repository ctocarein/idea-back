"""Assemblage du service documents (storage injecté)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.storage import get_storage
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService


def get_document_service(session: AsyncSession = Depends(get_session)) -> DocumentService:
    return DocumentService(DocumentRepository(session), get_storage())
