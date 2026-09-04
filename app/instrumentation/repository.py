"""Lectures analytiques sur les événements (tableau de bord d'apprentissage)."""

from __future__ import annotations

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diagnostics.models import DiagnosticDraft
from app.iam.models import User
from app.instrumentation.models import Event


class InstrumentationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def counts_by_name(self) -> dict[str, int]:
        result = await self.session.execute(select(Event.name, func.count()).group_by(Event.name))
        return {name: int(count) for name, count in result.all()}

    async def distinct_actors_for(self, name: str) -> int:
        result = await self.session.execute(select(func.count(distinct(Event.actor_id))).where(Event.name == name))
        return int(result.scalar_one())

    # --- Diagnostic en cours : la donnée qui n'existait nulle part ------------
    #
    # Le taux d'abandon en cours de saisie et l'étape où il survient ne se déduisent
    # d'aucune autre donnée. Pour un produit dont le seul signal utilisateur validé porte
    # précisément sur le moment du diagnostic, c'est la mesure la plus coûteuse à ne pas
    # avoir — et la moins chère à obtenir, une fois les brouillons persistés.

    async def draft_completion(self) -> tuple[int, int]:
        """(brouillons créés, brouillons soumis). Le ratio est le taux de complétion."""
        result = await self.session.execute(
            select(
                func.count(),
                func.count(case((DiagnosticDraft.submitted_at.isnot(None), 1))),
            )
        )
        created, submitted = result.one()
        return int(created), int(submitted)

    async def draft_dropoff_by_dimension(self) -> dict[str, int]:
        """Où la saisie s'arrête, chez ceux qui n'ont jamais soumis.

        Si une dimension concentre les abandons, c'est sa FORMULATION qui est en cause —
        signal produit directement actionnable.
        """
        result = await self.session.execute(
            select(DiagnosticDraft.last_dimension, func.count())
            .where(DiagnosticDraft.submitted_at.is_(None))
            .group_by(DiagnosticDraft.last_dimension)
            .order_by(func.count().desc())
        )
        return {(dim or "inconnue"): int(count) for dim, count in result.all()}

    async def draft_median_resume_delay_seconds(self) -> float | None:
        """Délai médian entre première et dernière saisie, chez ceux qui sont revenus.

        Médiane et non moyenne : quelques brouillons vieux de plusieurs semaines écrasent
        une moyenne et rendraient l'indicateur illisible.
        """
        delay = func.extract("epoch", DiagnosticDraft.updated_at - DiagnosticDraft.created_at)
        result = await self.session.execute(
            select(func.percentile_cont(0.5).within_group(delay.asc())).where(
                DiagnosticDraft.updated_at > DiagnosticDraft.created_at
            )
        )
        value = result.scalar_one_or_none()
        return round(float(value), 1) if value is not None else None

    async def counts_by_prop(self, name: str, key: str) -> dict[str, int]:
        """Répartition d'un événement par une clé de ses `props`.

        Sert aux motifs d'annulation de rappel : sans eux, on saurait qu'un rappel n'est
        pas parti mais pas pourquoi — et « déjà revenu » (le produit marche) appelle une
        décision opposée à « désabonné » (le mail dérange).
        """
        prop = Event.props[key].astext
        result = await self.session.execute(select(prop, func.count()).where(Event.name == name).group_by(prop))
        return {(value or "inconnu"): int(count) for value, count in result.all()}

    async def opted_out_users(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.reminders_opt_out.is_(True))
        )
        return int(result.scalar_one())
