# Lotus architecture

Lotus is deployed as one authenticated Cloud Run service hosting the FastAPI API and compiled
React workspace. Google ADK is the agent framework. The browser never selects an agent mode: a
schema-validated Planner creates the execution graph and Result always runs last.

```mermaid
flowchart LR
  UI[React workspace] -->|POST /v1/chat/stream| API[Cloud Run / FastAPI]
  API --> Planner[ADK Planner]
  Planner --> Docs[Documents Agent]
  Planner --> Planning[Planning Agent]
  Planner --> People[People Agent]
  Planner --> Meeting[Meeting Agent]
  Planner --> Web[Web Search Agent]
  Planner --> Code[Code Agent]
  Docs --> Result[ADK Result]
  Planning --> Result
  People --> Result
  Meeting --> Result
  Web --> Result
  Code --> Result
  Docs --> DocsMCP[Documents MCP]
  Planning --> PlannerMCP[Planner MCP]
  People --> PeopleMCP[Employee Directory MCP]
  Meeting --> CalendarMCP[Calendar MCP]
  CalendarMCP --> MeetingTools[Analysis + anomaly tools]
  DocsMCP --> PG[(Cloud SQL PostgreSQL + pgvector)]
  PlannerMCP --> PG
  PeopleMCP --> PG
  CalendarMCP --> PG
  MeetingTools --> PG
  API --> PG
  Seed[Cloud Run seed job] -->|fixture bootstrap| PG
  Web --> Search[Google Search grounding]
  Code --> Repos[(Authorized repositories)]
  API --> Chat[(Persistent conversations)]
  Chat --> PG
  API -. safe RunEvent SSE .-> UI
  API -. metadata-only OTel .-> Trace[Cloud Trace]
```

The editable Mermaid source above is the source of truth. Exported hackathon assets are in
`docs/assets/lotus-architecture.svg` and `docs/assets/lotus-architecture.png`.

## Runtime boundaries

- `RUNTIME_MODE` controls generation. Cloud Run uses live Planner, Documents, Planning, People,
  Meeting, Result, and Google Search agents. Meeting analysis is a task of the Meeting Agent, not a
  separate agent; deterministic anomaly detection runs as a tool after analysis extraction.
- `EMBEDDING_RUNTIME_MODE` independently controls indexing/query embeddings. Cloud Run uses the
  deterministic 768-dimensional `fixture:hash-v1:768` embedder, so query vectors are computed
  locally without a model call.
- Deployed Cloud Run uses `STORE_BACKEND=postgres` and reads all searchable and mutable workspace
  state from Cloud SQL. Packaged fixtures are seed inputs used only by the migration/seed jobs;
  API startup never reads or embeds them.
- `STORE_BACKEND=memory` remains available only for deterministic tests and explicit local demos.
- Planning, Documents, People, and Calendar specialists use scoped read-only MCP tools. The browser
  sends IDs only; each tool resolves the entity in PostgreSQL and re-checks tenant, project, and
  ACLs.

## Streaming and observability

`POST /v1/chat/stream` emits schema-validated events for run start, agent/tool node state, bounded
answer deltas, completion, failure, and heartbeat. Events contain counts, timings, bounded tool
inputs, and redacted previews—not system prompts, credentials, complete transcripts, or hidden reasoning. The
same execution and session IDs correlate the opt-in Run inspector, structured logs, ADK spans,
and Google Cloud Trace. Conversation messages are persisted; safe run events remain browser-local.

## Future integrations

The dashed future boundary is limited to replacing Lotus's read-only mock MCP data with live Jira,
Confluence, Google Calendar, GitHub, and employee-directory adapters. Agent contracts, navigation
targets, and authorization checks remain unchanged.

## Security invariants

Every retrieval path filters tenant, project, principals, and active embedding model before
ranking. Mock code access additionally checks repository scope, rejects traversal, bounds file and
result sizes, and is read-only. Raw HTML is disabled in rendered Markdown. Prompt/response span
capture is disabled in the Cloud Run environment.
