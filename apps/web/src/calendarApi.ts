import type { CalendarEvent, MeetingRecord } from "./types";
import { authHeaders } from "./auth";

export const DEMO_RECORDING_SRC =
  "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4";

export function resolveRecordingUrl(recordingUrl: string | null | undefined) {
  if (!recordingUrl || recordingUrl.startsWith("fixture://")) return DEMO_RECORDING_SRC;
  return recordingUrl;
}

export async function fetchCalendarEvents(dateFrom: string, dateTo: string) {
  const params = new URLSearchParams({
    project_id: "payments",
    date_from: dateFrom,
    date_to: dateTo
  });
  const response = await fetch(`/v1/calendar/events?${params}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Calendar request failed with ${response.status}`);
  return (await response.json()) as CalendarEvent[];
}

export async function fetchMeetingRecord(meetingId: string) {
  const response = await fetch(`/v1/meetings/${meetingId}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Meeting request failed with ${response.status}`);
  return (await response.json()) as MeetingRecord;
}

export async function summarizeMeeting(meetingId: string) {
  const response = await fetch(`/v1/meetings/${meetingId}/summarize`, {
    method: "POST",
    headers: authHeaders()
  });
  if (!response.ok) throw new Error(`Meeting summary failed with ${response.status}`);
  return (await response.json()) as MeetingRecord;
}
