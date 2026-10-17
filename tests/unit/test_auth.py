import pytest
from fastapi import HTTPException
from lotus_api.auth import _google_auth_context


def test_google_auth_accepts_any_verified_google_email() -> None:
    context = _google_auth_context(
        {
            "sub": "google-subject-1",
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice",
        }
    )

    assert context.user_id == "google-subject-1"
    assert context.email == "alice@example.com"
    assert "group:demo" in context.principals


def test_google_auth_rejects_unverified_account() -> None:
    with pytest.raises(HTTPException) as error:
        _google_auth_context(
            {
                "sub": "google-subject-2",
                "email": "outsider@example.net",
                "email_verified": False,
            }
        )

    assert error.value.status_code == 401
