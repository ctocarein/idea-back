"""Transport email enfichable.

Sans SMTP configuré (dev), on **logge** le lien au lieu d'envoyer → le mécanisme de
vérification est testable de bout en bout sans fournisseur. En prod, renseigner
`SMTP_HOST` (+ user/password) bascule sur un envoi réel via smtplib. Best-effort :
un échec d'envoi ne doit jamais casser l'inscription.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("email")


def send_email(*, to: str, subject: str, body: str) -> None:
    """Envoie un email (SMTP si configuré, sinon log). Best-effort, ne lève jamais."""
    settings = get_settings()
    if not settings.smtp_host:
        # Dev / pas de SMTP : on trace le contenu pour pouvoir suivre le lien.
        logger.info("email_logged", to=to, subject=subject, body=body)
        return
    try:
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
            s.starttls()
            if settings.smtp_user and settings.smtp_password:
                s.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            s.send_message(msg)
        logger.info("email_sent", to=to, subject=subject)
    except Exception as exc:  # noqa: BLE001 — best-effort, ne bloque jamais l'appelant
        logger.warning("email_send_failed", to=to, error=str(exc))


def send_verification_email(*, to: str, name: str, token: str) -> None:
    link = f"{get_settings().public_base_url.rstrip('/')}/verify-email?token={token}"
    body = (
        f"Bonjour {name},\n\n"
        "Confirme ton adresse email pour sécuriser ton espace IDEAXION :\n\n"
        f"{link}\n\n"
        "Ce lien est valable 24 h. Si tu n'es pas à l'origine de cette inscription, ignore ce message.\n"
    )
    send_email(to=to, subject="Confirme ton adresse — IDEAXION", body=body)
