import { ChatComposer } from "../../ChatComposer";
import { MarkdownMessage } from "../../MarkdownMessage";
import type { GroundedAnswer } from "../../types";

const suggestions = [
  "Why are checkout retries capped, and what should on-call do?",
  "What is the current status of PAY-123?",
  "What is the lunar office dress code?"
];

type Feedback = "like" | "dislike" | null;

type AIWorkspaceProps = {
  message: string;
  onMessageChange: (value: string) => void;
  submittedMessage: string;
  answer: GroundedAnswer | null;
  streamedAnswer: string;
  loading: boolean;
  error: string | null;
  feedback: Feedback;
  copied: boolean;
  onFeedbackChange: (value: Feedback) => void;
  onCopiedChange: (value: boolean) => void;
  onError: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

function ThumbIcon({ down = false }: { down?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="response-action-icon" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <g transform={down ? "rotate(180 12 12)" : undefined}>
        <path d="M7 10v12" />
        <path d="M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 8a2 2 0 0 1-1.9 1.4H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9Z" />
      </g>
    </svg>
  );
}

export function AIWorkspace({
  message,
  onMessageChange,
  submittedMessage,
  answer,
  streamedAnswer,
  loading,
  error,
  feedback,
  copied,
  onFeedbackChange,
  onCopiedChange,
  onError,
  onSubmit,
  onCancel
}: AIWorkspaceProps) {
  return (
    <>
      <div className="intro">
        <p className="eyebrow">Trusted answers, visible evidence</p>
        <h1>What do you need to understand?</h1>
        <p>Ask across product knowledge, architecture, runbooks, meetings, and public research.</p>
      </div>

      <div className="suggestions">
        {suggestions.map((item) => (
          <button type="button" onClick={() => onMessageChange(item)} key={item}>{item}</button>
        ))}
      </div>

      {submittedMessage && <p className="last-prompt">{submittedMessage}</p>}

      {(answer || streamedAnswer) && (
        <article className="answer-card">
          <MarkdownMessage>{answer?.answer ?? streamedAnswer}</MarkdownMessage>
          {answer && (
            <div className="response-actions" aria-label="Response actions">
              <button type="button" className={feedback === "like" ? "active" : ""} aria-label="Like response" title="Like" onClick={() => onFeedbackChange(feedback === "like" ? null : "like")}>
                <ThumbIcon />
              </button>
              <button type="button" className={feedback === "dislike" ? "active" : ""} aria-label="Dislike response" title="Dislike" onClick={() => onFeedbackChange(feedback === "dislike" ? null : "dislike")}>
                <ThumbIcon down />
              </button>
              <button
                type="button"
                aria-label="Copy response"
                title="Copy"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(answer.answer);
                    onCopiedChange(true);
                    window.setTimeout(() => onCopiedChange(false), 1600);
                  } catch {
                    onError("Unable to copy the response.");
                  }
                }}
              >
                <span aria-hidden="true">{copied ? "✓" : "⧉"}</span>
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
          )}
        </article>
      )}

      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="progress-line" role="status" aria-live="polite">
          <strong>Thinking</strong>
          <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span>
        </div>
      )}
      <ChatComposer value={message} loading={loading} onChange={onMessageChange} onSubmit={onSubmit} onCancel={onCancel} />
    </>
  );
}
