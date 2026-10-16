export function agentLocation(sessionId?: string | null): string {
  const params = new URLSearchParams({ section: "agent" });
  if (sessionId) params.set("session", sessionId);
  return `?${params.toString()}`;
}
