import json
import re

from .config import get_settings
from .models import (
    AuthContext,
    BOARD_ISSUE_UNASSIGNED,
    BoardAssignee,
    BoardIssueCreate,
    BoardIssueItem,
    BoardIssueUpdate,
    BoardMeta,
    BoardTeam,
    WorkBoardResponse,
)
from .storage.base import KnowledgeStore


def _read_fixture(name: str) -> object:
    path = get_settings().fixture_dir / name
    return json.loads(path.read_text(encoding="utf-8"))


def get_work_board(
    store: KnowledgeStore,
    auth: AuthContext,
    project_id: str | None = None,
    team_id: str | None = None,
) -> WorkBoardResponse:
    board = BoardMeta.model_validate(_read_fixture("work_board/board.json"))
    teams = [BoardTeam.model_validate(row) for row in _read_fixture("work_board/teams.json")]
    assignees = [
        BoardAssignee.model_validate(row) for row in _read_fixture("work_board/assignees.json")
    ]
    scoped_project = project_id or board.project_id
    issues = store.list_board_issues(auth, scoped_project, team_id)
    return WorkBoardResponse(
        board=board,
        teams=teams,
        assignees=assignees,
        issues=issues,
    )


def _team_for_id(team_id: str) -> BoardTeam:
    teams = [BoardTeam.model_validate(row) for row in _read_fixture("work_board/teams.json")]
    for team in teams:
        if team.team_id == team_id:
            return team
    raise LookupError(team_id)


def _feature_for_key(feature_key: str, team_id: str) -> tuple[str, str]:
    rows = _read_fixture("work_board/features.json")
    if not isinstance(rows, list):
        raise ValueError("Invalid features fixture")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("feature_key") == feature_key and row.get("team_id") == team_id:
            title = row.get("title")
            if isinstance(title, str) and title.strip():
                return feature_key, title.strip()
    raise ValueError("Unknown feature_key for this team")


def _assignee_ids() -> set[str]:
    rows = _read_fixture("work_board/assignees.json")
    if not isinstance(rows, list):
        return set()
    return {
        str(row["assignee_id"])
        for row in rows
        if isinstance(row, dict) and row.get("assignee_id")
    }


def _validate_person_field(field_name: str, person_id: str) -> None:
    if person_id == BOARD_ISSUE_UNASSIGNED:
        return
    if person_id not in _assignee_ids():
        raise ValueError(f"Unknown {field_name}")


def _next_issue_key(store: KnowledgeStore, auth: AuthContext, key_prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(key_prefix)}-(\d+)$")
    max_number = 0
    for issue in store.list_board_issues(auth, None, None):
        match = pattern.match(issue.issue_key)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{key_prefix}-{max_number + 1}"


def create_board_issue(
    store: KnowledgeStore,
    auth: AuthContext,
    payload: BoardIssueCreate,
) -> BoardIssueItem:
    team = _team_for_id(payload.team_id)
    _validate_person_field("assignee_id", payload.assignee_id)
    _validate_person_field("reporter_id", payload.reporter_id)

    feature_key, feature_title = _feature_for_key(payload.feature_key.strip(), payload.team_id)
    issue_key = _next_issue_key(store, auth, team.key_prefix)
    item = BoardIssueItem(
        issue_key=issue_key,
        project_id=payload.project_id,
        team_id=payload.team_id,
        title=payload.title.strip(),
        issue_type=payload.issue_type,
        feature_key=feature_key,
        feature_title=feature_title,
        description=payload.description.strip(),
        acceptance_criteria=payload.acceptance_criteria,
        priority=payload.priority,
        story_points=payload.story_points,
        sprint=None,
        reporter_id=payload.reporter_id,
        status=payload.status,
        assignee_id=payload.assignee_id,
    )
    return store.upsert_board_issue(auth, item)


def update_board_issue(
    store: KnowledgeStore,
    issue_key: str,
    auth: AuthContext,
    patch: BoardIssueUpdate,
) -> BoardIssueItem:
    if not patch.model_fields_set:
        raise ValueError("At least one field is required")
    if patch.assignee_id is not None:
        _validate_person_field("assignee_id", patch.assignee_id)
    if patch.reporter_id is not None:
        _validate_person_field("reporter_id", patch.reporter_id)
    updated = store.update_board_issue(issue_key, auth, patch)
    if updated is None:
        raise LookupError(issue_key)
    return updated
