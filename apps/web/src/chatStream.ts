import type { RunEvent } from "./types";

export function parseSseFrames(buffer: string): { events: RunEvent[]; remainder: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const frames = normalized.split("\n\n");
  const remainder = frames.pop() ?? "";
  const events: RunEvent[] = [];
  for (const frame of frames) {
    const data = frame
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data || data === "{}") continue;
    try {
      events.push(JSON.parse(data) as RunEvent);
    } catch {
      throw new Error("Lotus returned a malformed streaming event.");
    }
  }
  return { events, remainder };
}

export async function streamChat(
  payload: Record<string, unknown>,
  headers: HeadersInit,
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch("/v1/chat/stream", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session expired. Sign in again.");
    if (response.status === 429) throw new Error("Request limit reached. Please try again shortly.");
    throw new Error(`Lotus request failed (${response.status}).`);
  }
  if (!response.body) throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSseFrames(buffer);
    buffer = parsed.remainder;
    parsed.events.forEach(onEvent);
    if (done) break;
  }
  if (buffer.trim()) {
    const parsed = parseSseFrames(`${buffer}\n\n`);
    parsed.events.forEach(onEvent);
  }
}
