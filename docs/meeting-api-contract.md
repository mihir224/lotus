# Meeting API contract

The UI should call the backend; it should not import fixture files.

- `GET /v1/calendar/events?project_id=payments&date_from=...&date_to=...` lists work-week calendar
  events from the KnowledgeStore (seeded from `demo_data/calendar/events.json`). Each row includes a
  `meeting_id` for detail lookup.
- `POST /v1/calendar/events` creates a calendar event and linked meeting record for the active tenant.
  Created events are persisted in the KnowledgeStore (`calendar_events` when using Postgres). Re-run
  `make seed` to refresh fixture rows from disk without removing user-created events that share new ids.
- `GET /v1/meetings?project_id=payments&team=platform&date_from=...&date_to=...` lists calendar-ready historical meetings.
- `GET /v1/meetings/{meeting_id}` returns metadata, the complete timestamped transcript, and generated analysis.
- `POST /v1/meetings/{meeting_id}/process` accepts a transcript payload and idempotently builds transcript embeddings plus analysis.

All calls may send `X-Lotus-Tenant` and `X-Lotus-User`. The process body contains
`calendar_event_id`, `title`, `project_id`, `team`, `started_at`, `ended_at`,
`participants`, `language_code`, optional `recording_url`, and timestamped `segments`.

Chat requests contain only `message`, `project_id`, and optional meeting/repository context.
There is no mode field: the Planner Agent selects Data, Meeting, Web, and Anomaly work,
and the Result Agent always runs last.
