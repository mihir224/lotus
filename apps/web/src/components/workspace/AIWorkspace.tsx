import { useState } from "react";
import { ChatComposer } from "../../ChatComposer";
import { MarkdownMessage } from "../../MarkdownMessage";
import { MermaidDiagram } from "../../MermaidDiagram";
import { hideEvidenceReferences } from "../../chatPresentation";
import type { ChatMessage, GroundedAnswer, NavigationTarget } from "../../types";

const suggestions = [
  "Why are checkout retries capped, and what should on-call do?",
  "Who are the stakeholders for the payments project?",
  "Draw the checkout resilience architecture flow"
];

function ThumbIcon({ down = false }: { down?: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="response-action-icon" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><g transform={down ? "rotate(180 12 12)" : undefined}><path d="M7 10v12" /><path d="M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 8a2 2 0 0 1-1.9 1.4H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9Z" /></g></svg>;
}

function HistoryIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="chat-header-icon" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></svg>;
}

function PlusIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="chat-header-icon" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>;
}

function ResponseBlock({ response, content, theme, debugEnabled, onNavigate }: { response: GroundedAnswer | null; content: string; theme: "dark" | "light"; debugEnabled: boolean; onNavigate: (target: NavigationTarget) => void }) {
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null);
  const [copied, setCopied] = useState(false);
  const visibleContent = debugEnabled ? content : hideEvidenceReferences(content);
  return <div className="assistant-response">
    <MarkdownMessage>{visibleContent}</MarkdownMessage>
    {response?.artifacts.map((artifact, index) => artifact.artifact_type === "mermaid" && typeof artifact.content === "string" ? <MermaidDiagram key={`${artifact.title}-${index}`} title={artifact.title} source={artifact.content} theme={theme} /> : null)}
    {(response?.navigation_targets.length ?? 0) > 0 && <div className="navigation-actions">{response!.navigation_targets.map((target) => <button type="button" key={`${target.kind}-${target.entity_id}`} onClick={() => onNavigate(target)}>{target.label} <span aria-hidden="true">→</span></button>)}</div>}
    {response && <div className="response-actions" aria-label="Response actions">
      <button type="button" className={feedback === "like" ? "active" : ""} aria-label="Like response" onClick={() => setFeedback(feedback === "like" ? null : "like")}><ThumbIcon /></button>
      <button type="button" className={feedback === "dislike" ? "active" : ""} aria-label="Dislike response" onClick={() => setFeedback(feedback === "dislike" ? null : "dislike")}><ThumbIcon down /></button>
      <button type="button" aria-label="Copy response" onClick={async () => { await navigator.clipboard.writeText(visibleContent); setCopied(true); window.setTimeout(() => setCopied(false), 1600); }}><span aria-hidden="true">{copied ? "✓" : "⧉"}</span><span>{copied ? "Copied" : "Copy"}</span></button>
    </div>}
  </div>;
}

type Props = {
  message: string;
  messages: ChatMessage[];
  streamedAnswer: string;
  loading: boolean;
  error: string | null;
  theme: "dark" | "light";
  debugEnabled: boolean;
  onMessageChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onOpenHistory: () => void;
  onNewConversation: () => void;
  onNavigate: (target: NavigationTarget) => void;
};

export function AIWorkspace(props: Props) {
  const empty = props.messages.length === 0 && !props.streamedAnswer;
  return <div className="chat-workspace">
    <header className="chat-header"><div><p className="eyebrow">Lotus AI workspace</p><h1>Iris</h1></div><div className="chat-header-actions"><button type="button" className="history-trigger" onClick={props.onNewConversation} aria-label="Start new chat" title="New chat"><PlusIcon /></button><button type="button" className="history-trigger" onClick={props.onOpenHistory} aria-label="Open chat history" title="Chat history"><HistoryIcon /></button></div></header>
    <div className="chat-scroll" aria-live="polite">
      {empty && <><div className="intro"><h2>What do you need to understand?</h2><p>Ask across projects, documents, meetings, repositories, and public research.</p></div><div className="suggestions">{suggestions.map((item) => <button type="button" onClick={() => props.onMessageChange(item)} key={item}>{item}</button>)}</div></>}
      <div className="message-thread">
        {props.messages.map((item) => item.role === "user" ? <div className="user-message" key={item.message_id}>{item.content}</div> : <ResponseBlock key={item.message_id} response={item.response} content={item.content} theme={props.theme} debugEnabled={props.debugEnabled} onNavigate={props.onNavigate} />)}
        {props.streamedAnswer && <ResponseBlock response={null} content={props.streamedAnswer} theme={props.theme} debugEnabled={props.debugEnabled} onNavigate={props.onNavigate} />}
        {props.loading && !props.streamedAnswer && <div className="progress-line" role="status"><strong>Thinking</strong><span className="typing-dots" aria-hidden="true"><i /><i /><i /></span></div>}
      </div>
      {props.error && <div className="error">{props.error}</div>}
    </div>
    <ChatComposer value={props.message} loading={props.loading} onChange={props.onMessageChange} onSubmit={props.onSubmit} onCancel={props.onCancel} />
  </div>;
}
