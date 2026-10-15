import { FormEvent, useEffect, useState } from "react";
export type NewMeetingDraft = {
  title: string;
  date: string;
  startTime: string;
  endTime: string;
  location: string;
  description: string;
  attendees: string;
  videoMeeting: boolean;
};

type NewMeetingModalProps = {
  open: boolean;
  anchorDate: Date;
  onClose: () => void;
  onSave: (draft: NewMeetingDraft) => Promise<void>;
  saving: boolean;
  error: string | null;
};

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function defaultDraft(anchorDate: Date): NewMeetingDraft {
  const date = `${anchorDate.getFullYear()}-${pad(anchorDate.getMonth() + 1)}-${pad(anchorDate.getDate())}`;
  return {
    title: "",
    date,
    startTime: "10:00",
    endTime: "10:30",
    location: "",
    description: "",
    attendees: "",
    videoMeeting: true
  };
}

function previewRange(draft: NewMeetingDraft) {
  const start = new Date(`${draft.date}T${draft.startTime}`);
  const end = new Date(`${draft.date}T${draft.endTime}`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "Select a valid time";
  const day = start.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  const time = (value: Date) => value.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day} · ${time(start)} – ${time(end)}`;
}

function schedulerStyle(draft: NewMeetingDraft) {
  const [startHour, startMinute] = draft.startTime.split(":").map(Number);
  const [endHour, endMinute] = draft.endTime.split(":").map(Number);
  const startMinutes = startHour * 60 + startMinute;
  const endMinutes = endHour * 60 + endMinute;
  const top = (startMinutes / 60) * 44;
  const height = Math.max(((endMinutes - startMinutes) / 60) * 44, 28);
  return { top: `${top}px`, height: `${height}px` };
}

export function NewMeetingModal({ open, anchorDate, onClose, onSave, saving, error }: NewMeetingModalProps) {
  const [draft, setDraft] = useState(() => defaultDraft(anchorDate));

  useEffect(() => {
    if (open) setDraft(defaultDraft(anchorDate));
  }, [open, anchorDate]);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft.title.trim() || saving) return;
    try {
      await onSave(draft);
    } catch {
      // Parent surfaces createMeetingError.
    }
  }

  const hours = Array.from({ length: 13 }, (_, index) => index + 8);

  return (
    <div className="calendar-overlay" role="presentation" onClick={onClose}>
      <form
        className="calendar-new-event"
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <header className="calendar-new-event-head">
          <div>
            <p className="eyebrow">New event</p>
            <h2>Schedule a meeting</h2>
          </div>
          <div className="calendar-new-event-actions">
            <button type="button" className="calendar-btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="calendar-btn calendar-btn-primary" disabled={saving || !draft.title.trim()}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </header>

        <div className="calendar-new-event-body">
          <div className="calendar-new-event-form">
            <label className="calendar-field">
              <span>Title</span>
              <input
                value={draft.title}
                onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
                placeholder="Add a title"
                required
              />
            </label>
            <label className="calendar-field">
              <span>Attendees</span>
              <input
                value={draft.attendees}
                onChange={(event) => setDraft((prev) => ({ ...prev, attendees: event.target.value }))}
                placeholder="Invite required attendees"
              />
            </label>
            <div className="calendar-field-row">
              <label className="calendar-field">
                <span>Date</span>
                <input
                  type="date"
                  value={draft.date}
                  onChange={(event) => setDraft((prev) => ({ ...prev, date: event.target.value }))}
                  required
                />
              </label>
              <label className="calendar-field">
                <span>Start</span>
                <input
                  type="time"
                  value={draft.startTime}
                  onChange={(event) => setDraft((prev) => ({ ...prev, startTime: event.target.value }))}
                  required
                />
              </label>
              <label className="calendar-field">
                <span>End</span>
                <input
                  type="time"
                  value={draft.endTime}
                  onChange={(event) => setDraft((prev) => ({ ...prev, endTime: event.target.value }))}
                  required
                />
              </label>
            </div>
            <p className="calendar-new-event-range">{previewRange(draft)}</p>
            <label className="calendar-field">
              <span>Location</span>
              <input
                value={draft.location}
                onChange={(event) => setDraft((prev) => ({ ...prev, location: event.target.value }))}
                placeholder="Add a room or location"
              />
            </label>
            <label className="calendar-toggle">
              <input
                type="checkbox"
                checked={draft.videoMeeting}
                onChange={(event) => setDraft((prev) => ({ ...prev, videoMeeting: event.target.checked }))}
              />
              <span>Lotus video meeting</span>
            </label>
            <label className="calendar-field">
              <span>Description</span>
              <textarea
                rows={4}
                value={draft.description}
                onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
                placeholder="Add meeting details"
              />
            </label>
          </div>

          <aside className="calendar-new-event-scheduler" aria-label="Scheduler preview">
            <header>
              <strong>{previewRange(draft)}</strong>
            </header>
            <div className="calendar-new-event-scheduler-grid">
              <div className="calendar-new-event-hours">
                {hours.map((hour) => (
                  <div key={hour} style={{ height: 44 }}>
                    {new Date(2000, 0, 1, hour).toLocaleTimeString(undefined, { hour: "numeric" })}
                  </div>
                ))}
              </div>
              <div className="calendar-new-event-slot-col">
                {hours.map((hour) => (
                  <div key={hour} className="calendar-new-event-hour-line" style={{ height: 44 }} />
                ))}
                <div className="calendar-new-event-slot" style={schedulerStyle(draft)}>
                  {draft.title.trim() || "New meeting"}
                </div>
              </div>
            </div>
          </aside>
        </div>

        {error && <div className="error calendar-new-event-error">{error}</div>}
      </form>
    </div>
  );
}
