"""Handlers worker des notifications — envoi d'email et rappel J+7 sur l'action prioritaire.

Une notification in-app n'est visible qu'une fois le porteur revenu : elle ne peut pas le
faire revenir. Le rappel comble ce manque, et rien d'autre — il ne remplace pas la boucle
institutionnelle (l'incubateur qui dit à sa cohorte de refaire le point avant le comité),
et il ne valide aucune hypothèse sur ce qui ramène un porteur.

La mesure de succès est le TAUX DE RE-DIAGNOSTIC, pas le taux d'ouverture.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.email import asend_email, reminder_message
from app.core.logging import get_logger
from app.core.security import create_unsubscribe_token
from app.iam.repository import UserRepository
from app.instrumentation.service import InstrumentationService
from app.notifications.repository import NotificationRepository
from app.projects.models import DiagnosticStatus
from app.projects.repository import ProjectRepository
from app.reports.repository import ReportRepository
from app.scoring.repository import ScoreRunRepository

logger = get_logger("notifications.reminders")

SEND_EMAIL_JOB = "send_email"
ACTION_REMINDER_JOB = "action_reminder"

# Seuil au-delà duquel une dimension est considérée FORTE : identique à celui qui a
# produit l'action (`derive_next_actions`). Les deux doivent bouger ensemble.
STRONG_THRESHOLD = 8

# Leviers routables aujourd'hui. `academy` et `pitchsim` pointent vers des modules retirés
# (10 dimensions sur 12) : un rappel les référençant dirait « tu devais apprendre X » en
# renvoyant vers rien. Couverture partielle ASSUMÉE — préférable à un rappel vers du vide.
# L'élargissement, après SPEC_LEVIERS_V2, est un changement de cette constante, pas de code.
ROUTABLE_LEVERS = ("document", "mentor")


async def handle_send_email(payload: dict[str, Any]) -> None:
    """Envoi d'email asynchrone. `asend_email` déporte déjà le SMTP bloquant dans un thread.

    Les échecs transitoires sont couverts par le retry backoff de la file (1/5/15 min).
    """
    await asend_email(
        to=payload["to"],
        subject=payload["subject"],
        body=payload["body"],
    )


async def handle_action_reminder(payload: dict[str, Any]) -> None:
    """Rappel J+7 — l'état est REVÉRIFIÉ à l'exécution, jamais à la planification.

    Sept jours séparent les deux : le porteur a pu revenir, faire l'action, archiver son
    projet ou se désabonner. Chaque annulation est un SUCCÈS avec log, pas une erreur —
    un job en échec serait retenté, et retenterait d'envoyer un mail devenu inutile.
    """
    project_id = UUID(payload["project_id"])
    axis_key = str(payload["axis_key"])
    report_id = UUID(payload["report_id"])

    async with get_session_factory()() as session:
        projects = ProjectRepository(session)
        project = await projects.get_by_id(project_id)
        if project is None:
            return await _cancel(session, project_id, "project_missing")

        # 1. Projet archivé → le porteur a tourné la page.
        if project.diagnostic_status is DiagnosticStatus.ARCHIVED:
            return await _cancel(session, project_id, "project_archived")

        user = await UserRepository(session).get_by_id(project.owner_id)
        if user is None:
            return await _cancel(session, project_id, "user_missing")

        # 2. Désabonné → obligation, pas option.
        if user.reminders_opt_out:
            return await _cancel(session, project_id, "opted_out")

        # 3. Compte non vérifié → on n'écrit pas à une adresse non prouvée : c'est la
        # délivrabilité de TOUS les envois qui est en jeu, y compris la vérification.
        if not user.email_verified:
            return await _cancel(session, project_id, "email_unverified")

        # Au niveau du PORTEUR, pas du projet : chaque diagnostic crée son propre projet,
        # donc un porteur revenu a produit son nouveau score sur un autre `project_id`.
        # Interroger le projet du bilan ne le verrait jamais revenir.
        latest = await ScoreRunRepository(session).get_latest_for_owner(project.owner_id)

        # 4. Un score plus récent, sur un AUTRE bilan → le porteur est déjà revenu.
        if latest is not None and latest.report_id is not None and latest.report_id != report_id:
            return await _cancel(session, project_id, "already_returned")

        # 5. La dimension visée a atteint le seuil fort → l'action est faite. `latest` porte
        # ici le score courant du bilan visé (sinon on serait sorti au point 4), y compris
        # après un ajustement analyste.
        if latest is not None and int((latest.axes or {}).get(axis_key, 0)) >= STRONG_THRESHOLD:
            return await _cancel(session, project_id, "action_done")

        report = await ReportRepository(session).get_by_id(report_id)
        action = _find_action(report.next_actions if report else None, axis_key)
        if action is None:
            # L'action a disparu du bilan (re-scoring analyste) : plus rien à rappeler.
            return await _cancel(session, project_id, "action_gone")

        subject, body = reminder_message(
            name=user.full_name.split(" ")[0] or user.full_name,
            dimension=action.get("dimension", axis_key.upper()),
            action_label=action.get("label", ""),
            report_id=str(report_id),
            unsubscribe_token=create_unsubscribe_token(user.id),
            lang=user.language,
        )
        await asend_email(to=user.email, subject=subject, body=body)

        # Trace in-app, créée À L'ENVOI et pas à la planification : elle doit refléter un
        # mail réellement parti, sinon elle mentirait sur chaque rappel annulé.
        await NotificationRepository(session).create(
            user_id=user.id,
            type="action_reminder",
            payload={
                "axis_key": axis_key,
                "code": action.get("code", ""),
                "dimension": action.get("dimension", ""),
                "lever_type": action.get("lever_type", ""),
                "action_label": action.get("label", ""),
                "report_id": str(report_id),
            },
        )
        await InstrumentationService(session).emit(
            "reminder_sent",
            actor_id=user.id,
            project_id=project_id,
            props={"axis_key": axis_key, "lever_type": action.get("lever_type", "")},
        )
        await session.commit()
    logger.info("action_reminder_sent", project_id=str(project_id), axis_key=axis_key)


def _find_action(actions: list | None, axis_key: str) -> dict | None:
    return next(
        (a for a in (actions or []) if isinstance(a, dict) and a.get("key") == axis_key),
        None,
    )


async def _cancel(session, project_id: UUID, reason: str) -> None:
    """Annulation silencieuse : job terminé en SUCCÈS, avec la raison tracée.

    Le motif est instrumenté : sans lui, on saurait qu'un rappel n'est pas parti mais pas
    pourquoi — et « déjà revenu » (le produit fonctionne) ne se distingue pas de
    « désabonné » (le mail dérange), qui appellent des décisions opposées.
    """
    await InstrumentationService(session).emit(
        "reminder_cancelled",
        project_id=project_id,
        props={"reason": reason},
    )
    await session.commit()
    logger.info("action_reminder_cancelled", project_id=str(project_id), reason=reason)


def reminder_delay_days() -> int:
    return get_settings().reminder_delay_days
