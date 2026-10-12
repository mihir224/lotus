# Lotus

Lotus is a unified enterprise AI workspace for trusted knowledge retrieval,
meeting intelligence, bounded background code changes, document analysis, and
grounded web research.

This repository starts from the hackathon PRD in:

`/Users/mihir.saini/Documents/Codex/2026-10-13/referenced-chatgpt-conversation-this-is-an/outputs/unified-enterprise-ai-workspace-prd.md`

## Intended stack

- React + Vite + TypeScript for the web workspace
- Python + FastAPI for the API and worker boundaries
- Google ADK and Gemini on Vertex AI for orchestration and model calls
- BigQuery, Firestore, Cloud Storage, and Cloud Tasks for managed data and jobs
- Read-only Jira and Confluence access through narrow MCP adapters

## Repository layout

```text
apps/       Web and API entry points
agents/     ADK router and bounded specialists
workers/    Ingestion, meeting, and coding background workers
packages/   Shared retrieval, connector, storage, and security modules
schemas/    JSON contracts used across agents and APIs
skills/     Versioned company coding policies
infra/      Deployment and local infrastructure
tests/      Unit, integration, end-to-end, and evaluation tests
demo_data/  Deterministic hackathon fixtures
docs/       Architecture, audit, and demo documentation
```

The initial code-reuse assessment is in [docs/reuse-audit.md](docs/reuse-audit.md).
Reference repositories are used for ideas only; Lotus code is written from scratch.

## Run locally

Requires Python 3.12+, `uv`, and Node.js 20+.

```bash
uv sync
npm install --prefix apps/web
make api
```

In a second terminal:

```bash
make web-dev
```

Open `http://127.0.0.1:5173`. The fixture-backed API runs at
`http://127.0.0.1:8000` and requires no cloud credentials.

## Verify

```bash
make test
make lint
npm run test --prefix apps/web
npm run build --prefix apps/web
```
