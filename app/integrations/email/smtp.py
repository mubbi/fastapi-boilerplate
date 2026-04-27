"""Async SMTP email sender via ``aiosmtplib``.

Production-grade implementation: STARTTLS / TLS, authentication, multipart
``alternative`` body, structured logging, and a graceful close.
"""

from __future__ import annotations

from email.message import EmailMessage as MIMEMessage

import aiosmtplib

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.integrations.email.base import EmailAddress, EmailMessage
from app.integrations.email.renderer import TemplateRenderer

log = get_logger(__name__)


class SMTPEmailSender:
    """Send emails over SMTP."""

    def __init__(self, *, settings: Settings, renderer: TemplateRenderer) -> None:
        self._settings = settings
        self._renderer = renderer

    async def send_template(
        self,
        *,
        template: str,
        to: tuple[EmailAddress, ...] | EmailAddress,
        locale: str,
        context: dict[str, object] | None = None,
        sender: EmailAddress | None = None,
    ) -> EmailMessage:
        rendered = self._renderer.render(template=template, locale=locale, context=context)
        recipients = (to,) if isinstance(to, EmailAddress) else to
        message = EmailMessage(
            to=recipients,
            sender=sender or self._default_sender(),
            subject=rendered.subject,
            text_body=rendered.text_body,
            html_body=rendered.html_body,
            locale=rendered.locale,
            headers={"Content-Language": rendered.locale},
        )
        await self.send(message)
        return message

    async def send(self, message: EmailMessage) -> None:
        mime = self._build_mime(message)
        try:
            await aiosmtplib.send(
                mime,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=self._settings.smtp_user or None,
                password=(
                    self._settings.smtp_password.get_secret_value()
                    if self._settings.smtp_password.get_secret_value()
                    else None
                ),
                use_tls=self._settings.smtp_use_tls,
                start_tls=self._settings.smtp_use_starttls,
                timeout=30,
            )
            log.info(
                "email.sent",
                template_locale=message.locale,
                recipients=len(message.to),
                subject_len=len(message.subject),
            )
        except Exception as exc:
            log.error("email.send_failed", error=str(exc))
            raise ExternalServiceError(
                code="EMAIL_SEND_FAILED",
                message="errors.email.send_failed",
                details={"reason": str(exc)},
            ) from exc

    def _build_mime(self, message: EmailMessage) -> MIMEMessage:
        mime = MIMEMessage()
        mime["From"] = message.sender.render()
        mime["To"] = ", ".join(addr.render() for addr in message.to)
        mime["Subject"] = message.subject
        for k, v in message.headers.items():
            mime[k] = v
        mime.set_content(message.text_body, subtype="plain", charset="utf-8")
        mime.add_alternative(message.html_body, subtype="html", charset="utf-8")
        return mime

    def _default_sender(self) -> EmailAddress:
        return EmailAddress(
            address=self._settings.email_from_address,
            name=self._settings.email_from_name,
        )

    async def aclose(self) -> None:
        return None
