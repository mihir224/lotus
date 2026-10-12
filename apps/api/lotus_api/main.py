from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_auth_context
from .config import get_settings
from .models import AuthContext, ChatRequest, GroundedAnswer
from .service import answer_chat

settings = get_settings()
app = FastAPI(title="Lotus API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Lotus-Tenant", "X-Lotus-User"],
)


@app.get("/v1/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/v1/readyz")
def ready() -> dict[str, object]:
    return {
        "status": "ready",
        "mode": "fixture" if settings.demo_mode else "cloud",
        "gcp_configured": bool(settings.google_cloud_project),
        "location": settings.google_cloud_location,
    }


@app.post("/v1/chat/messages", response_model=GroundedAnswer)
def chat(
    request: ChatRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> GroundedAnswer:
    return answer_chat(request, auth)
