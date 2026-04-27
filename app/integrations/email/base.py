"""Email Protocol + value objects.

Spec §10.5; rules in ``.cursor/rules/email-integration.mdc`` and ``.cursor/rules/i18n-l10n.mdc``.
Hard rules:
- ``locale`` is **always** an explicit kwarg — services never read it from a thread-local.
- Templates live under ``app/templates/email/<id>/<locale>/{subject,html,txt}.j2``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """Address pair (display name optional)."""

    address: str
    name: str | None = None

    def render(self) -> str:
        if self.name:
            return f"{self.name} <{self.address}>"
        return self.address


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Rendered, ready-to-send email."""

    to: tuple[EmailAddress, ...]
    sender: EmailAddress
    subject: str
    text_body: str
    html_body: str
    locale: str
    headers: dict[str, str] = field(default_factory=dict)


class EmailSender(Protocol):
    """Adapter contract for sending emails.

    Implementations: :class:`SMTPEmailSender` (production), :class:`NullEmailSender` (tests).
    """

    async def send_template(
        self,
        *,
        template: str,
        to: tuple[EmailAddress, ...] | EmailAddress,
        locale: str,
        context: dict[str, object] | None = None,
        sender: EmailAddress | None = None,
    ) -> EmailMessage:
        """Render and send a templated email; return the rendered ``EmailMessage``."""
        ...

    async def send(self, message: EmailMessage) -> None:
        """Send an already-rendered :class:`EmailMessage`."""
        ...

    async def aclose(self) -> None: ...
