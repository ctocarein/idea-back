"""Transport email enfichable.

Sans SMTP configuré (dev), on **logge** le lien au lieu d'envoyer → le mécanisme de
vérification est testable de bout en bout sans fournisseur. En prod, renseigner
`SMTP_HOST` (+ user/password) bascule sur un envoi réel via smtplib. Best-effort :
un échec d'envoi ne doit jamais casser l'inscription.

Deux points sur lesquels un SMTP « simplement branché » échoue en production :

* **Le mode TLS.** Port 587 = connexion claire puis STARTTLS ; port 465 = TLS
  implicite dès la poignée de main. Appeler `starttls()` sur 465 échoue toujours.
  On déduit le mode du port, surchargeable par `SMTP_TLS`.
* **Le blocage de la boucle.** `smtplib` est synchrone : appelé tel quel depuis un
  handler async, il gèle *toutes* les requêtes le temps du dialogue SMTP (jusqu'à
  10 s). D'où `asend_email`, à utiliser depuis tout code async.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("email")

# Port d'usage pour le TLS implicite (SMTPS).
_IMPLICIT_TLS_PORT = 465


def _tls_mode(host_port: int, configured: str | None) -> str:
    """`implicit` | `starttls` | `none`. Déduit du port si non configuré."""
    mode = (configured or "").strip().lower()
    if mode in {"implicit", "starttls", "none"}:
        return mode
    return "implicit" if host_port == _IMPLICIT_TLS_PORT else "starttls"


def _deliver(*, to: str, subject: str, body: str) -> None:
    """Dialogue SMTP réel. Bloquant — ne jamais appeler directement depuis de l'async."""
    settings = get_settings()
    mode = _tls_mode(settings.smtp_port, settings.smtp_tls)

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if mode == "implicit":
        client = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=context
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)

    with client as session:
        if mode == "starttls":
            session.starttls(context=context)
        if settings.smtp_user and settings.smtp_password:
            session.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        session.send_message(msg)


def _log_instead(*, to: str, subject: str, body: str) -> bool:
    """Trace le contenu quand aucun SMTP n'est configuré. `True` si on a bien loggé."""
    if get_settings().smtp_host:
        return False
    logger.info("email_logged", to=to, subject=subject, body=body)
    return True


def send_email(*, to: str, subject: str, body: str) -> None:
    """Envoie un email (SMTP si configuré, sinon log). Best-effort, ne lève jamais.

    Version bloquante, réservée au code synchrone (worker, scripts). Depuis un
    contexte async, utiliser `asend_email`.
    """
    if _log_instead(to=to, subject=subject, body=body):
        return
    try:
        _deliver(to=to, subject=subject, body=body)
        logger.info("email_sent", to=to, subject=subject)
    except Exception as exc:  # noqa: BLE001 — best-effort, ne bloque jamais l'appelant
        # `warning` et non `error` : l'appelant a réussi (le compte est créé). Mais
        # cet évènement doit rester compté — un pic ici signifie que des porteurs
        # n'ont jamais reçu leur lien, et ils ne s'en plaindront pas, ils partiront.
        logger.warning("email_send_failed", to=to, subject=subject, error=str(exc))


async def asend_email(*, to: str, subject: str, body: str) -> None:
    """`send_email` sans geler la boucle d'évènements. Best-effort, ne lève jamais."""
    if _log_instead(to=to, subject=subject, body=body):
        return
    try:
        await asyncio.to_thread(_deliver, to=to, subject=subject, body=body)
        logger.info("email_sent", to=to, subject=subject)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("email_send_failed", to=to, subject=subject, error=str(exc))


# Bilingue : l'email de vérification suit la langue du porteur (défaut "fr").
_VERIFY_EMAIL = {
    "fr": {
        "subject": "Confirme ton adresse — IDEAXION",
        "body": (
            "Bonjour {name},\n\n"
            "Confirme ton adresse email pour sécuriser ton espace IDEAXION :\n\n"
            "{link}\n\n"
            "Ce lien est valable 24 h. Si tu n'es pas à l'origine de cette inscription, ignore ce message.\n"
        ),
    },
    "en": {
        "subject": "Confirm your email — IDEAXION",
        "body": (
            "Hi {name},\n\n"
            "Confirm your email address to secure your IDEAXION space:\n\n"
            "{link}\n\n"
            "This link is valid for 24 h. If you didn't sign up, please ignore this message.\n"
        ),
    },
}


