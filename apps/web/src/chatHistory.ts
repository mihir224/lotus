import { authHeaders } from "./auth";
import type { ChatSession, ChatSessionDetail } from "./types";

async function expectJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`Conversation request failed (${response.status}).`);
  return response.json() as Promise<T>;
}

export async function createChatSession(projectId = "payments"): Promise<ChatSession> {
  return expectJson<ChatSession>(await fetch("/v1/chat/sessions", {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ project_id: projectId })
  }));
}

export async function listChatSessions(): Promise<ChatSession[]> {
  const page = await expectJson<{ items: ChatSession[] }>(
    await fetch("/v1/chat/sessions?limit=50", { headers: authHeaders() })
  );
  return page.items;
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return expectJson<ChatSessionDetail>(
    await fetch(`/v1/chat/sessions/${encodeURIComponent(sessionId)}`, { headers: authHeaders() })
  );
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  const response = await fetch(`/v1/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: authHeaders()
  });
  if (!response.ok) throw new Error(`Unable to delete conversation (${response.status}).`);
}
