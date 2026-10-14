from datetime import datetime

from .fixtures import load_fixture
from .models import AuthContext, CalendarEventItem


def _allowed(row: dict[str, object], auth: AuthContext) -> bool:
    if row["tenant_id"] != auth.tenant_id:
        return False
    principals = row.get("acl_principals", [])
    if not isinstance(principals, list):
        return False
    return bool(set(principals) & set(auth.principals))


def list_calendar_events(
    auth: AuthContext,
    project_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CalendarEventItem]:
    result: list[CalendarEventItem] = []
    for raw in load_fixture("calendar/events.json"):
        if not _allowed(raw, auth):
            continue
        payload = {
            key: value
            for key, value in raw.items()
            if key not in {"tenant_id", "acl_principals"}
        }
        item = CalendarEventItem.model_validate(payload)
        if project_id and item.project_id != project_id:
            continue
        if date_from and item.started_at < date_from:
            continue
        if date_to and item.started_at >= date_to:
            continue
        result.append(item)
    return sorted(result, key=lambda row: row.started_at)
