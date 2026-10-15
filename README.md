# Lotus

Lotus is a unified enterprise AI workspace for trusted knowledge retrieval,
meeting intelligence, document analysis, and grounded web research.

This repository starts from the hackathon PRD in:

`/Users/mihir.saini/Documents/Codex/2026-10-13/referenced-chatgpt-conversation-this-is-an/outputs/unified-enterprise-ai-workspace-prd.md`

## Implemented stack

- React + Vite + TypeScript for the web workspace
- Python + FastAPI for the API and worker boundaries
- Google ADK 2.12 and Gemini Enterprise Agent Platform for live orchestration
- PostgreSQL 17 with pgvector for document and timestamped transcript retrieval
- Deterministic fixture adapters for Jira, Confluence, SharePoint, GitHub, calendar, and web

There is no user-selected chat mode. The Planner Agent selects Data, Meeting, and
Web specialists, optionally runs Anomaly after meeting evidence, and always runs
the Result Agent last. Fixture mode uses the same contracts without cloud credentials.

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
Credentials, and re-seed so stored vectors and query vectors share the same
embedding model. The live defaults use the Agent Platform `global` endpoint,
`gemini-3.7-flash`, and 768-dimensional `gemini-embedding-001` vectors.

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
