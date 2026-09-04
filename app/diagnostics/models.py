"""Modèle du diagnostic — l'ENTRÉE du porteur (le score/bilan vit dans `reports`).

Deux modes :
  - GUIDED   : le porteur écrit son idée + répond aux questions par catégorie (flow A).
  - DOCUMENT : le porteur uploade un document, extrait par le worker (flow B).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EntryMode(str, Enum):
    GUIDED = "guided"  # "J'ai une idée à explorer"
    DOCUMENT = "document"  # "J'ai déjà un document"


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[EntryMode]
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # Réponses aux questions guidées : { questionId: réponse } (flow A).
    answers: Mapped[dict | None] = mapped_column(JSONB, default=None)
    funding_need: Mapped[int | None] = mapped_column(default=None)  # FCFA
    # Document source (flow B) — l'extraction texte est faite par le worker.
    document_id: Mapped[UUID | None] = mapped_column(default=None)
    consent_at: Mapped[datetime] = mapped_column(server_default=func.now())  # RGPD
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DiagnosticDraft(Base):
    """Saisie EN COURS, côté serveur. Un stockage, jamais un objet métier.

    Le pipeline `_start()` crée projet + diagnostic + rapport + job en une transaction :
    `DRAFT` ne dure donc que le temps de cette transaction, et un porteur qui abandonne en
    cours de saisie ne laissait **aucune ligne en base**. Conséquence la plus coûteuse : le
    taux d'abandon et l'étape où il survient étaient inconnus, et ne se déduisent d'aucune
    autre donnée.

    Table SÉPARÉE plutôt qu'un statut sur `Diagnostic` : un statut contaminerait tout le
    pipeline (`_start()` conditionnel, `create_pending` en attente, statuts projet perdant
    leur sens de « pipeline machine »). Ce pipeline est sain — on n'y touche pas.

    RGPD : aucune ligne avant création de compte. Le parcours anonyme garde son
    `localStorage`, ce qui est le comportement correct — la donnée reste sur l'appareil du
    visiteur. Le brouillon porte son PROPRE `consent_at`, distinct de celui du diagnostic
    soumis, et il est purgé (pas archivé) au-delà de `draft_ttl_days`.

    Règle à tenir : aucun score, aucun statut projet, aucune notification ne s'adosse à un
    brouillon. Dès qu'une logique métier s'y accroche, il devient une seconde source de
    vérité.
    """

    __tablename__ = "diagnostic_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Saisie partielle, même forme que `Diagnostic.answers` : { dimensionKey: texte }.
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Métadonnées du récit telles que collectées avant l'entrée du wizard (title, sector…).
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    mode: Mapped[EntryMode] = mapped_column(default=EntryMode.GUIDED)
    # Dernière dimension ouverte — c'est LE champ de mesure : il situe le décrochage.
    last_dimension: Mapped[str | None] = mapped_column(String(10), default=None)
    consent_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), index=True)
    # Renseigné à la conversion en diagnostic réel ; sinon le brouillon est VIVANT.
    # Conservé plutôt que supprimé : la trajectoire de saisie est la donnée qu'on cherchait.
    submitted_at: Mapped[datetime | None] = mapped_column(default=None, index=True)

    __table_args__ = (
        # Un seul brouillon ACTIF par porteur : le produit ne gère pas plusieurs saisies
        # simultanées, et l'unicité partielle empêche l'accumulation silencieuse.
        # À lever si le produit ouvre un jour plusieurs projets en saisie (multi-projet V2).
        Index(
            "uq_active_draft_per_owner",
            "owner_id",
            unique=True,
            postgresql_where=submitted_at.is_(None),
        ),
    )
