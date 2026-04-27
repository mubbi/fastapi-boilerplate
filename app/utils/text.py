"""Text utilities — slug, truncate, normalize.

Pure helpers; no business logic, no I/O, no settings access.
"""

from __future__ import annotations

import re
import unicodedata

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-{2,}")


def slugify(value: str, *, max_length: int = 80) -> str:
    """ASCII-safe URL slug.

    Notes:
        - Strips combining marks via NFKD normalisation.
        - Replaces non-alphanumerics with ``-``.
        - Collapses repeated dashes and trims to ``max_length``.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().strip()
    replaced = _SLUG_NON_ALNUM.sub("-", lowered)
    collapsed = _DASHES.sub("-", replaced).strip("-")
    return collapsed[:max_length].rstrip("-")


def truncate(value: str, *, max_length: int, suffix: str = "…") -> str:
    """Truncate ``value`` to ``max_length`` characters, appending ``suffix`` if cut."""
    if len(value) <= max_length:
        return value
    if max_length <= len(suffix):
        return value[:max_length]
    return value[: max_length - len(suffix)] + suffix


def normalize_email(email: str) -> str:
    """Lowercase + strip — used before storing/comparing emails to prevent dupes."""
    return email.strip().lower()
