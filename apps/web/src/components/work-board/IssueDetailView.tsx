import { FormEvent, useEffect, useMemo, useState } from "react";
import { BOARD_COLUMNS, ISSUE_TYPE_LABEL, featureAccentClass } from "./boardConstants";
import { SearchableSelect } from "./SearchableSelect";
import {
  BOARD_ISSUE_UNASSIGNED,
  type BoardAssignee,
  type BoardIssue,
  type BoardIssueCreatePayload,
  type BoardIssueType
} from "./workBoardApi";

type IssueSavePayload = {
  title: string;
  issue_type: BoardIssueType;
  status: BoardIssue["status"];
  assignee_id: string;
  description: string;
  acceptance_criteria: string[];
  priority: BoardIssue["priority"];
  story_points: number;
  reporter_id: string;
};

type IssueDetailViewProps = {
  mode: "edit" | "create";
  issue: BoardIssue;
  assignees: BoardAssignee[];
  teamName: string;
  onClose: () => void;
  onSave?: (patch: IssueSavePayload) => Promise<void>;
  onCreate?: (payload: BoardIssueCreatePayload) => Promise<void>;
};

const TYPE_OPTIONS = Object.entries(ISSUE_TYPE_LABEL).map(([value, label]) => ({
  value,
  label
}));

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" }
];

