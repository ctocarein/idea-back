"""Routes documents — upload presigned (flow B du diagnostic + data room)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.documents.dependencies import get_document_service
from app.documents.schemas import ConfirmIn, DocumentOut, UploadUrlIn, UploadUrlOut
from app.documents.service import DocumentService
from app.iam.dependencies import AuthContext, get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload-url", response_model=UploadUrlOut)
async def request_upload_url(
    body: UploadUrlIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: DocumentService = Depends(get_document_service),
) -> UploadUrlOut:
    # Émet une URL PUT signée (5 min). Le client uploade ensuite directement sur MinIO.
    return await svc.request_upload_url(ctx, body)


@router.post("/confirm", response_model=DocumentOut)
async def confirm_upload(
    body: ConfirmIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: DocumentService = Depends(get_document_service),
) -> DocumentOut:
    return await svc.confirm_upload(ctx, body.document_id)


@router.get("", response_model=list[DocumentOut])
async def list_my_documents(
    ctx: AuthContext = Depends(get_current_user),
    svc: DocumentService = Depends(get_document_service),
) -> list[DocumentOut]:
    return await svc.list_mine(ctx)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    ctx: AuthContext = Depends(get_current_user),
    svc: DocumentService = Depends(get_document_service),
) -> None:
    await svc.delete(ctx, document_id)
