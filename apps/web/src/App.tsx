import { useEffect, useRef, useState } from "react";
import {
  authHeaders,
  type AuthConfig,
  type AuthSession,
  GoogleLogin,
  signOut,
  storedAuthSession
} from "./auth";
import { streamChat } from "./chatStream";
import { CalendarView } from "./components/calendar/CalendarView";
import { DocsView } from "./components/docs/DocsView";
import { AppRail } from "./components/navigation/AppRail";
import type { AppSection } from "./components/navigation/types";
import { ProfileAvatar } from "./components/profile/ProfileAvatar";
import { ProfilePanel } from "./components/profile/ProfilePanel";
import { useUserProfile } from "./components/profile/useUserProfile";
import { WorkBoardView } from "./components/work-board/WorkBoardView";
import { AIWorkspace } from "./components/workspace/AIWorkspace";
import { EvidenceDrawer } from "./components/workspace/EvidenceDrawer";
import type { GroundedAnswer, RunEvent } from "./types";

export function App() {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [session, setSession] = useState<AuthSession | null>(storedAuthSession);
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<AppSection>("chat");
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
  const [profileOpen, setProfileOpen] = useState(false);
  const { profile } = useUserProfile(session, authConfig?.mode ?? "dev");

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

  function renderMainContent() {
    switch (activeSection) {
      case "work-board":
        return <WorkBoardView />;
      case "docs":
        return <DocsView />;
      case "calendar":
        return <CalendarView today={new Date()} />;
      case "chat":
        return (
          <AIWorkspace
            message={message}
            onMessageChange={setMessage}
            submittedMessage={submittedMessage}
            answer={answer}
            streamedAnswer={streamedAnswer}
            loading={loading}
            error={error}
            feedback={feedback}
            copied={copied}
            onFeedbackChange={setFeedback}
            onCopiedChange={setCopied}
            onError={setError}
            onSubmit={submit}
            onCancel={() => controllerRef.current?.abort()}
          />
        );
      default:
        return null;
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="lotus-mark" aria-hidden="true">✦</div>
          <div><strong>Lotus</strong><span>Enterprise workspace</span></div>
        </div>
        {profile && (
          <button type="button" className="profile-topbar-btn" aria-label="Open profile" aria-expanded={profileOpen} onClick={() => setProfileOpen(true)}>
            <ProfileAvatar profile={profile} size={40} />
          </button>
        )}
      </header>

      {profile && (
        <ProfilePanel
          open={profileOpen}
          profile={profile}
          onClose={() => setProfileOpen(false)}
          showSignOut={authConfig.mode === "google" && Boolean(session)}
          onSignOut={() => {
            signOut();
            setSession(null);
            setProfileOpen(false);
          }}
        />
      )}

      <section className={`workspace${activeSection === "chat" ? "" : " workspace-two-col"}`}>
        <AppRail activeSection={activeSection} onSelect={setActiveSection} />
        <section
          className={`conversation${
            activeSection === "calendar"
              ? " conversation-calendar"
              : activeSection === "work-board"
                ? " conversation-board"
                : activeSection === "docs"
                  ? " conversation-docs"
                  : ""
          }`}
        >
          {renderMainContent()}
        </section>

        {activeSection === "chat" && (
          <EvidenceDrawer answer={answer} events={runEvents} activeTab={drawerTab} onTabChange={setDrawerTab} />
        )}
      </section>
    </main>
  );
}
