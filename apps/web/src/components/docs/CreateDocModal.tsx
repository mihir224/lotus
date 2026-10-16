import { FormEvent, useEffect, useState } from "react";
import { DOC_TYPE_OPTIONS } from "./docConstants";

export type DocDraft = {
  title: string;
  team: string;
  source_type: string;
  body: string;
};

type DocEditorModalProps = {
  open: boolean;
  teamOptions: string[];
  mode: "create" | "edit";
  initialValue?: DocDraft;
  onClose: () => void;
  onSave: (draft: DocDraft) => Promise<void>;
};

export function DocEditorModal({
  open,
  teamOptions,
  mode,
  initialValue,
  onClose,
  onSave
}: DocEditorModalProps) {
  const [title, setTitle] = useState("");
  const [team, setTeam] = useState(teamOptions[0] ?? "Platform");
  const [sourceType, setSourceType] = useState("guide");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(initialValue?.title ?? "");
    setTeam(initialValue?.team ?? teamOptions[0] ?? "Platform");
    setSourceType(initialValue?.source_type ?? "guide");
    setBody(initialValue?.body ?? "");
    setError(null);
  }, [open, initialValue, teamOptions]);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave({
        title: title.trim(),
        team: team.trim(),
        source_type: sourceType,
        body: body.trim()
      });
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create document");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="lotus-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="lotus-modal docs-create-modal"
        role="dialog"
        aria-labelledby="docs-create-title"
        onClick={(event) => event.stopPropagation()}
      >
        <form onSubmit={submit}>
          <header className="lotus-modal-head">
            <span className="lotus-modal-icon" aria-hidden="true">{mode === "edit" ? "✎" : "＋"}</span>
            <div className="lotus-modal-head-main">
              <p className="lotus-modal-kicker">{mode === "edit" ? "Edit document" : "New document"}</p>
              <h2 id="docs-create-title">{mode === "edit" ? "Update page" : "Create a page"}</h2>
              <p className="lotus-modal-desc">
                {mode === "edit"
                  ? "Update this document and refresh its searchable representation."
                  : "Add a new guide, runbook, or other document to your workspace."}
              </p>
            </div>
            <button type="button" className="lotus-modal-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </header>

          <div className="lotus-modal-body docs-create-body">
            <label className="board-field">
              <span>
                Title<span className="req">*</span>
              </span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Enter document title…"
                required
              />
            </label>
            <label className="board-field">
              <span>
                Team<span className="req">*</span>
              </span>
              <input
                list="docs-team-options"
                value={team}
                onChange={(event) => setTeam(event.target.value)}
                placeholder="Team name"
                required
              />
              <datalist id="docs-team-options">
                {teamOptions.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </label>
            <label className="board-field">
              <span>
                Type<span className="req">*</span>
              </span>
              <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
                {DOC_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="board-field">
              <span>
                Body<span className="req">*</span>
              </span>
              <textarea
                value={body}
                onChange={(event) => setBody(event.target.value)}
                rows={12}
                placeholder="Write the document content…"
                required
              />
            </label>
          </div>

          {error && <p className="error docs-create-error">{error}</p>}
          <footer className="lotus-modal-foot docs-create-actions">
            <button type="button" className="lotus-modal-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="lotus-modal-btn-primary" disabled={saving}>
              {saving ? "Saving…" : mode === "edit" ? "Save changes" : "Create document"}
              <span className="lotus-modal-btn-arrow" aria-hidden="true">
                →
              </span>
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
