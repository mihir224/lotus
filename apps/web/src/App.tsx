import { FormEvent, useEffect, useState } from "react";
import { CalendarView } from "./components/calendar/CalendarView";
import { AppRail } from "./components/navigation/AppRail";
import type { AppSection } from "./components/navigation/types";
import { AIWorkspace } from "./components/workspace/AIWorkspace";
import { EvidenceDrawer } from "./components/workspace/EvidenceDrawer";
import { DocsView } from "./components/docs/DocsView";
import { WorkBoardView } from "./components/work-board/WorkBoardView";
import {
  authHeaders,
  type AuthConfig,
  type AuthSession,
  GoogleLogin,
  signOut,
  storedAuthSession
} from "./auth";
import { ProfileAvatar } from "./components/profile/ProfileAvatar";
import { ProfilePanel } from "./components/profile/ProfilePanel";
import { useUserProfile } from "./components/profile/useUserProfile";
import type { GroundedAnswer } from "./types";

const suggestions = [
  "Why are checkout retries capped, and what should on-call do?",
  "What is the current status of PAY-123?",
  "What is the lunar office dress code?"
];

export function App() {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [session, setSession] = useState<AuthSession | null>(storedAuthSession);
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<AppSection>("chat");
  const [message, setMessage] = useState(suggestions[0]);
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/v1/chat/messages", {
        method: "POST",
        headers: authHeaders(true),
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
            answer={answer}
            loading={loading}
            error={error}
            onSubmit={submit}
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
          <div>
            <strong>Lotus</strong>
            <span>Enterprise workspace</span>
          </div>
        </div>
        {profile && (
          <button
            type="button"
            className="profile-topbar-btn"
            aria-label="Open profile"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen(true)}
          >
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

        {activeSection === "chat" && <EvidenceDrawer answer={answer} />}
      </section>
    </main>
  );
}
