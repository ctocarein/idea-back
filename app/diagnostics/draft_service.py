"""Service brouillon de diagnostic — un STOCKAGE, pas un objet métier.

Aucun score, aucun statut projet, aucune notification ne s'adosse à un brouillon. C'est la
règle qui l'empêche de devenir une seconde source de vérité, et elle doit tenir dans le
temps : dès qu'une logique métier s'y accroche, deux états divergent.

Le brouillon n'existe qu'après création de compte. Le parcours anonyme reste sur le
`localStorage` du visiteur — c'est le comportement conforme, pas un pis-aller : persister
une saisie anonyme côté serveur, ce serait stocker des données personnelles avant
consentement.
"""

from __future__ import annotations

from app.core.errors import NotFoundError
from app.diagnostics.draft_repository import DiagnosticDraftRepository
from app.diagnostics.schemas import DiagnosticDraftIn, DiagnosticDraftOut
from app.iam.dependencies import AuthContext


class DiagnosticDraftService:
    def __init__(self, drafts: DiagnosticDraftRepository) -> None:
        self.drafts = drafts
        self.session = drafts.session

    async def save(self, ctx: AuthContext, data: DiagnosticDraftIn) -> DiagnosticDraftOut:
        # Pas de `guard_owner_access` : la propriété n'est pas vérifiée, elle est IMPOSÉE —
        # le porteur ne peut écrire que sous son propre `owner_id`, jamais désigner un autre.
        draft = await self.drafts.upsert(
            owner_id=ctx.user.id,
            answers=data.answers,
            payload=data.payload,
            mode=data.mode,
            last_dimension=data.last_dimension,
        )
        await self.session.commit()
        return DiagnosticDraftOut.model_validate(draft)

    async def get(self, ctx: AuthContext) -> DiagnosticDraftOut:
        draft = await self.drafts.get_active(ctx.user.id)
        if draft is None:
            raise NotFoundError("Aucun diagnostic en cours.")
        return DiagnosticDraftOut.model_validate(draft)

    async def discard(self, ctx: AuthContext) -> None:
        # Abandon EXPLICITE du porteur (« Recommencer »). Aucune suppression implicite
        # ailleurs : un brouillon ne disparaît que sur demande ou à la purge du TTL.
        await self.drafts.delete_active(ctx.user.id)
        await self.session.commit()
