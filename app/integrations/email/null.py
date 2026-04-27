"""No-op email sender used in tests / disabled-email environments.

Captures sent messages on ``self.outbox`` so tests can assert on what would
have been sent without ever opening a network socket.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.integrations.email.base import EmailAddress, EmailMessage
from app.integrations.email.renderer import TemplateRenderer

log = get_logger(__name__)


class NullEmailSender:
    """Records messages instead of sending them."""

    def __init__(self, *, renderer: TemplateRenderer) -> None:
        self._renderer = renderer
        self.outbox: list[EmailMessage] = []

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
        sender_addr = sender or EmailAddress(
            address=self._renderer._settings.email_from_address,
            name=self._renderer._settings.email_from_name,
        )
        message = EmailMessage(
            to=recipients,
            sender=sender_addr,
            subject=rendered.subject,
            text_body=rendered.text_body,
            html_body=rendered.html_body,
            locale=rendered.locale,
            headers={"Content-Language": rendered.locale},
        )
        await self.send(message)
        return message

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
        log.info(
            "email.captured",
            recipients=len(message.to),
            subject=message.subject,
            locale=message.locale,
        )

    async def aclose(self) -> None:
        self.outbox.clear()
