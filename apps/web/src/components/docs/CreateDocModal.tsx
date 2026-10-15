import { FormEvent, useState } from "react";
import { DOC_TYPE_OPTIONS } from "./docConstants";

type CreateDocModalProps = {
  open: boolean;
  teamOptions: string[];
  onClose: () => void;
  onCreate: (draft: {
    title: string;
    team: string;
    source_type: string;
    body: string;
  }) => Promise<void>;
};

export function CreateDocModal({ open, teamOptions, onClose, onCreate }: CreateDocModalProps) {
  const [title, setTitle] = useState("");
  const [team, setTeam] = useState(teamOptions[0] ?? "Platform");
  const [sourceType, setSourceType] = useState("guide");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onCreate({
        title: title.trim(),
        team: team.trim(),
        source_type: sourceType,
        body: body.trim()
      });
      setTitle("");
      setBody("");
      setSourceType("guide");
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create document");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="board-detail-overlay" role="presentation" onClick={onClose}>
      <div
        className="docs-create-modal"
        role="dialog"
        aria-labelledby="docs-create-title"
        onClick={(event) => event.stopPropagation()}
      >
        <form onSubmit={submit}>
          <header className="docs-create-head">
            <div>
              <p className="eyebrow">New document</p>
              <h2 id="docs-create-title">Create a page</h2>
            </div>
            <button type="button" className="board-icon-btn" onClick={onClose} aria-label="Close">
              ×
            </button>
          </header>

          <div className="docs-create-body">
            <label className="board-field">
              <span>Title</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Document title"
                required
              />
            </label>
            <label className="board-field">
              <span>Team</span>
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
              <span>Type</span>
              <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
                {DOC_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="board-field">
              <span>Body</span>
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
          <footer className="docs-create-actions">
            <button type="button" className="board-secondary-btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="board-primary-btn" disabled={saving}>
              {saving ? "Creating…" : "Create document"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
