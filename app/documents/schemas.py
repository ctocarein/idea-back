"""DTO documents — demande d'URL d'upload, confirmation, sortie."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Garde-fous : taille max et types autorisés (un BP / pitch, pas un exécutable).
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 Mo
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "text/plain",
    "image/png",
    "image/jpeg",
}


class UploadUrlIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size: int = Field(gt=0, le=MAX_SIZE_BYTES)
    project_id: UUID | None = None


class UploadUrlOut(BaseModel):
    document_id: UUID
    upload_url: str  # presigned PUT (expire 5 min)
    object_key: str
    expires_in: int = 300


class ConfirmIn(BaseModel):
    document_id: UUID


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    size: int
    status: str
    project_id: UUID | None
    created_at: datetime
