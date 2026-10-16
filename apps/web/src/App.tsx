import { useEffect, useRef, useState } from "react";
import { authHeaders, type AuthConfig, type AuthSession, GoogleLogin, signOut, storedAuthSession } from "./auth";
import { createChatSession, deleteChatSession, getChatSession, listChatSessions } from "./chatHistory";
import { streamChat } from "./chatStream";
import { CalendarView } from "./components/calendar/CalendarView";
import { DocsView } from "./components/docs/DocsView";
import { AppRail } from "./components/navigation/AppRail";
import type { AppSection } from "./components/navigation/types";
import { ProfileAvatar } from "./components/profile/ProfileAvatar";
import { ProfilePanel } from "./components/profile/ProfilePanel";
import { useUserProfile } from "./components/profile/useUserProfile";
import { ChatsView } from "./components/chats/ChatsView";
import { WorkBoardView } from "./components/work-board/WorkBoardView";
import { AIWorkspace } from "./components/workspace/AIWorkspace";
import { ChatHistoryDialog } from "./components/workspace/ChatHistoryDialog";
import { DebugDialog } from "./components/workspace/DebugDialog";
import { EvidenceDrawer } from "./components/workspace/EvidenceDrawer";
import type { ChatMessage, ChatSession, GroundedAnswer, NavigationTarget, RunEvent } from "./types";

type Theme = "dark" | "light";

const APP_SECTIONS: AppSection[] = ["agent", "chats", "calendar", "docs", "work-board"];

function parseSectionParam(raw: string | null): AppSection {
  if (raw === "chat") return "agent";
  if (raw && APP_SECTIONS.includes(raw as AppSection)) return raw as AppSection;
  return "agent";
}

function initialLocation() {
  const params = new URLSearchParams(window.location.search);
  return {
    section: parseSectionParam(params.get("section")),
    meetingId: params.get("meeting"),
    documentId: params.get("document"),
    projectId: params.get("project"),
    issueKey: params.get("issue")
  };
}

