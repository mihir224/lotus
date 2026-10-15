# Implementation gap review

## Addressed in this milestone

| Priority | Gap | Resolution |
|---|---|---|
| P0 | Memory cold starts rebuilt live embeddings | Generation and embedding runtimes are separate; Cloud Run uses deterministic fixture embeddings. |
| P0 | Chat blocked until one JSON response | Authenticated SSE exposes safe progress, graph nodes, answer deltas, heartbeats, and failures. |
| P0 | Markdown displayed as plain text | GFM Markdown is sanitized and rendered through a reusable component. |
| P0 | Meeting summaries were deterministic only | ADK Meeting Analysis generates schema-constrained output in live mode with deterministic fallback and anomaly checks. |
| P1 | No execution visualizer | Evidence/Run inspector displays agent/tool state and bounded previews, retained in `sessionStorage`. |
| P1 | No code specialist | Planner can route to an ACL-aware, read-only mock Code Agent with file/line citations. |
| P1 | No trace export | ADK and Lotus spans use authenticated Google Cloud OTLP exporters with content capture disabled. |
| P1 | No frontend regression tests | Vitest covers split SSE frames, composer keys/placeholder, Markdown/GFM, and XSS stripping. |

## Still open or gated

- The older `build_agent_tree` transfer prototype remains unused; controlled orchestration is the
  production path because it enforces concurrency, Result-last ordering, ACLs, and normalized
  evidence. It should be removed after the hackathon or converted into a tested equivalent—not
  activated alongside the current orchestrator.
- Production storage is still in memory. Cloud SQL/pgvector is deliberately separate because it
  adds continuous cost; session history is browser-scoped.
- Live Google Search grounding is wired, but gated evaluation still requires ADC and quota. The
  acceptance test must require grounded titles/URLs and skip explicitly without credentials.
- Planning/Jira and Docs/Confluence browser context is gated on Vanshika's merged selected-page
  state. The API accepts only selected IDs; Lotus-owned adapters must resolve those IDs.
- Live GitHub OAuth/API, repository mutation, execution, and commits remain out of scope.
- Client disconnect cancellation is best-effort for the HTTP stream; a model call already in
  flight cannot yet be force-cancelled through ADK.
