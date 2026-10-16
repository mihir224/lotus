# Lotus backend agent context

## Runtime and entry points

- FastAPI app: `apps/api/lotus_api/main.py`
- Settings: `config.py`, loaded from the root `.env`
- Service cache: `service.py` and `storage/factory.py`; restart the API after changing `.env`
- Models and validated contracts: `models.py`
- Local commands: `make db-up`, `make migrate`, `make seed`, `make api`

## Orchestration contract

`agents/orchestrator.py` owns controlled execution. In `agent_platform` mode, the Google ADK
Planner produces an `ExecutionPlan`; independent Documents, Planning, People, Meeting, Web, and
Code work runs concurrently; Result runs last. A conversational request may validly use only Result.
If Planner times out, use the safe Result-only degraded plan—never retrieve arbitrary data.

Current live boundaries:

- Planner and Result are ADK/Gemini agents.
- Web uses the ADK Google Search tool and converts grounding metadata to `Evidence`.
- Documents, Planning, People, and Meeting are ADK specialists using scoped internal Streamable
  HTTP MCP tools.
- Code is a read-only specialist over the authorized repositories packaged under `demo_data/code`.
- Meeting owns transcript retrieval and schema-constrained analysis. `analyze_meeting` exposes the
  shared processing path to chat; the Summarize API calls the same path directly. Deterministic
  anomaly and clarification tools live in `meeting_analysis.py`; there is no Anomaly Agent or
  Meeting Analysis Agent.
- Every ADK call has a bounded timeout. Preserve safe fallbacks and related logs.

Fixture mode uses `fixture_plan`, deterministic normalized hash embeddings, fixture web results,
and deterministic answer composition. Do not make fixture tests call Google.

## Specialist tool selection

The specialist chooses the narrow tool after the Planner chooses the specialist:

- Documents MCP: `list_documents` for inventories/counts, `get_document` for a known ID, and
  `search_documents` only for semantic content retrieval.
- Planner MCP: `get_project`, `get_planning_item`, the compatibility
  `get_project_stakeholders`, and structured `search_planning_items`; Planning never uses vector
  retrieval. New stakeholder/contact questions route to People.
- Employee Directory MCP: `get_employee`, `search_employees`,
  `get_employee_project_stakeholders`, and `find_subject_matter_experts`. People results are scoped
  by tenant and ACL; expertise matches must retain their structured-data basis.
- Calendar MCP: `search_meetings` for arbitrary date ranges, counts, titles, and metadata;
  `get_meeting` for one selected meeting; `search_transcript_chunks` only for topics, quotes,
  keywords, or discussion content; and `analyze_meeting` for summary, decisions, action items,
  questions, clarifications, and deterministic anomaly checks.

Do not reintroduce keyword routing in the live path. Deterministic phrase/date handling is an
offline fixture fallback only. MCP scope comes from trusted run context, never model-supplied tenant
or ACL values.

## Storage invariants

PostgreSQL + pgvector stores retrieval, workspace, and conversation state, including:

- `document_embeddings`
- `meeting_transcripts`
- `transcript_embeddings`
- `calendar_events`
- `board_issues`
- `chat_sessions` and `chat_messages`
- `workspace_projects`, `employees`, and `project_stakeholders`

Both vector tables use normalized 768-dimensional vectors. Never rank rows created by a different
`embedding_model`. Every search MUST filter tenant, project, ACL overlap, and active model before
ordering by cosine distance. Transcript evidence MUST retain meeting ID and timestamp range.

`STORE_BACKEND=memory` is the zero-infrastructure test path. Deployed Cloud Run and normal local
integration runs use `STORE_BACKEND=postgres`. Raw files under `demo_data` are bootstrap inputs,
not an API-time retrieval fallback. Seeding MUST remain idempotent for each embedding model.

Calendar creation stores only `calendar_events`. It MUST NOT fabricate a transcript or mark a
scheduled event as processed. A `meeting_transcripts` row is created only when transcript content is
processed. Legacy one-line `Scheduled meeting: …` placeholders are excluded from MCP details and
transcript vector search.

## Conversations and run events

`chat_sessions` and `chat_messages` are user-and-tenant scoped. Missing `session_id` creates a new
conversation; clients restore history with the explicit session APIs. Planner and Result receive
only the bounded recent-message window.

SSE run events merge `node.started` and `node.completed` in the UI. Tool events may expose bounded
query and filter inputs plus count-oriented outputs in Debug Mode. Continue redacting credentials,
authorization headers, system prompts, full transcripts, vectors, and unrestricted payloads.

## Authentication and abuse control

`AUTH_MODE=dev` trusts local `X-Lotus-*` headers. `AUTH_MODE=google` requires a server-verified
Google ID token and a non-empty email/domain allowlist. Do not weaken the allowlist or accept a
decoded-but-unverified browser token. Google users receive the existing `group:demo` fixture ACL.

Only health, readiness, and auth configuration are public. `/v1/auth/me` and all data routes require
authentication in Google mode. Chat is limited per authenticated user by `rate_limit.py`; this
limiter is per process and assumes one Cloud Run instance for the hackathon.

## API compatibility

Preserve `POST /v1/chat/messages` fields and evidence shape. Calendar and meeting APIs are listed in
`meeting-api-contract.md`. The UI must call APIs rather than import backend fixture files.

## Logging and privacy

Use the `uvicorn.error.lotus` logger hierarchy. Log request/execution IDs, selected agents, counts,
durations, timeouts, and failures. Never log full prompts, transcripts, bearer tokens, credentials,
or vector contents. Bounded tool-input previews are sent only in authenticated SSE debug events;
they are not an authorization input and must not be copied into backend logs or traces.

