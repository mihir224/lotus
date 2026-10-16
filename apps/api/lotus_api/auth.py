from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from .config import Settings, get_settings
from .models import AuthContext


def _google_auth_context(claims: dict[str, Any], settings: Settings) -> AuthContext:
    subject = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip().casefold()
    name = str(claims.get("name", "")).strip() or None
    picture = str(claims.get("picture", "")).strip() or None
    if not subject or not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google account email is not verified")

    email_domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    allowed_emails = settings.google_email_allowlist
    allowed_domains = settings.google_domain_allowlist
    if not allowed_emails and not allowed_domains:
        raise HTTPException(status_code=503, detail="Google account allowlist is not configured")
    if email not in allowed_emails and email_domain not in allowed_domains:
        raise HTTPException(status_code=403, detail="Google account is not allowed")

    return AuthContext(
        tenant_id="demo",
        user_id=subject,
        email=email,
        name=name,
        designation=None,
        picture_url=picture,
        principals=(
            f"user:{subject}",
            f"email:{email}",
            f"domain:{email_domain}",
            "group:demo",
        ),
    )


def get_auth_context(
    tenant_id: str = Header(default="demo", alias="X-Lotus-Tenant"),
    user_id: str = Header(default="demo-user", alias="X-Lotus-User"),
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> AuthContext:
    settings = settings or get_settings()
    if settings.auth_mode == "google":
        if not settings.google_oauth_client_id:
            raise HTTPException(status_code=503, detail="Google OAuth client is not configured")
        scheme, _, credential = (authorization or "").partition(" ")
        if scheme.casefold() != "bearer" or not credential:
            raise HTTPException(
                status_code=401,
                detail="Google sign-in is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            claims = id_token.verify_oauth2_token(
                credential,
                GoogleRequest(),
                settings.google_oauth_client_id,
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(
                status_code=401,
                detail="Google ID token is invalid or expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from error
        return _google_auth_context(claims, settings)

    if settings.auth_mode != "dev":
        raise HTTPException(status_code=503, detail="Unsupported authentication mode")
    if not tenant_id.strip() or not user_id.strip():
        raise HTTPException(status_code=401, detail="Missing Lotus identity context")
    return AuthContext(
        tenant_id=tenant_id.strip(),
        user_id=user_id.strip(),
        email="demo.engineer@lotus.example",
        name="Demo Engineer",
        designation="Platform Engineer",
        picture_url=None,
        principals=(f"user:{user_id.strip()}", "group:demo"),
    )
