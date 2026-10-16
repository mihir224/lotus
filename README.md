# Lotus

Lotus is a unified enterprise AI workspace for trusted knowledge retrieval, employee and
stakeholder discovery, meeting intelligence, document analysis, code context, and grounded web
research.

This repository starts from the hackathon PRD in:

`/Users/mihir.saini/Documents/Codex/2026-10-13/referenced-chatgpt-conversation-this-is-an/outputs/unified-enterprise-ai-workspace-prd.md`

## Implemented stack

- React + Vite + TypeScript for the web workspace
- Python + FastAPI for the API and worker boundaries
- Google ADK 2.12 and Gemini Enterprise Agent Platform for live orchestration
- PostgreSQL 16 with pgvector for document and timestamped transcript retrieval
- Scoped mock MCP adapters for planning, documents, calendar, and the employee directory
- Deterministic repository and web fixtures for credential-free development

There is no user-selected chat mode. The Planner Agent selects Documents, Planning, People,
Meeting, Web, and Code specialists and always runs the Result Agent last. Meeting analysis is a
Meeting Agent capability; anomaly detection is a deterministic tool, not a separate agent. Fixture
mode uses the same contracts without cloud credentials.

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

Requires Python 3.12+, `uv`, Node.js 20+, and Docker for the pgvector path.

```bash
uv sync
npm install --prefix apps/web
cp .env.example .env
make db-up
make migrate
make seed
make api
```

In a second terminal:

```bash
make web-dev
```

Open `http://127.0.0.1:5173`. The fixture-backed API runs at
`http://127.0.0.1:8000` and requires no cloud credentials.

For a zero-infrastructure fixture run, set `STORE_BACKEND=memory`. The deployed service uses Cloud
SQL PostgreSQL with pgvector and deterministic `fixture:hash-v1:768` embeddings; packaged fixtures
are loaded only by the idempotent seed job. For live Gemini,
set `RUNTIME_MODE=agent_platform`, configure the project and Application Default
Credentials. Generation and embeddings are configured independently: the deployed service uses
the Agent Platform `global` endpoint with `gemini-3.7-flash`, while document and transcript vectors
remain on the deterministic 768-dimensional `fixture:hash-v1:768` model. If the embedding runtime
changes, re-seed so stored vectors and query vectors use the same model ID.

The calendar/meeting integration contract is documented in
[docs/meeting-api-contract.md](docs/meeting-api-contract.md).
Google Sign-In setup and Cloud Run abuse guardrails are documented in
[docs/google-auth-and-cloud-run.md](docs/google-auth-and-cloud-run.md).
AI agents working in this repository should start with
[docs/context.md](docs/context.md) and load the relevant backend, frontend, or deployment context.

## Verify

```bash
make test
make lint
npm run test --prefix apps/web
npm run build --prefix apps/web
```
