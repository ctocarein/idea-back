"""Service deck de pitch — upload direct + parsing → slides typées.

Le deck a besoin de ses octets pour être parsé : on l'uploade donc directement (multipart),
contrairement à la data-room (DOC-01 presigned). Les octets bruts peuvent être archivés dans
MinIO (best-effort, pour les vignettes en V2) ; le texte par slide est persisté en base.
"""

from __future__ import annotations

from uuid import UUID

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.storage import ObjectStorage
from app.iam.dependencies import AuthContext, guard_owner_access
from app.pitchsim.models import SlideKind
from app.pitchsim.parser import ALLOWED_DECK_TYPES, MAX_MAIN_SLIDES, parse_deck
from app.pitchsim.repository import PitchDeckRepository
from app.pitchsim.schemas import DeckOut, SlideOut

MAX_DECK_BYTES = 20 * 1024 * 1024  # 20 Mo


class PitchDeckService:
    def __init__(self, repo: PitchDeckRepository, storage: ObjectStorage | None) -> None:
        self.repo = repo
        self.storage = storage
        self.session = repo.session

    def _validate(self, content_type: str, data: bytes) -> None:
        if content_type not in ALLOWED_DECK_TYPES:
            raise BusinessRuleError(f"Type de deck non supporté : {content_type} (PDF ou PPTX).")
        if not data:
            raise BusinessRuleError("Fichier vide.")
        if len(data) > MAX_DECK_BYTES:
            raise BusinessRuleError("Deck trop volumineux (max 20 Mo).")

    async def create_deck(
        self,
        ctx: AuthContext,
        *,
        title: str,
        project_id: UUID | None,
        content_type: str,
        data: bytes,
    ) -> DeckOut:
        self._validate(content_type, data)
        slides = parse_deck(content_type, data)[:MAX_MAIN_SLIDES]  # deck principal court
        if not slides:
            raise BusinessRuleError("Aucune slide détectée dans le fichier.")
        deck = await self.repo.create_deck(owner_id=ctx.user.id, project_id=project_id, title=title)
        await self.repo.add_slides(deck.id, SlideKind.MAIN, slides)
        await self.session.commit()
        return await self._deck_out(deck.id, title, project_id)

    async def add_slides(
        self,
        ctx: AuthContext,
        deck_id: UUID,
        *,
        kind: SlideKind,
        content_type: str,
        data: bytes,
    ) -> DeckOut:
        if kind == SlideKind.MAIN:
            raise BusinessRuleError("Le deck principal se crée via POST /pitchsim/decks.")
        deck = await self.repo.get_deck(deck_id)
        if deck is None:
            raise NotFoundError("pitch_deck")
        guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
        self._validate(content_type, data)
        slides = parse_deck(content_type, data)
        await self.repo.add_slides(deck_id, kind, slides)
        await self.session.commit()
        return await self._deck_out(deck.id, deck.title, deck.project_id)

    async def get_deck(self, ctx: AuthContext, deck_id: UUID) -> DeckOut:
        deck = await self.repo.get_deck(deck_id)
        if deck is None:
            raise NotFoundError("pitch_deck")
        guard_owner_access(owner_id=deck.owner_id, ctx=ctx)
        return await self._deck_out(deck.id, deck.title, deck.project_id)

    async def _deck_out(self, deck_id: UUID, title: str, project_id: UUID | None) -> DeckOut:
        rows = await self.repo.slides_for_deck(deck_id)
        return DeckOut(
            id=deck_id,
            title=title,
            project_id=project_id,
            slides=[SlideOut.model_validate(r) for r in rows],
        )
