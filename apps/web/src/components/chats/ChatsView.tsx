import { FormEvent, useMemo, useState } from "react";
import mockData from "../../data/mock-chats.json";
import type { LocalChatMessage, MockChatsData, MockConversation } from "./chatsTypes";

const data = mockData as MockChatsData;

const FILTER_CHIPS = ["Unread", "Chats", "Unmuted", "Meeting chats"] as const;

function formatNowTime(): string {
  return new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function activityTimestamp(conv: MockConversation): number {
  const parsed = Date.parse(conv.last_activity_at);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function ChatsView() {
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    const sorted = [...data.conversations].sort(
      (a, b) => activityTimestamp(b) - activityTimestamp(a)
    );
    return sorted[0]?.id ?? null;
  });
  const [draft, setDraft] = useState("");
  const [localMessages, setLocalMessages] = useState<Record<string, LocalChatMessage[]>>({});
  const [activeFilter, setActiveFilter] = useState<string>("Chats");
  const [sidebarQuery, setSidebarQuery] = useState("");

  const selected = useMemo(
    () => data.conversations.find((conv) => conv.id === selectedId) ?? null,
    [selectedId]
  );

  const filteredConversations = useMemo(() => {
    const needle = sidebarQuery.trim().toLowerCase();
    return data.conversations.filter((conv) => {
      if (needle && !conv.name.toLowerCase().includes(needle) && !conv.preview.toLowerCase().includes(needle)) {
        return false;
      }
      return true;
    });
  }, [sidebarQuery]);

  const messages = useMemo(() => {
    if (!selected) return [];
    return [...selected.messages, ...(localMessages[selected.id] ?? [])];
  }, [selected, localMessages]);

  function handleSend(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !selected) return;
    const entry: LocalChatMessage = {
      id: `local-${crypto.randomUUID()}`,
      sender_name: "You",
      sender_initials: "DE",
      is_self: true,
      time_label: formatNowTime(),
      body: text,
      local: true
    };
    setLocalMessages((current) => ({
      ...current,
      [selected.id]: [...(current[selected.id] ?? []), entry]
    }));
    setDraft("");
  }

  return (
    <div className="teams-chats">
      <aside className="teams-chats-sidebar">
        <header className="teams-chats-sidebar-head">
          <h1>Chat</h1>
          <div className="teams-chats-sidebar-tools">
            <button type="button" className="teams-chats-icon-btn" aria-label="Filter" title="Filter">
              …
            </button>
            <button type="button" className="teams-chats-icon-btn" aria-label="New chat" title="New chat">
              +
            </button>
          </div>
        </header>

        <div className="teams-chats-filters">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              className={`teams-chats-filter${activeFilter === chip ? " active" : ""}`}
              onClick={() => setActiveFilter(chip)}
            >
              {chip}
            </button>
          ))}
        </div>

        <label className="teams-chats-sidebar-search">
          <span className="visually-hidden">Search conversations</span>
          <input
            type="search"
            value={sidebarQuery}
            onChange={(event) => setSidebarQuery(event.target.value)}
            placeholder="Search"
          />
        </label>

        <div className="teams-chats-sidebar-scroll">
          {data.sections.map((section) => {
            const items = filteredConversations
              .filter((conv) => conv.section === section.id)
              .sort((a, b) => activityTimestamp(b) - activityTimestamp(a));
            if (items.length === 0) return null;
            return (
              <section key={section.id} className="teams-chats-section">
                <h2>{section.label}</h2>
                <ul className="teams-chats-list">
                  {items.map((conv) => (
                    <ChatListItem
                      key={conv.id}
                      conversation={conv}
                      active={conv.id === selectedId}
                      onSelect={() => setSelectedId(conv.id)}
                    />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      </aside>

      <section className="teams-chats-main" aria-label="Conversation">
        {selected ? (
          <>
            <header className="teams-chats-main-head">
              <div className="teams-chats-main-title">
                <span
                  className="teams-chats-avatar teams-chats-avatar-lg"
                  style={{ background: selected.avatar_color }}
                >
                  {selected.initials}
                </span>
                <div>
                  <h2>{selected.name}</h2>
                  <p>{selected.kind === "group" ? "Group chat" : "Direct message"}</p>
                </div>
              </div>
              <div className="teams-chats-main-tabs" role="tablist">
                <button type="button" role="tab" aria-selected className="active">
                  Chat
                </button>
                <button type="button" role="tab" aria-selected={false}>
                  Shared
                </button>
                <button type="button" role="tab" aria-selected={false}>
                  Notes
                </button>
              </div>
            </header>

            <div className="teams-chats-messages">
              {messages.map((msg) => (
                <article
                  key={msg.id}
                  className={`teams-chats-message${msg.is_self ? " self" : ""}`}
                >
                  {!msg.is_self && (
                    <span
                      className="teams-chats-avatar teams-chats-avatar-sm"
                      style={{
                        background: msg.is_self ? "#3d6b5a" : selected.avatar_color
                      }}
                      aria-hidden="true"
                    >
                      {msg.sender_initials}
                    </span>
                  )}
                  <div className="teams-chats-bubble-wrap">
                    {!msg.is_self && <p className="teams-chats-sender">{msg.sender_name}</p>}
                    <div className="teams-chats-bubble">
                      <p>{msg.body}</p>
                    </div>
                    <time className="teams-chats-time">{msg.time_label}</time>
                  </div>
                </article>
              ))}
            </div>

            <form className="teams-chats-composer" onSubmit={handleSend}>
              <input
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Type a message"
                aria-label="Type a message"
              />
              <div className="teams-chats-composer-actions">
                <button type="button" className="teams-chats-icon-btn" aria-label="Attach">
                  +
                </button>
                <button
                  type="submit"
                  className="teams-chats-send"
                  aria-label="Send"
                  disabled={!draft.trim()}
                >
                  →
                </button>
              </div>
            </form>
          </>
        ) : (
          <div className="teams-chats-empty">
            <p>Select a conversation to start messaging.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function ChatListItem({
  conversation,
  active,
  onSelect
}: {
  conversation: MockConversation;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        className={`teams-chats-list-item${active ? " active" : ""}`}
        onClick={onSelect}
      >
        <span
          className="teams-chats-avatar"
          style={{ background: conversation.avatar_color }}
          aria-hidden="true"
        >
          {conversation.initials}
        </span>
        <span className="teams-chats-list-body">
          <span className="teams-chats-list-top">
            <span className="teams-chats-list-name">{conversation.name}</span>
            <span className="teams-chats-list-time">{conversation.time_label}</span>
          </span>
          <span className="teams-chats-list-preview">{conversation.preview}</span>
        </span>
      </button>
    </li>
  );
}
