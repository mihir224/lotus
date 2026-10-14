import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchCalendarEvents,
  fetchMeetingRecord,
  resolveRecordingUrl,
  summarizeMeeting
} from "./calendarApi";
import type { CalendarEvent, MeetingAnalysis, MeetingRecord } from "./types";

const GRID_START_HOUR = 0;
const GRID_END_HOUR = 23;
const HOUR_HEIGHT = 48;
const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function startOfWorkWeek(date: Date) {
  const copy = new Date(date);
  const weekday = copy.getDay();
  const offset = weekday === 0 ? -6 : 1 - weekday;
  copy.setDate(copy.getDate() + offset);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(date: Date, days: number) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function formatDayHeader(date: Date) {
  return date.toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
}

function formatRange(weekStart: Date) {
  const weekEnd = addDays(weekStart, 4);
  const sameMonth = weekStart.getMonth() === weekEnd.getMonth();
  const startPart = weekStart.toLocaleDateString(undefined, {
    day: "numeric",
    month: sameMonth ? undefined : "long"
  });
  const endPart = weekEnd.toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric"
  });
  return `${startPart}–${endPart}`;
}

function isoDayStart(date: Date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMinutes);
  const oh = String(Math.floor(abs / 60)).padStart(2, "0");
  const om = String(abs % 60).padStart(2, "0");
  return `${y}-${m}-${d}T00:00:00${sign}${oh}:${om}`;
}

function sameCalendarDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function formatEventTime(event: CalendarEvent) {
  const start = new Date(event.started_at);
  const end = new Date(event.ended_at);
  const dayPart = start.toLocaleDateString(undefined, {
    weekday: "short",
    month: "numeric",
    day: "numeric",
    year: "2-digit"
  });
  const timePart = (value: Date) =>
    value.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${dayPart} ${timePart(start)} – ${timePart(end)}`;
}

function eventStyle(event: CalendarEvent) {
  const start = new Date(event.started_at);
  const end = new Date(event.ended_at);
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  const top = ((startMinutes - GRID_START_HOUR * 60) / 60) * HOUR_HEIGHT;
  const height = ((endMinutes - startMinutes) / 60) * HOUR_HEIGHT;
  return { top: `${top}px`, height: `${Math.max(height, 28)}px` };
}

function startOfMonth(date: Date) {
  const copy = new Date(date.getFullYear(), date.getMonth(), 1);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addMonths(date: Date, months: number) {
  const copy = new Date(date);
  copy.setDate(1);
  copy.setMonth(copy.getMonth() + months);
  return copy;
}

function startOfCalendarWeek(date: Date) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() - copy.getDay());
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function buildMonthWeeks(viewMonth: Date) {
  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const weeks: Date[][] = [];
  let cursor = startOfCalendarWeek(new Date(year, month, 1));
  const monthEnd = new Date(year, month + 1, 0);
  while (weeks.length < 6) {
    weeks.push(Array.from({ length: 7 }, (_, index) => addDays(cursor, index)));
    cursor = addDays(cursor, 7);
    if (weeks.length >= 4 && cursor > monthEnd && weeks[weeks.length - 1][6].getMonth() !== month) {
      break;
    }
  }
  return weeks;
}

function isSameDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function isSameCalendarWeek(left: Date, right: Date) {
  return startOfCalendarWeek(left).getTime() === startOfCalendarWeek(right).getTime();
}

type CalendarViewProps = {
  today: Date;
};

function formatTranscriptTime(milliseconds: number) {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function MeetingSummary({ record }: { record: MeetingRecord }) {
  const analysis = record.analysis;
  if (!analysis) return <p className="calendar-summary-lead">No summary is available.</p>;
  return (
    <>
      <p className="calendar-summary-lead">{analysis.summary}</p>
      {analysis.decisions.length > 0 && (
        <section>
          <h3>Decisions</h3>
          <ul>{analysis.decisions.map((item) => <li key={item.text}>{item.text}</li>)}</ul>
        </section>
      )}
      {analysis.action_items.length > 0 && (
        <section>
          <h3>Action items</h3>
          <ul>
            {analysis.action_items.map((item) => (
              <li key={item.text}>
                {item.text}
                {item.owner && <small> — {item.owner}</small>}
                {item.due_date && <small> (due {item.due_date})</small>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {analysis.open_questions.length > 0 && (
        <section>
          <h3>Open questions</h3>
          <ul>{analysis.open_questions.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}
      <details className="calendar-transcript">
        <summary>View transcript · {record.transcript.segments.length} segments</summary>
        <ol>
          {record.transcript.segments.map((segment) => (
            <li key={segment.segment_id}>
              <time>{formatTranscriptTime(segment.start_ms)}</time>
              <div><strong>{segment.speaker}</strong><p>{segment.text}</p></div>
            </li>
          ))}
        </ol>
      </details>
    </>
  );
}

export function CalendarView({ today }: CalendarViewProps) {
  const gridScrollRef = useRef<HTMLDivElement>(null);
  const [weekStart, setWeekStart] = useState(() => startOfWorkWeek(today));
  const [sidebarMonth, setSidebarMonth] = useState(() => startOfMonth(today));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [recordingEvent, setRecordingEvent] = useState<CalendarEvent | null>(null);
  const [recordingAnalysis, setRecordingAnalysis] = useState<MeetingAnalysis | null>(null);
  const [recordingSrc, setRecordingSrc] = useState<string | null>(null);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryRecord, setSummaryRecord] = useState<MeetingRecord | null>(null);
  const [summarizingId, setSummarizingId] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  async function openSummary(event: CalendarEvent) {
    setSummarizingId(event.meeting_id);
    setSummaryError(null);
    try {
      const record = await summarizeMeeting(event.meeting_id);
      setSummaryRecord(record);
      setSelected(null);
    } catch (reason) {
      setSummaryError(reason instanceof Error ? reason.message : "Unable to summarize meeting");
    } finally {
      setSummarizingId(null);
    }
  }

  useEffect(() => {
    if (!recordingEvent) {
      setSummaryOpen(false);
      setRecordingAnalysis(null);
      setRecordingSrc(null);
    }
  }, [recordingEvent]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const rangeStart = isoDayStart(weekStart);
    const rangeEnd = isoDayStart(addDays(weekStart, 5));
    fetchCalendarEvents(rangeStart, rangeEnd)
      .then((rows) => {
        if (!cancelled) setEvents(rows);
      })
      .catch((reason) => {
        if (!cancelled) {
          setEvents([]);
          setError(reason instanceof Error ? reason.message : "Unable to load calendar events");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [weekStart]);

  useEffect(() => {
    setSidebarMonth(startOfMonth(weekStart));
  }, [weekStart]);

  useEffect(() => {
    const node = gridScrollRef.current;
    if (!node || loading) return;
    node.scrollTop = 8 * HOUR_HEIGHT;
  }, [loading, weekStart]);

  useEffect(() => {
    if (!recordingEvent) return;
    let cancelled = false;
    fetchMeetingRecord(recordingEvent.meeting_id)
      .then((record) => {
        if (cancelled) return;
        setRecordingAnalysis(record.analysis);
        setRecordingSrc(resolveRecordingUrl(record.transcript.recording_url));
      })
      .catch(() => {
        if (!cancelled) setRecordingAnalysis(null);
      });
    return () => {
      cancelled = true;
    };
  }, [recordingEvent]);

  const workDays = useMemo(
    () => Array.from({ length: 5 }, (_, index) => addDays(weekStart, index)),
    [weekStart]
  );

  const hours = useMemo(() => {
    const list: number[] = [];
    for (let h = GRID_START_HOUR; h <= GRID_END_HOUR; h += 1) list.push(h);
    return list;
  }, []);

  const isToday = (date: Date) => isSameDay(date, today);

  const monthWeeks = useMemo(() => buildMonthWeeks(sidebarMonth), [sidebarMonth]);
  const monthLabel = sidebarMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const highlightedWeekStart = startOfCalendarWeek(today);

  return (
    <div className="calendar-shell">
      <aside className="calendar-sidebar" aria-label="Calendar navigation">
        <h2 className="calendar-sidebar-title">Calendar</h2>
        <div className="calendar-mini-month">
          <div className="calendar-mini-month-head">
            <button type="button" className="calendar-month-label">
              {monthLabel}
              <span aria-hidden="true">▾</span>
            </button>
            <div className="calendar-month-nav">
              <button
                type="button"
                className="calendar-mini-nav-btn"
                aria-label="Previous month"
                onClick={() => setSidebarMonth((prev) => addMonths(prev, -1))}
              >
                ↑
              </button>
              <button
                type="button"
                className="calendar-mini-nav-btn"
                aria-label="Next month"
                onClick={() => setSidebarMonth((prev) => addMonths(prev, 1))}
              >
                ↓
              </button>
            </div>
          </div>
          <div className="calendar-mini-weekdays">
            {WEEKDAY_LABELS.map((label, index) => (
              <span key={`${label}-${index}`}>{label}</span>
            ))}
          </div>
          <div className="calendar-mini-weeks">
            {monthWeeks.map((week) => {
              const weekKey = week[0].toISOString();
              const activeWeek = isSameCalendarWeek(week[0], highlightedWeekStart);
              return (
                <div className={`calendar-mini-week${activeWeek ? " active" : ""}`} key={weekKey}>
                  {week.map((day) => {
                    const outside = day.getMonth() !== sidebarMonth.getMonth();
                    return (
                      <button
                        type="button"
                        key={day.toISOString()}
                        className={`calendar-mini-day${outside ? " outside" : ""}${isToday(day) ? " today" : ""}`}
                        onClick={() => {
                          setSidebarMonth(startOfMonth(day));
                          setWeekStart(startOfWorkWeek(day));
                        }}
                      >
                        <span>{day.getDate()}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
        <div className="calendar-sidebar-divider" aria-hidden="true">
          <span>▾</span>
        </div>
        <button type="button" className="calendar-sidebar-link">
          <span className="calendar-sidebar-icon" aria-hidden="true">+</span>
          Add calendar
        </button>
        <div className="calendar-my-calendars">
          <button type="button" className="calendar-my-calendars-head">
            <span aria-hidden="true">▾</span>
            My calendars
          </button>
          <label>
            <input type="checkbox" defaultChecked readOnly />
            <span className="calendar-check-dot" aria-hidden="true" />
            <span>Calendar</span>
          </label>
          <button type="button" className="calendar-show-all">
            Show all
          </button>
        </div>
      </aside>

      <div className="calendar-main">
      <div className="calendar-toolbar">
        <div className="calendar-toolbar-left">
          <button type="button" className="calendar-btn" onClick={() => setWeekStart(startOfWorkWeek(today))}>
            Today
          </button>
          <button
            type="button"
            className="calendar-icon-btn"
            aria-label="Previous week"
            onClick={() => setWeekStart((prev) => addDays(prev, -7))}
          >
            ‹
          </button>
          <button
            type="button"
            className="calendar-icon-btn"
            aria-label="Next week"
            onClick={() => setWeekStart((prev) => addDays(prev, 7))}
          >
            ›
          </button>
          <strong className="calendar-range">{formatRange(weekStart)}</strong>
        </div>
        <div className="calendar-toolbar-right">
          <span className="calendar-view-chip">Work week</span>
          <button type="button" className="calendar-btn calendar-btn-primary">
            + New meeting
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="calendar-grid-wrap" ref={gridScrollRef}>
        {loading ? (
          <p className="calendar-loading">Loading calendar events…</p>
        ) : (
          <div className="calendar-grid">
            <div className="calendar-corner" />
            {workDays.map((day) => (
              <div className={`calendar-day-head${isToday(day) ? " today" : ""}`} key={day.toISOString()}>
                <span>{formatDayHeader(day)}</span>
              </div>
            ))}

            <div className="calendar-times">
              {hours.map((hour) => (
                <div className="calendar-time-slot" key={hour} style={{ height: HOUR_HEIGHT }}>
                  <span>
                    {new Date(2000, 0, 1, hour).toLocaleTimeString(undefined, {
                      hour: "numeric",
                      minute: "2-digit"
                    })}
                  </span>
                </div>
              ))}
            </div>

            {workDays.map((day) => (
              <div
                className="calendar-day-col"
                key={day.toISOString()}
                style={{ height: hours.length * HOUR_HEIGHT }}
              >
                <div className="calendar-day-lines">
                  {hours.map((hour) => (
                    <div className="calendar-hour-line" key={hour} style={{ height: HOUR_HEIGHT }} />
                  ))}
                </div>
                {events
                  .filter((event) => sameCalendarDay(new Date(event.started_at), day))
                  .map((event) => (
                    <button
                      type="button"
                      key={event.event_id}
                      className={`calendar-event${event.canceled ? " canceled" : ""}${
                        selected?.event_id === event.event_id ? " selected" : ""
                      }`}
                      style={eventStyle(event)}
                      onClick={() => setSelected(event)}
                    >
                      {event.recurring && <span className="calendar-event-badge" aria-hidden="true">↻</span>}
                      <strong>{event.canceled ? `Canceled: ${event.title}` : event.title}</strong>
                      <small>{event.organizer}</small>
                    </button>
                  ))}
              </div>
            ))}
          </div>
        )}
      </div>
      </div>

      {selected && (
        <div className="calendar-overlay" role="presentation" onClick={() => setSelected(null)}>
          <article
            className="calendar-meeting-card"
            role="dialog"
            aria-labelledby="meeting-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="calendar-meeting-head">
              <h2 id="meeting-title">{selected.title}</h2>
              <button type="button" className="calendar-icon-btn" aria-label="Close" onClick={() => setSelected(null)}>
                ×
              </button>
            </header>
            <div className="calendar-meeting-actions">
              <button type="button" className="calendar-btn">Join</button>
              <button type="button" className="calendar-btn">Chat</button>
            </div>
            <ul className="calendar-meeting-meta">
              <li>
                <span className="calendar-meta-icon">Time</span>
                {formatEventTime(selected)}
              </li>
              <li>
                <span className="calendar-meta-icon">Loc</span>
                {selected.location ?? "No location added"}
              </li>
              <li className="calendar-organizer">
                <span className="calendar-avatar">{selected.organizer_initials}</span>
                <div>
                  <strong>{selected.organizer} invited you.</strong>
                  <small>Accepted 2, Didn&apos;t respond 1</small>
                </div>
              </li>
              <li>
                <span className="calendar-meta-icon">Note</span>
                <p>{selected.description}</p>
              </li>
            </ul>
            {summaryError && <p className="calendar-action-error" role="alert">{summaryError}</p>}
            <footer className="calendar-meeting-footer">
              <button
                type="button"
                className="calendar-btn calendar-recording-btn"
                onClick={() => {
                  setRecordingEvent(selected);
                  setSelected(null);
                }}
              >
                View recording
              </button>
              <button
                type="button"
                className="calendar-btn calendar-ai-btn"
                disabled={summarizingId === selected.meeting_id}
                onClick={() => void openSummary(selected)}
              >
                <span aria-hidden="true">✦</span>
                {summarizingId === selected.meeting_id ? "Summarizing…" : "Summarize"}
              </button>
            </footer>
          </article>
        </div>
      )}

      {summaryRecord && (
        <div className="calendar-overlay" role="presentation" onClick={() => setSummaryRecord(null)}>
          <article
            className="calendar-summary-modal"
            role="dialog"
            aria-labelledby="summary-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="eyebrow">AI meeting summary</p>
                <h2 id="summary-title">{summaryRecord.transcript.title}</h2>
              </div>
              <button
                type="button"
                className="calendar-icon-btn"
                aria-label="Close summary"
                onClick={() => setSummaryRecord(null)}
              >
                ×
              </button>
            </header>
            <div className="calendar-summary-body">
              <MeetingSummary record={summaryRecord} />
            </div>
          </article>
        </div>
      )}

      {recordingEvent && (
        <div className="calendar-overlay calendar-recording-overlay" role="presentation" onClick={() => setRecordingEvent(null)}>
          <div className="calendar-recording-modal" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <p className="eyebrow">Meeting recording</p>
                <h2>{recordingEvent.title}</h2>
              </div>
              <button type="button" className="calendar-icon-btn" aria-label="Close recording" onClick={() => setRecordingEvent(null)}>
                ×
              </button>
            </header>
            <div className="calendar-video-frame">
              {recordingSrc ? (
                <video controls autoPlay playsInline src={recordingSrc}>
                  Your browser does not support embedded video.
                </video>
              ) : (
                <p className="calendar-video-placeholder">Loading recording…</p>
              )}
            </div>
            <div className="calendar-recording-footer">
              <p className="calendar-recording-caption">
                Mock playback — {recordingEvent.organizer}, {formatEventTime(recordingEvent)}
              </p>
              <button
                type="button"
                className="calendar-summary-btn"
                disabled={!recordingAnalysis}
                onClick={(event) => {
                  event.stopPropagation();
                  setSummaryOpen((open) => !open);
                }}
              >
                View summary
              </button>
              {summaryOpen && recordingAnalysis && (
                <aside
                  className="calendar-summary-panel"
                  aria-label="Meeting summary"
                  onClick={(event) => event.stopPropagation()}
                >
                  <header>
                    <p className="eyebrow">AI summary</p>
                    <button type="button" className="calendar-icon-btn" aria-label="Close summary" onClick={() => setSummaryOpen(false)}>
                      ×
                    </button>
                  </header>
                  <p className="calendar-summary-lead">{recordingAnalysis.summary}</p>
                  {recordingAnalysis.decisions.length > 0 && (
                    <section>
                      <h3>Decisions</h3>
                      <ul>
                        {recordingAnalysis.decisions.map((item) => (
                          <li key={item.text}>{item.text}</li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {recordingAnalysis.action_items.length > 0 && (
                    <section>
                      <h3>Action items</h3>
                      <ul>
                        {recordingAnalysis.action_items.map((item) => (
                          <li key={item.text}>
                            {item.text}
                            {item.owner && <small> — {item.owner}</small>}
                            {item.due_date && <small> (due {item.due_date})</small>}
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {recordingAnalysis.open_questions.length > 0 && (
                    <section>
                      <h3>Open questions</h3>
                      <ul>
                        {recordingAnalysis.open_questions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </section>
                  )}
                </aside>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
