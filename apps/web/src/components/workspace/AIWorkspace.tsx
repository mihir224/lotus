import { FormEvent } from "react";
import type { GroundedAnswer } from "../../types";

const suggestions = [
  "Why are checkout retries capped, and what should on-call do?",
  "What is the current status of PAY-123?",
  "What is the lunar office dress code?"
];

type AIWorkspaceProps = {
  message: string;
  onMessageChange: (value: string) => void;
  answer: GroundedAnswer | null;
  loading: boolean;
  error: string | null;
  onSubmit: (event: FormEvent) => void;
};

export function AIWorkspace({
  message,
  onMessageChange,
  answer,
  loading,
  error,
  onSubmit
}: AIWorkspaceProps) {
  return (
    <>
      <div className="intro">
        <p className="eyebrow">Trusted answers, visible evidence</p>
        <h1>What do you need to understand?</h1>
        <p>Ask across product knowledge, architecture, runbooks, and exact source records.</p>
      </div>

      <div className="suggestions">
        {suggestions.map((item) => (
          <button type="button" onClick={() => onMessageChange(item)} key={item}>
            {item}
          </button>
        ))}
      </div>

      {answer && (
        <article className="answer-card">
          <div className="answer-head">
            <span className="route-chip">{answer.route.route}</span>
            <span>{answer.agents_used.join(" → ")}</span>
            <span>{answer.route.live_retrieval ? "Live web retrieval" : "Indexed retrieval"}</span>
          </div>
          <h2>Answer</h2>
          <p>{answer.answer}</p>
          {answer.uncertainty.length > 0 && (
            <div className="uncertainty">
              <strong>Uncertainty</strong>
              {answer.uncertainty.join(" ")}
            </div>
          )}
        </article>
      )}

      {error && <div className="error">{error}</div>}

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          aria-label="Ask Lotus"
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          rows={3}
        />
        <div>
          <span>Planner selects the right agents automatically</span>
          <button type="submit" disabled={loading}>
            {loading ? "Checking sources…" : "Ask Lotus"}
          </button>
        </div>
      </form>
    </>
  );
}
