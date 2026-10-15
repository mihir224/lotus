from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .models import RunEvent

RunEventSink = Callable[[RunEvent], None]

_SENSITIVE_KEYS = {"authorization", "token", "secret", "password", "transcript", "prompt"}


def bounded_preview(value: Any, *, limit: int = 240) -> Any:
    """Return a small telemetry-safe value; never expose raw prompts or transcripts."""
    if isinstance(value, dict):
        return {
            str(key): "[redacted]"
            if any(part in str(key).casefold() for part in _SENSITIVE_KEYS)
            else bounded_preview(item, limit=limit)
            for key, item in list(value.items())[:12]
        }
    if isinstance(value, (list, tuple)):
        return [bounded_preview(item, limit=limit) for item in value[:8]]
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized[:limit] + ("…" if len(normalized) > limit else "")
    return value


def event(execution_id: str, event_type: str, **values: Any) -> RunEvent:
    return RunEvent(
        event_type=event_type,
        execution_id=execution_id,
        timestamp=datetime.now(UTC),
        **values,
    )
