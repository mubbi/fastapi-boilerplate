"""Security primitives: password hashing + JWT helpers.

Domain code (auth flows) is project-specific. The boilerplate ships only the
mechanism so per-project auth is plug-and-play.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_RESERVED_CLAIMS = frozenset({"sub", "iat", "nbf", "exp", "iss", "aud", "type"})


# ── Password hashing ─────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ──────────────────────────────────────────────────


def create_access_token(
    *,
    subject: str,
    settings: Settings,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Mint a signed JWT access token with standard registered claims."""
    if extra_claims and _RESERVED_CLAIMS.intersection(extra_claims):
        raise ValueError("extra_claims must not override registered JWT claims")

    now = datetime.now(tz=UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.app_name,
        "aud": settings.jwt_audience,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token if isinstance(token, str) else token.decode("utf-8")


def decode_token(token: str, *, settings: Settings) -> dict[str, Any]:
    """Decode + validate JWT. Raises :class:`UnauthorizedError` on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.app_name,
            options={"require_exp": True, "require_iat": True, "require_nbf": True},
        )
    except JWTError as exc:
        raise UnauthorizedError(message="auth.invalid_token") from exc
    if not isinstance(payload, dict):
        raise UnauthorizedError(message="auth.invalid_token")
    return payload
