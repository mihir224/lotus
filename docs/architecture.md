# Lotus architecture baseline

Lotus will use a deterministic supervisor with small, tool-scoped specialists.
All retrieved content is untrusted data, and all model outputs that drive program
logic must validate against a schema in `schemas/`.

The first vertical slice is:

1. Accept a scoped company question.
2. Route exact identifiers to a fake/live read adapter and conceptual questions
   to product or technical retrieval.
3. Normalize all results into one evidence envelope.
4. Return a cited answer or an explicit abstention.
5. Render route, scope, provenance, and evidence in the web UI.

Provider integrations remain behind Lotus-owned interfaces so deterministic
fixtures can exercise the entire application without cloud credentials.

## Provisional cloud baseline

`us-central1` is the configurable default because it is one of the US regions
eligible for the Google Cloud Storage always-free allowance and works well with
the intended serverless footprint. No resource is provisioned automatically.
Model and Speech-to-Text availability must pass a readiness check before a real
project is deployed.
