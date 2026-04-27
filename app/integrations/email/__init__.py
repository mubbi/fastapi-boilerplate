"""Email integration: Protocol + adapters + Jinja2 renderer."""

from __future__ import annotations

from app.core.config import Settings
from app.core.i18n import Translator
from app.core.logging import get_logger
from app.integrations.email.base import EmailAddress, EmailMessage, EmailSender
from app.integrations.email.null import NullEmailSender
from app.integrations.email.renderer import TemplateRenderer
from app.integrations.email.smtp import SMTPEmailSender

log = get_logger(__name__)


async def build_email_sender(
    settings: Settings,
    *,
    translator: Translator,
) -> EmailSender:
    """Pick an :class:`EmailSender` adapter for the current environment."""
    renderer = TemplateRenderer(settings=settings, translator=translator)

    if not settings.email_enabled or settings.email_provider == "null":
        log.info("email.adapter", adapter="null")
        return NullEmailSender(renderer=renderer)

    log.info("email.adapter", adapter="smtp", host=settings.smtp_host, port=settings.smtp_port)
    return SMTPEmailSender(settings=settings, renderer=renderer)


__all__ = [
    "EmailAddress",
    "EmailMessage",
    "EmailSender",
    "NullEmailSender",
    "SMTPEmailSender",
    "TemplateRenderer",
    "build_email_sender",
]
