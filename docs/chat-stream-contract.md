# Chat and run-stream contract

`POST /v1/chat/messages` remains the compatible blocking API. Both blocking and streaming
responses include an `execution_id`. Requests may include `session_id`, `meeting_id`,
`repository_id`, `planning_item_ids`, and `document_ids`; selected IDs are re-resolved and
authorized by Lotus rather than accepting browser-provided page content.

`POST /v1/chat/stream` accepts the same authenticated JSON request and returns
`text/event-stream`. Event names and JSON `event_type` values are:

- `run.started`
- `node.started`, `node.completed`, `node.failed`
- `answer.delta`, `answer.completed`
- `run.failed`
- `heartbeat`

`answer.completed.response` contains the final `GroundedAnswer`. Agent nodes use IDs such as
`planner`, `documents`, `planning`, `people`, `meeting`, `web`, `code`, and `result`. Tool nodes set
`parent_id` to their owning agent. Input/output previews are deliberately bounded; credentials,
system prompts, full transcripts, and unrestricted payloads remain redacted.

Example request:

```json
{
  "message": "Compare our checkout retry implementation with the runbook",
  "project_id": "payments",
  "repository_id": "checkout-service",
  "document_ids": ["ADR-017"],
  "session_id": "browser-generated-uuid"
}
```

The browser must tolerate SSE frames split across network chunks. It may cancel the HTTP request,
show an interrupted state, and retain only bounded current-session events in `sessionStorage`.
