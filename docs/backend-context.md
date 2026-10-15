# Lotus backend agent context

## Runtime and entry points

- FastAPI app: `apps/api/lotus_api/main.py`
- Settings: `config.py`, loaded from the root `.env`
- Service cache: `service.py` and `storage/factory.py`; restart the API after changing `.env`
- Models and validated contracts: `models.py`
- Local commands: `make db-up`, `make migrate`, `make seed`, `make api`

## Orchestration contract

`agents/orchestrator.py` owns controlled execution. In `agent_platform` mode, the Google ADK
Planner produces an `ExecutionPlan`; independent Data, Meeting, and Web work runs concurrently;
Anomaly runs only after Meeting; Result runs last. A conversational request may validly use only
Result. If Planner times out, use the safe Result-only degraded plan—never retrieve arbitrary Data.

Current live boundaries:

- Planner and Result are ADK/Gemini agents.
- Web uses the ADK Google Search tool and converts grounding metadata to `Evidence`.
- Data and Meeting execute authorized Python retrieval selected by the Planner.
- Anomaly reads stored meeting analysis; deterministic transcript analysis lives in
  `meeting_analysis.py`.
- Every ADK call has a bounded timeout. Preserve safe fallbacks and related logs.

Fixture mode uses `fixture_plan`, deterministic normalized hash embeddings, fixture web results,
and deterministic answer composition. Do not make fixture tests call Google.

## Storage invariants

PostgreSQL + pgvector has five application tables created across the Alembic migration chain:

- `document_embeddings`
- `meeting_transcripts`
- `transcript_embeddings`
- `calendar_events`
- `board_issues`

Both vector tables use normalized 768-dimensional vectors. Never rank rows created by a different
`embedding_model`. Every search MUST filter tenant, project, ACL overlap, and active model before
ordering by cosine distance. Transcript evidence MUST retain meeting ID and timestamp range.

`STORE_BACKEND=memory` is the zero-infrastructure test path. Deployed Cloud Run and normal local
integration runs use `STORE_BACKEND=postgres`. Raw files under `demo_data` are bootstrap inputs,
not an API-time retrieval fallback. Seeding MUST remain idempotent for each embedding model.

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
or vector contents.

