import { FormEvent, useState } from "react";
import { CalendarView } from "./CalendarView";
import type { GroundedAnswer } from "./types";

type WorkspaceTab = "planner" | "specialists" | "result" | "calendar";

const workflowTabs: { id: WorkspaceTab; label: string }[] = [
  { id: "planner", label: "Planner" },
  { id: "specialists", label: "Specialists" },
  { id: "result", label: "Result" },
  { id: "calendar", label: "Calendar" }
];

const suggestions = [
  "Why are checkout retries capped, and what should on-call do?",
  "What is the current status of PAY-123?",
  "What is the lunar office dress code?"
];

export function App() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("planner");
  const [message, setMessage] = useState(suggestions[0]);
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/v1/chat/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Lotus-Tenant": "demo",
          "X-Lotus-User": "demo-user"
        },
        body: JSON.stringify({ message, project_id: "payments" })
      });
      if (!response.ok) throw new Error(`Request failed with ${response.status}`);
      setAnswer((await response.json()) as GroundedAnswer);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reach Lotus API");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="lotus-mark" aria-hidden="true">✦</div>
          <div>
            <strong>Lotus</strong>
            <span>Enterprise workspace</span>
          </div>
        </div>
        <div className="context">
          <span>Project</span>
          <strong>Payments</strong>
          <i />
          <span>Environment</span>
          <strong>Fixture demo</strong>
        </div>
      </header>

      <section className="workspace">
        <aside className="rail" aria-label="Agent workflow">
          <p className="eyebrow">Agent workflow</p>
          {workflowTabs.map((item, index) => (
            <button
              type="button"
              className={`mode${activeTab === item.id ? " active" : ""}`}
              key={item.id}
              onClick={() => setActiveTab(item.id)}
            >
              <span>{index + 1}</span>
              {item.label}
            </button>
          ))}
          <div className="rail-note">
            <span className="pulse" />
            <div><strong>Local ready</strong><small>No cloud credentials</small></div>
          </div>
        </aside>

        <section className={`conversation${activeTab === "calendar" ? " conversation-calendar" : ""}`}>
          {activeTab === "calendar" ? (
            <CalendarView today={new Date()} />
          ) : (
            <>
              <div className="intro">
                <p className="eyebrow">Trusted answers, visible evidence</p>
                <h1>What do you need to understand?</h1>
                <p>Ask across product knowledge, architecture, runbooks, and exact source records.</p>
              </div>

              <div className="suggestions">
                {suggestions.map((item) => (
                  <button type="button" onClick={() => setMessage(item)} key={item}>{item}</button>
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
                    <div className="uncertainty"><strong>Uncertainty</strong>{answer.uncertainty.join(" ")}</div>
                  )}
                </article>
              )}

              {error && <div className="error">{error}</div>}

              <form className="composer" onSubmit={submit}>
                <textarea
                  aria-label="Ask Lotus"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  rows={3}
                />
                <div>
                  <span>Planner selects the right agents automatically</span>
                  <button type="submit" disabled={loading}>{loading ? "Checking sources…" : "Ask Lotus"}</button>
                </div>
              </form>
            </>
          )}
        </section>

        <aside className="evidence" aria-label="Evidence drawer">
          <div className="drawer-head">
            <div><p className="eyebrow">Evidence</p><h2>Source trail</h2></div>
            <span>{answer?.evidence.length ?? 0}</span>
          </div>
          {!answer && <p className="empty">Sources used for an answer will appear here with scope and provenance.</p>}
          {answer?.evidence.map((item, index) => (
            <article className="source" key={`${item.source_id}-${index}`}>
              <div><span>[{index + 1}]</span><small>{item.retrieval_method.replace("_", " ")}</small></div>
              <h3>{item.title ?? item.source_id}</h3>
              <p>{item.snippet}</p>
              <footer><strong>{item.source_type}</strong><span>{item.source_id}</span></footer>
            </article>
          ))}
        </aside>
      </section>
    </main>
  );
}
