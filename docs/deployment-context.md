# Lotus deployment agent context

## Current state

The repository has a production multi-stage `Dockerfile` and
`infra/deploy-cloud-run-demo.sh`. Cloud Run service `lotus` is deployed in `asia-south1` at
`https://lotus-6n3idqotvq-el.a.run.app`; revision `lotus-00001-8pp` initially received 100% of
traffic. Public health, readiness, auth-configuration, and SPA smoke tests passed on 2026-10-15.
The deployed demo uses the in-memory fixture store and live Agent Platform runtime. Google login
will not work until the exact Cloud Run origin is added to the OAuth client's Authorized JavaScript
origins. There is no Cloud SQL instance, migration job, or Terraform configuration yet.

## Target architecture

Use GCP project `ai-builder-hackthon-vys`:

```text
Browser → public Cloud Run service → FastAPI/ADK → Agent Platform
                                  └→ Cloud SQL PostgreSQL + pgvector
```

For the hackathon, build React and FastAPI into one container and serve one same-origin HTTPS site.
Cloud Run must listen on `$PORT`. Use `asia-south1` for Cloud Run and Cloud SQL unless the user
chooses another region; keep Agent Platform and embeddings on their configured `global` endpoint.

## Required deployment work

1. Add `https://lotus-6n3idqotvq-el.a.run.app` to the OAuth Web client's authorized JavaScript
   origins and run an authenticated browser smoke test.
2. Confirm Cloud SQL's continuous cost before provisioning it.
3. Provision Cloud SQL PostgreSQL, enable `vector`, run Alembic, and seed the active live model.
4. Store the database credential in Secret Manager; attach Cloud SQL through the Cloud Run service.
5. Extend the dedicated runtime service account with least-privilege Cloud SQL and secret access.
   secret access. Use service identity/ADC—never ship a service-account key.
6. Switch the deployed service from `STORE_BACKEND=memory` to `STORE_BACKEND=postgres`.
7. Start with `max-instances=1`, conservative concurrency, and the application rate limiter.
8. Add the exact Cloud Run HTTPS origin to the OAuth Web client and run authenticated smoke tests.

## Security and cost rules

The Cloud Run URL must be public so unauthenticated browsers can load the login page. Application
APIs enforce Google authentication and allowlisting. The current limiter is per instance; before
scaling past one instance, move rate-limit state to a shared store. Add billing budgets and alerts,
but do not claim they are hard spending caps. Cloud SQL is normally continuously billed; confirm
cost acceptance before provisioning it.

Google Auth Platform branding, audience/test users, and Web OAuth client origins are manual console
steps. Everything else should be scripted with `gcloud` or infrastructure as code. See
`google-auth-and-cloud-run.md` for the current OAuth setup procedure.

## Secrets

NEVER commit `.env`, OAuth secrets, database passwords, ADC files, or service-account JSON. The
browser flow uses only the public OAuth client ID; retain any client secret solely in Secret Manager
if a future authorization-code flow requires it.
