"""Domain exception hierarchy + status mapping."""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    UnauthorizedError,
    _status_for,
)


@pytest.mark.unit
def test_default_code_and_message() -> None:
    err = NotFoundError(details={"resource": "user"})
    assert err.code == "NOT_FOUND"
    assert err.message == "Resource not found"
    assert err.details == {"resource": "user"}


@pytest.mark.unit
def test_override_message_and_code() -> None:
    err = ConflictError(code="USER_EMAIL_TAKEN", message="user.email_taken")
    assert err.code == "USER_EMAIL_TAKEN"
    assert err.message == "user.email_taken"


@pytest.mark.unit
def test_status_mapping() -> None:
    assert _status_for(NotFoundError()) == 404
    assert _status_for(ConflictError()) == 409
    assert _status_for(UnauthorizedError()) == 401
    assert _status_for(DomainError()) == 500
