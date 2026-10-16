import { useCallback, useEffect, useMemo, useState } from "react";
import { BoardToolbar } from "./BoardToolbar";
import { avatarInitialsColor, BOARD_COLUMNS, featureAccentClass, priorityLabel } from "./boardConstants";
import { IssueDetailView } from "./IssueDetailView";
import {
  BOARD_ISSUE_UNASSIGNED,
  createBoardIssue,
  fetchWorkBoard,
  patchBoardIssue,
  type BoardAssignee,
  type BoardIssue,
  type BoardIssueStatus,
  type BoardIssueType,
  type WorkBoardPayload
} from "./workBoardApi";

function matchesFilters(
  issue: BoardIssue,
  search: string,
  assigneeFilter: Set<string>,
  typeFilter: BoardIssueType | "all"
): boolean {
  if (typeFilter !== "all" && issue.issue_type !== typeFilter) return false;
  if (assigneeFilter.size > 0 && !assigneeFilter.has(issue.assignee_id)) return false;
  if (!search.trim()) return true;
  const needle = search.trim().toLowerCase();
  return (
    issue.title.toLowerCase().includes(needle) ||
    issue.issue_key.toLowerCase().includes(needle) ||
    issue.feature_title.toLowerCase().includes(needle)
  );
}

export function WorkBoardView({
  initialProjectId,
  initialIssueKey
}: {
  initialProjectId?: string | null;
  initialIssueKey?: string | null;
}) {
  const [data, setData] = useState<WorkBoardPayload | null>(null);
  const [teamId, setTeamId] = useState<string>("platform");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<BoardIssue | null>(null);
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState<Set<string>>(() => new Set());
  const [typeFilter, setTypeFilter] = useState<BoardIssueType | "all">("all");
  const [creatingIssue, setCreatingIssue] = useState(false);
  const [createStatus, setCreateStatus] = useState<BoardIssueStatus>("ready_to_start");

  const load = useCallback(async (nextTeamId: string, projectId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const board = await fetchWorkBoard(projectId ?? initialProjectId ?? "payments", nextTeamId);
      setData(board);
      if (!projectId) setTeamId(nextTeamId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load work board");
    } finally {
      setLoading(false);
    }
  }, [initialProjectId]);

  useEffect(() => {
    void load(teamId);
  }, [teamId, load]);

  useEffect(() => {
    if (!initialIssueKey || !data) return;
    const issue = data.issues.find((row) => row.issue_key === initialIssueKey);
    if (issue) setSelectedIssue(issue);
  }, [data, initialIssueKey]);

  const assigneeById = useMemo(() => {
    const map = new Map<string, BoardAssignee>();
    for (const person of data?.assignees ?? []) map.set(person.assignee_id, person);
    return map;
  }, [data?.assignees]);

  const visibleIssues = useMemo(() => {
    if (!data) return [];
    return data.issues.filter((issue) =>
      matchesFilters(issue, search, assigneeFilter, typeFilter)
    );
  }, [data, search, assigneeFilter, typeFilter]);

  const activeTeamName =
    data?.teams.find((team) => team.team_id === teamId)?.name ?? teamId;

  const createDraft = useMemo((): BoardIssue | null => {
    if (!data) return null;
    return {
      issue_key: "",
      project_id: data.board.project_id,
      team_id: teamId,
      title: "",
      issue_type: "user_story",
      feature_key: "",
      feature_title: "",
      description: "",
      acceptance_criteria: [],
      priority: "medium",
      story_points: 0,
      sprint: null,
      reporter_id: BOARD_ISSUE_UNASSIGNED,
      status: createStatus,
      assignee_id: BOARD_ISSUE_UNASSIGNED
    };
  }, [data, teamId, createStatus]);

  async function applyIssueUpdate(issueKey: string, patch: Parameters<typeof patchBoardIssue>[1]) {
    const updated = await patchBoardIssue(issueKey, patch);
    setData((current) =>
      current
        ? {
            ...current,
            issues: current.issues.map((row) => (row.issue_key === issueKey ? updated : row))
          }
        : current
    );
    setSelectedIssue((current) => (current?.issue_key === issueKey ? updated : current));
  }

  async function handleDrop(status: BoardIssueStatus, issueKey: string) {
    const issue = data?.issues.find((row) => row.issue_key === issueKey);
    if (!issue || issue.status === status) return;
    try {
      await applyIssueUpdate(issueKey, { status });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to move card");
    } finally {
      setDraggingKey(null);
    }
  }

  function toggleAssignee(assigneeId: string) {
    setAssigneeFilter((current) => {
      const next = new Set(current);
      if (next.has(assigneeId)) next.delete(assigneeId);
      else next.add(assigneeId);
      return next;
    });
  }

  if (loading && !data) {
    return <div className="board-shell"><p className="board-muted">Loading work board…</p></div>;
  }

  if (error && !data) {
    return <div className="board-shell"><p className="error">{error}</p></div>;
  }

  if (!data) return null;

  return (
    <div className="board-shell">
      <header className="board-header">
        <div>
          <h1>{data.board.board_title}</h1>
        </div>
        <button
          type="button"
          className="board-primary-btn"
          onClick={() => {
            setCreateStatus("ready_to_start");
            setCreatingIssue(true);
          }}
        >
          Create
        </button>
      </header>

      <div className="board-team-tabs" role="tablist" aria-label="Teams">
        {data.teams.map((team) => (
          <button
            key={team.team_id}
            type="button"
            role="tab"
            aria-selected={team.team_id === teamId}
            className={`board-team-tab${team.team_id === teamId ? " active" : ""}`}
            onClick={() => setTeamId(team.team_id)}
          >
            {team.name}
          </button>
        ))}
      </div>

      <BoardToolbar
        search={search}
        onSearchChange={setSearch}
        assignees={data.assignees}
        assigneeFilter={assigneeFilter}
        onToggleAssignee={toggleAssignee}
        onClearAssignees={() => setAssigneeFilter(new Set())}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
      />

      {error && <p className="error board-inline-error">{error}</p>}

      <div className="board-columns">
        {BOARD_COLUMNS.map((column) => {
          const cards = visibleIssues.filter((issue) => issue.status === column.id);
          return (
            <section
              key={column.id}
              className="board-column"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                const key = event.dataTransfer.getData("text/plain");
                if (key) void handleDrop(column.id, key);
              }}
            >
              <header className="board-column-head">
                <div className="board-column-title">
                  <h2>{column.label}</h2>
                </div>
                <span className="board-count">{cards.length}</span>
              </header>
              <button
                type="button"
                className="board-column-create"
                onClick={() => {
                  setCreateStatus(column.id);
                  setCreatingIssue(true);
                }}
              >
                <span className="board-column-create-icon" aria-hidden="true">+</span>
                Create item
              </button>
              <ul className="board-card-list">
                {cards.map((issue) => {
                  const assignee = assigneeById.get(issue.assignee_id);
                  const accent = featureAccentClass(issue.feature_key);
                  return (
                    <li key={issue.issue_key}>
                      <button
                        type="button"
                        className={`board-card ${accent}${draggingKey === issue.issue_key ? " dragging" : ""}`}
                        draggable
                        onDragStart={(event) => {
                          event.dataTransfer.setData("text/plain", issue.issue_key);
                          event.dataTransfer.effectAllowed = "move";
                          setDraggingKey(issue.issue_key);
                        }}
                        onDragEnd={() => setDraggingKey(null)}
                        onClick={() => setSelectedIssue(issue)}
                      >
                        <span className="board-card-accent" aria-hidden="true" />
                        <div className="board-card-body">
                          <div className="board-card-top">
                            <span className="board-card-key">{issue.issue_key}</span>
                            <span
                              className={`board-priority-pill board-priority-${issue.priority}`}
                            >
                              <span className="board-priority-glyph" aria-hidden="true">
                                {issue.priority === "high"
                                  ? "▲"
                                  : issue.priority === "medium"
                                    ? "◆"
                                    : "▼"}
                              </span>
                              {priorityLabel(issue.priority)}
                            </span>
                            <span className="board-card-more" aria-hidden="true">
                              ···
                            </span>
                          </div>
                          <p className="board-card-title">{issue.title}</p>
                          <p className={`board-feature-chip ${accent}`}>
                            <span className="board-feature-icon" aria-hidden="true">
                              ◫
                            </span>
                            <span className="board-feature-text">{issue.feature_title}</span>
                          </p>
                          <div className="board-card-footer">
                            <div className="board-card-assignee">
                              <span
                                className="board-avatar board-avatar-sm board-card-avatar"
                                style={{
                                  background: assignee?.avatar_color ?? "#3d4f48",
                                  color: avatarInitialsColor(assignee?.avatar_color ?? "#3d4f48")
                                }}
                              >
                                {assignee?.initials ?? "?"}
                              </span>
                              <span className="board-card-assignee-name">
                                {assignee?.name ?? "Unassigned"}
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      {creatingIssue && createDraft && (
        <IssueDetailView
          mode="create"
          issue={createDraft}
          assignees={data.assignees}
          teamName={activeTeamName}
          onClose={() => setCreatingIssue(false)}
          onCreate={async (payload) => {
            const created = await createBoardIssue(payload);
            setData((current) =>
              current ? { ...current, issues: [...current.issues, created] } : current
            );
          }}
        />
      )}

      {selectedIssue && (
        <IssueDetailView
          mode="edit"
          issue={selectedIssue}
          assignees={data.assignees}
          teamName={activeTeamName}
          onClose={() => setSelectedIssue(null)}
          onSave={(patch) => applyIssueUpdate(selectedIssue.issue_key, patch)}
        />
      )}
    </div>
  );
}