export function App() {
  const location = initialLocation();
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [session, setSession] = useState<AuthSession | null>(storedAuthSession);
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<AppSection>(location.section);
  const [meetingTarget, setMeetingTarget] = useState(location.meetingId);
  const [documentTarget, setDocumentTarget] = useState(location.documentId);
  const [projectTarget, setProjectTarget] = useState(location.projectId);
  const [issueTarget, setIssueTarget] = useState(location.issueKey);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const runEventsRef = useRef<RunEvent[]>([]);
  const [drawerTab, setDrawerTab] = useState<"evidence" | "run">("evidence");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const [chatSessionId, setChatSessionId] = useState<string | null>(() => localStorage.getItem("lotus.chat_session_id"));
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [debugDialogOpen, setDebugDialogOpen] = useState(false);
  const [debugEnabled, setDebugEnabled] = useState(() => localStorage.getItem("lotus.debug") === "true");
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("lotus.theme") === "light" ? "light" : "dark");
  const [profileOpen, setProfileOpen] = useState(false);
  const { profile } = useUserProfile(session, authConfig?.mode ?? "dev");

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("lotus.theme", theme); }, [theme]);
  useEffect(() => { localStorage.setItem("lotus.debug", String(debugEnabled)); if (!debugEnabled) { setRunEvents([]); runEventsRef.current = []; sessionStorage.removeItem("lotus.latest_run"); } }, [debugEnabled]);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey && event.altKey && event.key.toLowerCase() === "o") || (event.ctrlKey && event.altKey && event.key.toLowerCase() === "o")) { event.preventDefault(); setDebugDialogOpen(true); }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  useEffect(() => {
    fetch("/v1/auth/config").then(async (response) => { if (!response.ok) throw new Error(`Authentication config failed with ${response.status}`); setAuthConfig((await response.json()) as AuthConfig); }).catch((reason) => setAuthConfigError(reason instanceof Error ? reason.message : "Unable to load authentication"));
  }, []);
  useEffect(() => {
    if (!authConfig || (authConfig.mode === "google" && !session) || !chatSessionId) return;
    void getChatSession(chatSessionId).then((detail) => setMessages(detail.messages)).catch(() => { localStorage.removeItem("lotus.chat_session_id"); setChatSessionId(null); });
  }, [authConfig, session, chatSessionId]);

  async function ensureSession() {
    if (chatSessionId) return chatSessionId;
    const created = await createChatSession("payments");
    setChatSessionId(created.session_id);
    localStorage.setItem("lotus.chat_session_id", created.session_id);
    return created.session_id;
  }

  async function submit() {
    if (!message.trim() || loading) return;
    const prompt = message.trim();
    setMessage(""); setLoading(true); setError(null); setAnswer(null); setStreamedAnswer(""); setDrawerTab("run");
    if (debugEnabled) { setRunEvents([]); runEventsRef.current = []; }
    const localUserId = `local-${crypto.randomUUID()}`;
    setMessages((current) => [...current, { message_id: localUserId, session_id: chatSessionId ?? "pending", role: "user", content: prompt, execution_id: null, status: "running", response: null, created_at: new Date().toISOString() }]);
    const controller = new AbortController(); controllerRef.current = controller;
    try {
      const activeSessionId = await ensureSession();
      await streamChat({ message: prompt, project_id: "payments", session_id: activeSessionId }, authHeaders(true), (event) => {
        if (debugEnabled) setRunEvents((previous) => { const next = [...previous, event].slice(-500); runEventsRef.current = next; sessionStorage.setItem("lotus.latest_run", JSON.stringify(next)); return next; });
        if (event.event_type === "answer.delta" && event.answer_delta) setStreamedAnswer((previous) => previous + event.answer_delta);
        if (event.event_type === "answer.completed" && event.response) {
          const response = event.response;
          setAnswer(response); setStreamedAnswer(""); setDrawerTab("evidence");
          setMessages((current) => [...current.map((item) => item.message_id === localUserId ? { ...item, status: "completed" as const, session_id: activeSessionId } : item), { message_id: `assistant-${response.execution_id}`, session_id: activeSessionId, role: "assistant", content: response.answer, execution_id: response.execution_id, status: "completed", response, created_at: new Date().toISOString() }]);
        }
        if (event.event_type === "run.failed") throw new Error("The Lotus run failed.");
      }, controller.signal);
    } catch (reason) {
      setMessages((current) => current.map((item) => item.message_id === localUserId ? { ...item, status: "failed" as const } : item));
      setError(reason instanceof DOMException && reason.name === "AbortError" ? "Run cancelled." : reason instanceof Error ? reason.message : "Unable to reach Lotus API");
    } finally { setLoading(false); controllerRef.current = null; }
  }

  async function openHistory() { setHistoryOpen(true); setHistoryLoading(true); try { setSessions(await listChatSessions()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load history"); } finally { setHistoryLoading(false); } }
  async function newConversation() { const created = await createChatSession("payments"); setChatSessionId(created.session_id); localStorage.setItem("lotus.chat_session_id", created.session_id); setMessages([]); setAnswer(null); setHistoryOpen(false); }
  async function openConversation(id: string) { const detail = await getChatSession(id); setChatSessionId(id); localStorage.setItem("lotus.chat_session_id", id); setMessages(detail.messages); setAnswer([...detail.messages].reverse().find((item) => item.response)?.response ?? null); setHistoryOpen(false); setActiveSection("agent"); }
  async function removeConversation(id: string) { if (!window.confirm("Delete this conversation?")) return; await deleteChatSession(id); setSessions((current) => current.filter((item) => item.session_id !== id)); if (id === chatSessionId) { localStorage.removeItem("lotus.chat_session_id"); setChatSessionId(null); setMessages([]); setAnswer(null); } }

  function navigate(target: NavigationTarget) {
    const params = new URLSearchParams();
    if (target.kind === "meeting") { setActiveSection("calendar"); setMeetingTarget(target.entity_id); params.set("section", "calendar"); params.set("meeting", target.entity_id); }
    else if (target.kind === "document") { setActiveSection("docs"); setDocumentTarget(target.entity_id); params.set("section", "docs"); params.set("document", target.entity_id); }
    else { setActiveSection("work-board"); setProjectTarget(target.project_id ?? target.entity_id); setIssueTarget(target.kind === "planning_item" ? target.entity_id : null); params.set("section", "work-board"); params.set("project", target.project_id ?? target.entity_id); if (target.kind === "planning_item") params.set("issue", target.entity_id); }
    window.history.pushState({}, "", `?${params}`);
  }

  if (authConfigError) return <main className="login-shell"><div className="error">{authConfigError}</div></main>;
  if (!authConfig) return <main className="login-shell"><p>Loading Lotus…</p></main>;
  if (authConfig.mode === "google" && !session) return authConfig.google_client_id ? <GoogleLogin clientId={authConfig.google_client_id} onAuthenticated={setSession} /> : <main className="login-shell"><div className="error">Google OAuth is not configured.</div></main>;

  const mainContent = activeSection === "work-board" ? <WorkBoardView initialProjectId={projectTarget} initialIssueKey={issueTarget} /> : activeSection === "docs" ? <DocsView initialDocumentId={documentTarget} /> : activeSection === "calendar" ? <CalendarView today={new Date()} initialMeetingId={meetingTarget} /> : activeSection === "chats" ? <ChatsView /> : <AIWorkspace message={message} messages={messages} streamedAnswer={streamedAnswer} loading={loading} error={error} theme={theme} onMessageChange={setMessage} onSubmit={submit} onCancel={() => controllerRef.current?.abort()} onOpenHistory={() => void openHistory()} onNavigate={navigate} />;

  return <main className="shell">
    <header className="topbar"><div className="brand"><div className="lotus-mark" aria-hidden="true">✦</div><div><strong>Lotus</strong><span>Enterprise workspace</span></div></div>{profile && <button type="button" className="profile-topbar-btn" aria-label="Open profile" onClick={() => setProfileOpen(true)}><ProfileAvatar profile={profile} size={40} /></button>}</header>
    {profile && <ProfilePanel open={profileOpen} profile={profile} theme={theme} onThemeChange={setTheme} onClose={() => setProfileOpen(false)} showSignOut={authConfig.mode === "google" && Boolean(session)} onSignOut={() => { signOut(); setSession(null); setProfileOpen(false); }} />}
    <section className={`workspace${activeSection === "agent" && debugEnabled ? "" : " workspace-two-col"}`}><AppRail activeSection={activeSection} onSelect={(section) => { setActiveSection(section); window.history.pushState({}, "", `?section=${section}`); }} /><section className={`conversation conversation-${activeSection}${activeSection === "chats" ? " conversation-chats" : ""}`}>{mainContent}</section>{activeSection === "agent" && debugEnabled && <EvidenceDrawer answer={answer} events={runEvents} activeTab={drawerTab} onTabChange={setDrawerTab} />}</section>
    <ChatHistoryDialog open={historyOpen} sessions={sessions} currentSessionId={chatSessionId} loading={historyLoading} onClose={() => setHistoryOpen(false)} onNew={() => void newConversation()} onOpen={(id) => void openConversation(id)} onDelete={(id) => void removeConversation(id)} />
    <DebugDialog open={debugDialogOpen} enabled={debugEnabled} onChange={setDebugEnabled} onClose={() => setDebugDialogOpen(false)} />
  </main>;
}
