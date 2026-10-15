# Lotus architecture

Lotus is deployed as one authenticated Cloud Run service hosting the FastAPI API and compiled
React workspace. Google ADK is the agent framework. The browser never selects an agent mode: a
schema-validated Planner creates the execution graph and Result always runs last.

```mermaid
flowchart LR
  UI[React workspace] -->|POST /v1/chat/stream| API[Cloud Run / FastAPI]
  API --> Planner[ADK Planner]
  Planner --> Data[Data Agent]
  Planner --> Meeting[Meeting Agent]
  Planner --> Web[Web Search Agent]
  Planner --> Code[Mock Code Agent]
  Meeting --> Anomaly[Deterministic Anomaly]
  Data --> Result[ADK Result]
  Meeting --> Result
  Web --> Result
  Code --> Result
  Anomaly --> Result
  Data --> Docs[(Fixture documents)]
  Meeting --> Transcripts[(Transcript JSON + chunks)]
  Web --> Search[Google Search grounding]
  Code --> Repos[(Authorized mock repos)]
  API -. safe RunEvent SSE .-> UI
  API -. metadata-only OTel .-> Trace[Cloud Trace]
  Docs -. future .-> PG[(PostgreSQL + pgvector)]
  Transcripts -. future .-> PG
```

The editable Mermaid source above is the source of truth. Exported hackathon assets are in
`docs/assets/lotus-architecture.svg` and `docs/assets/lotus-architecture.png`.

## Runtime boundaries

- `RUNTIME_MODE` controls generation. Cloud Run uses live Planner, Result, Meeting Analysis, and
  Google Search agents.
- `EMBEDDING_RUNTIME_MODE` independently controls indexing/query embeddings. The scale-to-zero
  memory deployment uses deterministic 768-dimensional fixture embeddings, avoiding live
  re-embedding at each cold start.
- `STORE_BACKEND=memory` remains the no-cost deployment. PostgreSQL/pgvector repositories and
  migrations remain ready for a later Cloud SQL deployment.
- Planning/Jira and Docs/Confluence selections use ID-only workspace context. Their final browser
  wiring waits for Vanshika's branch; server-side adapters must resolve IDs and re-check ACLs.

## Streaming and observability

`POST /v1/chat/stream` emits schema-validated events for run start, agent/tool node state, bounded
answer deltas, completion, failure, and heartbeat. Events contain counts, timings, and redacted
previews—not prompts, tokens, system instructions, complete transcripts, or hidden reasoning. The
same execution and session IDs correlate the session-scoped Run inspector, structured logs, ADK
spans, and Google Cloud Trace. Server-side run history is intentionally not persisted.

## Security invariants

Every retrieval path filters tenant, project, principals, and active embedding model before
ranking. Mock code access additionally checks repository scope, rejects traversal, bounds file and
result sizes, and is read-only. Raw HTML is disabled in rendered Markdown. Prompt/response span
capture is disabled in the Cloud Run environment.