def _verification_message(*, name: str, token: str, lang: str) -> tuple[str, str]:
    """(sujet, corps) du mail de vérification, dans la langue du porteur."""
    lang = lang if lang in _VERIFY_EMAIL else "fr"
    # Lien vers la route localisée du front (préfixe /fr /en, cf. routing next-intl).
    base = get_settings().public_base_url.rstrip("/")
    link = f"{base}/{lang}/verify-email?token={token}"
    tpl = _VERIFY_EMAIL[lang]
    return tpl["subject"], tpl["body"].format(name=name, link=link)


# Rappel J+7 sur l'action prioritaire. Texte BRUT, pas de HTML : poids réduit, meilleure
# délivrabilité, et cohérent avec une infrastructure mail encore jeune.
#
# Le mail référence CE QUE LE PORTEUR A LUI-MÊME ÉCRIT, via son action prioritaire. Il ne
# ressemble pas à du marketing parce qu'il n'en est pas : pas de séquence, pas de contenu
# générique, aucune injonction d'achat. Deux issues seulement, et les deux mènent au
# produit — « pas encore » n'est pas un échec, c'est un retour au bilan.
_REMINDER_EMAIL = {
    "fr": {
        "subject": "Où en es-tu sur {dimension} ?",
        "body": (
            "Bonjour {name},\n\n"
            "Il y a une semaine, ton bilan IDEAXION pointait une priorité :\n"
            "{action_label}.\n\n"
            "Où en es-tu ?\n\n"
            "  → C'est fait, je refais le point : {rediagnostic_url}\n"
            "  → Pas encore : {bilan_url}\n\n"
            "Ton bilan reste disponible à tout moment.\n\n"
            "—\n"
            "Se désabonner des rappels : {unsubscribe_url}\n"
        ),
    },
    "en": {
        "subject": "Where do you stand on {dimension}?",
        "body": (
            "Hi {name},\n\n"
            "A week ago, your IDEAXION assessment pointed to one priority:\n"
            "{action_label}.\n\n"
            "Where do you stand?\n\n"
            "  → Done, let's reassess: {rediagnostic_url}\n"
            "  → Not yet: {bilan_url}\n\n"
            "Your assessment stays available at any time.\n\n"
            "—\n"
            "Unsubscribe from reminders: {unsubscribe_url}\n"
        ),
    },
}


def reminder_message(
    *,
    name: str,
    dimension: str,
    action_label: str,
    report_id: str,
    unsubscribe_token: str,
    lang: str = "fr",
) -> tuple[str, str]:
    """(sujet, corps) du rappel d'action, dans la langue du porteur."""
    lang = lang if lang in _REMINDER_EMAIL else "fr"
    base = get_settings().public_base_url.rstrip("/")
    api = get_settings().backend_base_url.rstrip("/")
    tpl = _REMINDER_EMAIL[lang]
    return (
        tpl["subject"].format(dimension=dimension),
        tpl["body"].format(
            name=name,
            action_label=action_label,
            dimension=dimension,
            bilan_url=f"{base}/{lang}/dashboard/bilan/{report_id}",
            rediagnostic_url=f"{base}/{lang}/dashboard/diagnostic",
            # Le désabonnement est servi par le BACK : il doit fonctionner sans session,
            # donc sans passer par une page qui exigerait d'être connecté.
            unsubscribe_url=f"{api}/api/v1/notifications/unsubscribe?token={unsubscribe_token}",
        ),
    )


def send_verification_email(*, to: str, name: str, token: str, lang: str = "fr") -> None:
    subject, body = _verification_message(name=name, token=token, lang=lang)
    send_email(to=to, subject=subject, body=body)


async def asend_verification_email(*, to: str, name: str, token: str, lang: str = "fr") -> None:
    """Variante async — c'est celle qu'appelle l'inscription (handler async)."""
    subject, body = _verification_message(name=name, token=token, lang=lang)
    await asend_email(to=to, subject=subject, body=body)
