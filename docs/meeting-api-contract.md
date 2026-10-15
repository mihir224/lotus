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

- `GET /v1/work-board?project_id=payments&team_id=platform` returns board metadata (fixture
  config), assignee roster, teams, and issues from the KnowledgeStore (seeded from
  `demo_data/work_board/issues.json`).
- `POST /v1/work-board/issues` creates a board issue for the active tenant. The server assigns
  `issue_key` from the team `key_prefix`, resolves `feature_title` from `demo_data/work_board/features.json`
  when `feature_key` is valid for the team, and persists via the KnowledgeStore. Use
  `assignee_id` / `reporter_id` of `unassigned` when not set.
- `PATCH /v1/work-board/issues/{issue_key}` updates title, type, status, or assignee; changes
  persist in the KnowledgeStore.
- `GET /v1/docs/catalog?project_id=payments` lists document pages grouped by team (aggregated from
  `document_embeddings`, seeded from `demo_data/enterprise/documents.json`).
- `GET /v1/docs/search?project_id=payments&q=...` keyword-search titles and bodies.
- `GET /v1/docs/sources/{source_id}?project_id=payments` returns a full page (combined chunks).
- `POST /v1/docs/sources` creates a Lotus-authored page in the KnowledgeStore only (not the fixture
  file); it is embedded for chat retrieval with `source_system: lotus`.

Chat requests contain only `message`, `project_id`, and optional meeting/repository context.
There is no mode field: the Planner Agent selects Data, Meeting, Web, and Anomaly work,
and the Result Agent always runs last.
