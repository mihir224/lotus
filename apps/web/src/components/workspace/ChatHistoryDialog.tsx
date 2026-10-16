import type { ChatSession } from "../../types";

type Props = {
  open: boolean;
  sessions: ChatSession[];
  currentSessionId: string | null;
  loading: boolean;
  onClose: () => void;
  onNew: () => void;
  onOpen: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
};

export function ChatHistoryDialog(props: Props) {
  if (!props.open) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={props.onClose}>
      <section className="history-dialog" role="dialog" aria-modal="true" aria-label="Chat history" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><p className="eyebrow">Conversations</p><h2>Chat history</h2></div><button type="button" className="icon-button" onClick={props.onClose}>×</button></header>
        <button type="button" className="history-new" onClick={props.onNew}>＋ New conversation</button>
        {props.loading ? <p className="muted">Loading history…</p> : (
          <ul className="history-list">
            {props.sessions.map((session) => (
              <li key={session.session_id} className={session.session_id === props.currentSessionId ? "active" : ""}>
                <button type="button" className="history-open" onClick={() => props.onOpen(session.session_id)}>
                  <strong>{session.title}</strong>
                  <time>{new Date(session.updated_at).toLocaleString()}</time>
                </button>
                <button type="button" className="history-delete" aria-label={`Delete ${session.title}`} onClick={() => props.onDelete(session.session_id)}>×</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
