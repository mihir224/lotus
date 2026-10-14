import pytest
from fastapi import HTTPException
from lotus_api.auth import _google_auth_context
from lotus_api.config import Settings


def test_google_auth_accepts_allowlisted_verified_email() -> None:
    context = _google_auth_context(
        {
            "sub": "google-subject-1",
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice",
        },
        Settings(allowed_google_domains="example.com"),
    )

    assert context.user_id == "google-subject-1"
    assert context.email == "alice@example.com"
    assert "group:demo" in context.principals


def test_google_auth_rejects_account_outside_allowlist() -> None:
    with pytest.raises(HTTPException) as error:
        _google_auth_context(
            {
                "sub": "google-subject-2",
                "email": "outsider@example.net",
                "email_verified": True,
            },
            Settings(allowed_google_domains="example.com"),
        )

    assert error.value.status_code == 403