export function IssueDetailView({
  mode,
  issue,
  assignees,
  teamName,
  onClose,
  onSave,
  onCreate
}: IssueDetailViewProps) {
  const isCreate = mode === "create";
  const [title, setTitle] = useState(issue.title);
  const [issueType, setIssueType] = useState(issue.issue_type);
  const [status, setStatus] = useState(issue.status);
  const [assigneeId, setAssigneeId] = useState(issue.assignee_id);
  const [reporterId, setReporterId] = useState(issue.reporter_id);
  const [featureKey, setFeatureKey] = useState(issue.feature_key);
  const [description, setDescription] = useState(issue.description);
  const [criteriaText, setCriteriaText] = useState(issue.acceptance_criteria.join("\n"));
  const [priority, setPriority] = useState(issue.priority);
  const [storyPoints, setStoryPoints] = useState(issue.story_points);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const personOptions = useMemo(
    () => [
      { value: BOARD_ISSUE_UNASSIGNED, label: "Unassigned" },
      ...assignees.map((person) => ({
        value: person.assignee_id,
        label: person.name
      }))
    ],
    [assignees]
  );

  const statusOptions = BOARD_COLUMNS.map((column) => ({
    value: column.id,
    label: column.label
  }));

  useEffect(() => {
    setTitle(issue.title);
    setIssueType(issue.issue_type);
    setStatus(issue.status);
    setAssigneeId(issue.assignee_id);
    setReporterId(issue.reporter_id);
    setFeatureKey(issue.feature_key);
    setDescription(issue.description);
    setCriteriaText(issue.acceptance_criteria.join("\n"));
    setPriority(issue.priority);
    setStoryPoints(issue.story_points);
  }, [issue]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const acceptance_criteria = criteriaText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const trimmedTitle = title.trim();
    const trimmedFeatureKey = featureKey.trim();
    try {
      if (isCreate) {
        if (!onCreate) throw new Error("Create handler missing");
        if (!trimmedFeatureKey) {
          throw new Error("Feature key is required");
        }
        await onCreate({
          title: trimmedTitle,
          project_id: issue.project_id,
          team_id: issue.team_id,
          feature_key: trimmedFeatureKey,
          issue_type: issueType,
          status,
          assignee_id: assigneeId,
          reporter_id: reporterId,
          description: description.trim(),
          acceptance_criteria,
          priority,
          story_points: storyPoints
        });
      } else {
        if (!onSave) throw new Error("Save handler missing");
        await onSave({
          title: trimmedTitle,
          issue_type: issueType,
          status,
          assignee_id: assigneeId,
          description: description.trim(),
          acceptance_criteria,
          priority,
          story_points: storyPoints,
          reporter_id: reporterId
        });
      }
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save");
    } finally {
      setSaving(false);
    }
  }

  const breadcrumbFeatureKey = isCreate ? featureKey || "Feature key" : issue.feature_key;
  const breadcrumbIssueKey = isCreate ? "New issue" : issue.issue_key;

  return (
    <div className="lotus-modal-overlay board-detail-overlay" role="presentation" onClick={onClose}>
      <div
        className="lotus-modal lotus-modal-wide board-detail"
        role="dialog"
        aria-labelledby="board-detail-title"
        onClick={(event) => event.stopPropagation()}
      >
        <form className="board-detail-form" onSubmit={submit}>
          <header className={`board-detail-head${isCreate ? " lotus-modal-head" : ""}`}>
            {isCreate && (
              <span className="lotus-modal-icon" aria-hidden="true">
                ◫
              </span>
            )}
            <div className={`board-detail-head-main${isCreate ? " lotus-modal-head-main" : ""}`}>
              {isCreate && <p className="lotus-modal-kicker">New work item</p>}
              <p className="board-detail-breadcrumb">
                <span className={featureAccentClass(breadcrumbFeatureKey)}>
                  {breadcrumbFeatureKey}
                </span>
                <span aria-hidden="true"> / </span>
                <span>{breadcrumbIssueKey}</span>
                <span className={`board-detail-type board-type-${issueType}`}>
                  {ISSUE_TYPE_LABEL[issueType]}
                </span>
              </p>
              <input
                id="board-detail-title"
                className="board-detail-title-input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={isCreate ? "Issue title" : undefined}
                required
              />
            </div>
            <button type="button" className="lotus-modal-close board-icon-btn" onClick={onClose} aria-label="Close">
              ×
            </button>
          </header>

          <div className="board-detail-columns">
            <div className="board-detail-main">
              <section className="board-detail-panel">
                <h3>Description</h3>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={8}
                  placeholder={
                    isCreate ? "Describe the work, context, and any links the team needs." : undefined
                  }
                />
              </section>
              <section className="board-detail-panel">
                <h3>Acceptance criteria</h3>
                <textarea
                  value={criteriaText}
                  onChange={(event) => setCriteriaText(event.target.value)}
                  rows={8}
                  placeholder={
                    isCreate
                      ? "One criterion per line (optional)"
                      : "One criterion per line"
                  }
                />
              </section>
            </div>

            <aside className="board-detail-sidebar">
              <h3>Details</h3>
              <div className="board-detail-fields">
                <SearchableSelect
                  label="Status"
                  value={status}
                  options={statusOptions}
                  onChange={(next) => setStatus(next as BoardIssue["status"])}
                />
                <SearchableSelect
                  label="Type"
                  value={issueType}
                  options={TYPE_OPTIONS}
                  onChange={(next) => setIssueType(next as BoardIssueType)}
                />
                {isCreate ? (
                  <label className="board-field">
                    <span>Feature key</span>
                    <input
                      type="text"
                      value={featureKey}
                      onChange={(event) => setFeatureKey(event.target.value)}
                      placeholder="e.g. PROJ-42"
                      required
                    />
                  </label>
                ) : (
                  <div className="board-detail-readonly">
                    <span>Parent</span>
                    <p className={`board-feature-chip ${featureAccentClass(issue.feature_key)}`}>
                      <span className="board-feature-swatch" aria-hidden="true" />
                      <span className="board-feature-text">{issue.feature_title}</span>
                    </p>
                  </div>
                )}
                <SearchableSelect
                  label="Priority"
                  value={priority}
                  options={PRIORITY_OPTIONS}
                  onChange={(next) => setPriority(next as BoardIssue["priority"])}
                />
                <label className="board-field">
                  <span>Story points</span>
                  <input
                    type="number"
                    min={0}
                    max={99}
                    value={isCreate && storyPoints === 0 ? "" : storyPoints}
                    placeholder={isCreate ? "Optional" : undefined}
                    onChange={(event) => {
                      const raw = event.target.value;
                      setStoryPoints(raw === "" ? 0 : Number(raw));
                    }}
                  />
                </label>
                <div className="board-detail-readonly">
                  <span>Sprint</span>
                  <p>{issue.sprint ?? "—"}</p>
                </div>
                <SearchableSelect
                  label="Assignee"
                  value={assigneeId}
                  options={personOptions}
                  onChange={setAssigneeId}
                  placeholder="Unassigned"
                />
                <SearchableSelect
                  label="Reporter"
                  value={reporterId}
                  options={personOptions}
                  onChange={setReporterId}
                  placeholder="Unassigned"
                />
                <div className="board-detail-readonly">
                  <span>Team</span>
                  <p>{teamName}</p>
                </div>
              </div>
            </aside>
          </div>

          {error && <p className="error board-detail-error">{error}</p>}
          <footer className="lotus-modal-foot board-detail-actions">
            <button type="button" className="lotus-modal-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="lotus-modal-btn-primary" disabled={saving}>
              {isCreate ? "◫ " : ""}
              {saving ? (isCreate ? "Creating…" : "Saving…") : isCreate ? "Create issue" : "Save changes"}
              {isCreate && (
                <span className="lotus-modal-btn-arrow" aria-hidden="true">
                  →
                </span>
              )}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
