from fastapi import Header, HTTPException

from .models import AuthContext


def get_auth_context(
    tenant_id: str = Header(default="demo", alias="X-Lotus-Tenant"),
    user_id: str = Header(default="demo-user", alias="X-Lotus-User"),
) -> AuthContext:
    if not tenant_id.strip() or not user_id.strip():
        raise HTTPException(status_code=401, detail="Missing Lotus identity context")
    return AuthContext(
        tenant_id=tenant_id.strip(),
        user_id=user_id.strip(),
        principals=(f"user:{user_id.strip()}", "group:demo"),
    )
