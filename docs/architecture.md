# Lotus architecture baseline

Lotus uses a schema-validated Google ADK Planner with small, tool-scoped specialists.
All retrieved content is untrusted data, and all model outputs that drive program
logic must validate against Pydantic or JSON schemas.

The first vertical slice is:

1. Accept an authenticated, scoped company question.
2. Let the Planner select Data, Meeting, Web, and optional Anomaly work.
3. Normalize authorized results into one evidence model.
4. Run Result last to return a cited answer or explicit abstention.
5. Render route, scope, provenance, and evidence in the web UI.

Provider integrations remain behind Lotus-owned interfaces so deterministic
fixtures can exercise the entire application without cloud credentials.

## Provisional cloud baseline

The deployment target is one Cloud Run service plus Cloud SQL PostgreSQL with
pgvector. No cloud runtime or database resource is provisioned yet. The current
hackathon recommendation is `asia-south1` for Cloud Run and Cloud SQL, with the
Agent Platform model endpoint configured independently as `global`.
