import { useEffect, useRef, useState } from "react";
import {
  authHeaders,
  type AuthConfig,
  type AuthSession,
  GoogleLogin,
  signOut,
  storedAuthSession
} from "./auth";
import { CalendarView } from "./CalendarView";
import type { GroundedAnswer } from "./types";
import type { RunEvent } from "./types";
import { ChatComposer } from "./ChatComposer";
import { MarkdownMessage } from "./MarkdownMessage";
import { RunInspector } from "./RunInspector";
import { streamChat } from "./chatStream";

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
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [session, setSession] = useState<AuthSession | null>(storedAuthSession);
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("planner");
  const [message, setMessage] = useState("");
  const [submittedMessage, setSubmittedMessage] = useState("");
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const runEventsRef = useRef<RunEvent[]>([]);
  const [drawerTab, setDrawerTab] = useState<"evidence" | "run">("evidence");
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const [chatSessionId] = useState(() => {
    const existing = sessionStorage.getItem("lotus.session_id");
    if (existing) return existing;
    const created = crypto.randomUUID();
    sessionStorage.setItem("lotus.session_id", created);
    return created;
  });

  useEffect(() => {
    fetch("/v1/auth/config")
      .then(async (response) => {
        if (!response.ok) throw new Error(`Authentication config failed with ${response.status}`);
        setAuthConfig((await response.json()) as AuthConfig);
      })
      .catch((reason) => {
        setAuthConfigError(reason instanceof Error ? reason.message : "Unable to load authentication");
      });
  }, []);

  if (authConfigError) {
    return <main className="login-shell"><div className="error">{authConfigError}</div></main>;
  }
  if (!authConfig) {
    return <main className="login-shell"><p>Loading Lotus…</p></main>;
  }
  if (authConfig.mode === "google" && !session) {
    if (!authConfig.google_client_id) {
      return <main className="login-shell"><div className="error">Google OAuth is not configured.</div></main>;
    }
    return <GoogleLogin clientId={authConfig.google_client_id} onAuthenticated={setSession} />;
  }

  async function submit() {
    if (!message.trim() || loading) return;
    const prompt = message.trim();
    setSubmittedMessage(prompt);
    setMessage("");
    setLoading(true);
    setError(null);
    setAnswer(null);
    setStreamedAnswer("");
    setRunEvents([]);
    setFeedback(null);
    setCopied(false);
    runEventsRef.current = [];
    setDrawerTab("run");
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      await streamChat(
        { message: prompt, project_id: "payments", session_id: chatSessionId },
        authHeaders(true),
        (event) => {
          setRunEvents((previous) => {
            const next = [...previous, event].slice(-500);
            runEventsRef.current = next;
            sessionStorage.setItem("lotus.latest_run", JSON.stringify(next));
            return next;
          });
          if (event.event_type === "answer.delta" && event.answer_delta) {
            setStreamedAnswer((previous) => previous + event.answer_delta);
          }
          if (event.event_type === "answer.completed" && event.response) {
            setAnswer(event.response);
            setDrawerTab("evidence");
            const stored = JSON.parse(sessionStorage.getItem("lotus.completed_runs") ?? "[]") as RunEvent[][];
            sessionStorage.setItem(
              "lotus.completed_runs",
              JSON.stringify([...stored, runEventsRef.current].slice(-10))
            );
          }
          if (event.event_type === "run.failed") throw new Error("The Lotus run failed.");
        },
        controller.signal
      );
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        setError("Run cancelled.");
      } else {
        setError(reason instanceof Error ? reason.message : "Unable to reach Lotus API");
      }
    } finally {
      setLoading(false);
      controllerRef.current = null;
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
          {session && (
            <>
              <i />
              <strong>{session.name ?? session.email}</strong>
              <button
                type="button"
                className="signout-btn"
                onClick={() => {
                  signOut();
                  setSession(null);
                }}
              >
                Sign out
              </button>
            </>
          )}
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

              {submittedMessage && <p className="last-prompt">{submittedMessage}</p>}

              {(answer || streamedAnswer) && (
                <article className="answer-card">
                  <MarkdownMessage>{answer?.answer ?? streamedAnswer}</MarkdownMessage>
                  {answer && (
                    <div className="response-actions" aria-label="Response actions">
                      <button
                        type="button"
                        className={feedback === "like" ? "active" : ""}
                        aria-label="Like response"
                        title="Like"
                        onClick={() => setFeedback(feedback === "like" ? null : "like")}
                      >
                        <span aria-hidden="true">👍</span>
                      </button>
                      <button
                        type="button"
                        className={feedback === "dislike" ? "active" : ""}
                        aria-label="Dislike response"
                        title="Dislike"
                        onClick={() => setFeedback(feedback === "dislike" ? null : "dislike")}
                      >
                        <span aria-hidden="true">👎</span>
                      </button>
                      <button
                        type="button"
                        aria-label="Copy response"
                        title="Copy"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(answer.answer);
                            setCopied(true);
                            window.setTimeout(() => setCopied(false), 1600);
                          } catch {
                            setError("Unable to copy the response.");
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
                  <span className="typing-dots" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                </div>
              )}
              <ChatComposer
                value={message}
                loading={loading}
                onChange={setMessage}
                onSubmit={submit}
                onCancel={() => controllerRef.current?.abort()}
              />
            </>
          )}
        </section>

        <aside className="evidence" aria-label="Evidence drawer">
          <div className="drawer-head">
            <div className="drawer-tabs">
              <button className={drawerTab === "evidence" ? "active" : ""} onClick={() => setDrawerTab("evidence")}>Evidence</button>
              <button className={drawerTab === "run" ? "active" : ""} onClick={() => setDrawerTab("run")}>Run</button>
            </div>
            <span>{drawerTab === "evidence" ? answer?.evidence.length ?? 0 : runEvents.filter((item) => item.node_id).length}</span>
          </div>
          {drawerTab === "run" ? <RunInspector events={runEvents} /> : <>
          {!answer && <p className="empty">Sources used for an answer will appear here with scope and provenance.</p>}
          {answer?.evidence.map((item, index) => (
            <article className="source" key={`${item.source_id}-${index}`}>
              <div><span>[{index + 1}]</span><small>{item.retrieval_method.replace("_", " ")}</small></div>
              <h3>{item.title ?? item.source_id}</h3>
              <p>{item.snippet}</p>
              <footer><strong>{item.source_type}</strong><span>{item.source_id}</span></footer>
            </article>
          ))}</>}
        </aside>
      </section>
    </main>
  );
}
