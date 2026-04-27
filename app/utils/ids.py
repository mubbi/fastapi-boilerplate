"""UUIDv7 generation.

Time-sortable, K-friendly identifiers preferred for primary keys, request IDs,
and event IDs. Provided by the ``uuid7`` PyPI package (``uuid_extensions``).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from uuid_extensions import uuid7 as _uuid7


def new_uuid7() -> UUID:
    """Return a fresh UUIDv7."""
    result = _uuid7()
    return result if isinstance(result, UUID) else UUID(str(result))


def new_uuid7_hex() -> str:
    """Return a UUIDv7 as 32 lowercase hex characters (no dashes)."""
    return new_uuid7().hex


def new_uuid4_hex() -> str:
    """Random UUIDv4 as 32 lowercase hex characters; used where time-sort is undesirable."""
    return uuid4().hex
