"""UUIDv7 generation.

Time-sortable, K-friendly identifiers preferred for primary keys, request IDs,
and event IDs. Falls back to ``uuid.uuid4`` when the optional ``uuid7`` package
is unavailable, so the boilerplate runs out of the box.
"""

from __future__ import annotations

import os
import time
from uuid import UUID, uuid4

try:
    from uuid_extensions import uuid7 as _uuid7  # type: ignore[import-not-found]

    _HAS_UUID7 = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_UUID7 = False


def _manual_uuid7() -> UUID:
    """Deterministic UUIDv7 implementation per RFC 9562 (best-effort).

    Layout (MSB → LSB):
      - 48 bits: unix timestamp in milliseconds
      - 4  bits: version (7)
      - 12 bits: random A
      - 2  bits: variant (10)
      - 62 bits: random B
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

    value = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)


def new_uuid7() -> UUID:
    """Return a fresh UUIDv7."""
    if _HAS_UUID7:
        result = _uuid7()
        return result if isinstance(result, UUID) else UUID(str(result))
    return _manual_uuid7()


def new_uuid7_hex() -> str:
    """Return a UUIDv7 as 32 lowercase hex characters (no dashes)."""
    return new_uuid7().hex


def new_uuid4_hex() -> str:
    """Random UUIDv4 as 32 lowercase hex characters; used where time-sort is undesirable."""
    return uuid4().hex
