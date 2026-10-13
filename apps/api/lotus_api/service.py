from functools import lru_cache

from .agents import OrchestrationService
from .config import get_settings
from .models import AuthContext, ChatRequest, GroundedAnswer
from .storage import get_store


def answer_chat(request: ChatRequest, auth: AuthContext) -> GroundedAnswer:
    return get_orchestrator().answer(request, auth)


@lru_cache
def get_orchestrator() -> OrchestrationService:
    return OrchestrationService(get_settings(), get_store())
