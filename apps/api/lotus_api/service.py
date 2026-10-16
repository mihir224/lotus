from functools import lru_cache

from .agents import OrchestrationService
from .config import get_settings
from .models import AuthContext, ChatMessageRecord, ChatRequest, GroundedAnswer, RunEvent
from .run_events import event
from .storage import get_store


def answer_chat(request: ChatRequest, auth: AuthContext) -> GroundedAnswer:
    return _run_persisted(request, auth)


def stream_chat(request: ChatRequest, auth: AuthContext, emit) -> GroundedAnswer:
    return _run_persisted(request, auth, emit)


def _run_persisted(request: ChatRequest, auth: AuthContext, emit=None) -> GroundedAnswer:
    store = get_store()
    session = store.create_chat_session(auth, request.project_id, request.session_id)
    scoped_request = request.model_copy(update={"session_id": session.session_id})
    context: list[ChatMessageRecord] = store.get_chat_context(session.session_id, auth)
    user_message = store.add_chat_message(
        session.session_id,
        auth,
        "user",
        request.message,
        "running",
    )
    completed_event: RunEvent | None = None

    def durable_emit(item: RunEvent) -> None:
        nonlocal completed_event
        if item.event_type == "answer.completed":
            completed_event = item
        elif emit:
            emit(item)

    try:
        response = get_orchestrator().answer(
            scoped_request,
            auth,
            durable_emit if emit else None,
            context,
        )
        response.session_id = session.session_id
        store.update_chat_message_status(user_message.message_id, auth, "completed")
        store.add_chat_message(
            session.session_id,
            auth,
            "assistant",
            response.answer,
            "completed",
            execution_id=response.execution_id,
            response=response.model_dump(mode="json"),
        )
        if emit and completed_event:
            emit(completed_event.model_copy(update={"response": response}))
        return response
    except Exception as exc:
        store.update_chat_message_status(user_message.message_id, auth, "failed")
        if emit and completed_event:
            emit(
                event(
                    completed_event.execution_id,
                    "run.failed",
                    session_id=session.session_id,
                    error=type(exc).__name__,
                )
            )
        raise


@lru_cache
def get_orchestrator() -> OrchestrationService:
    return OrchestrationService(get_settings(), get_store())
