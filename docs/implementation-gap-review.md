# Implementation gap review

## Addressed in this milestone

| Priority | Gap | Resolution |
|---|---|---|
| P0 | Memory cold starts rebuilt live embeddings | Generation and embedding runtimes are separate; Cloud Run uses deterministic fixture embeddings. |
| P0 | Chat blocked until one JSON response | Authenticated SSE exposes safe progress, graph nodes, answer deltas, heartbeats, and failures. |
| P0 | Markdown displayed as plain text | GFM Markdown is sanitized and rendered through a reusable component. |
| P0 | Meeting summaries were deterministic only | The ADK Meeting Agent generates schema-constrained analysis in live mode; deterministic analysis and anomaly tools remain the fallback. |
| P1 | No execution visualizer | Evidence/Run inspector displays agent/tool state and bounded previews, retained in `sessionStorage`. |
| P1 | No code specialist | Planner can route to an ACL-aware, read-only Code Agent with file/line citations. |
| P1 | No trace export | ADK and Lotus spans use authenticated Google Cloud OTLP exporters with content capture disabled. |
| P1 | No frontend regression tests | Vitest covers split SSE frames, composer keys/placeholder, Markdown/GFM, and XSS stripping. |
| P0 | Chat replaced the previous run | Conversations and messages now persist per authenticated user in Cloud SQL. |
| P1 | Workspace sources were direct retrieval nodes | Documents, Planning, People, and Meeting are ADK specialists with scoped MCP tools. |
| P1 | Employee information was project-only | People Agent uses a scoped Employee Directory MCP for profiles, contacts, project stakeholders, and metadata-backed expert discovery. |

## Still open or gated

- The unused `build_agent_tree` transfer prototype has been removed. Controlled orchestration is
  the only execution path and enforces concurrency, Result-last ordering, ACLs, and normalized
  evidence.
- Production uses Cloud SQL/pgvector for workspace data, vectors, and per-user conversation history.
- Live Google Search grounding is wired, but gated evaluation still requires ADC and quota. The
  acceptance test must require grounded titles/URLs and skip explicitly without credentials.
- Live Jira, Confluence, Calendar, GitHub, and employee-directory adapters remain future work. The
  current MCP contracts resolve Lotus-owned IDs and enforce authorization server-side.
- Live GitHub OAuth/API, repository mutation, execution, and commits remain out of scope.
- Client disconnect cancellation is best-effort for the HTTP stream; a model call already in
  flight cannot yet be force-cancelled through ADK.
