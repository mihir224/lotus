import type { CalendarEvent, MeetingRecord } from "../../types";
import { authenticatedFetch, authHeaders } from "../../auth";

/** Bundled clip for all fixture meeting recordings (apps/web/public). */
export const DEMO_RECORDING_SRC = "/team_discussion.mp4";

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
  const response = await authenticatedFetch(`/v1/calendar/events?${params}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Calendar request failed with ${response.status}`);
  return (await response.json()) as CalendarEvent[];
}

export async function fetchMeetingRecord(meetingId: string) {
  const response = await authenticatedFetch(`/v1/meetings/${meetingId}`, { headers: authHeaders() });
  if (!response.ok) throw new Error(`Meeting request failed with ${response.status}`);
  return (await response.json()) as MeetingRecord;
}

export type CreateCalendarEventPayload = {
  title: string;
  project_id?: string;
  location?: string | null;
  description?: string;
  started_at: string;
  ended_at: string;
  attendees?: string[];
  video_meeting?: boolean;
};

export async function createCalendarEvent(payload: CreateCalendarEventPayload) {
  const response = await authenticatedFetch("/v1/calendar/events", {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Create event failed with ${response.status}`);
  }
  return (await response.json()) as CalendarEvent;
}

export async function summarizeMeeting(meetingId: string) {
  const response = await authenticatedFetch(`/v1/meetings/${meetingId}/summarize`, {
    method: "POST",
    headers: authHeaders()
  });
  if (!response.ok) throw new Error(`Meeting summary failed with ${response.status}`);
  return (await response.json()) as MeetingRecord;
}
