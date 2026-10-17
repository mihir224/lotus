# Lotus deployment agent context

## Current architecture

Lotus runs in GCP project `ai-builder-hackthon-vys`, region `asia-south1`. One authenticated Cloud
Run service hosts the compiled React workspace and FastAPI/Google ADK backend. Agent generation
uses Agent Platform. Persistent workspace state and both vector indexes live in Cloud SQL
PostgreSQL with pgvector. Query embeddings use the deterministic local 768-dimensional
`fixture:hash-v1:768` implementation.

The image still contains `demo_data`, but only the Cloud Run seed job reads those files. The API
does not load fixture rows at startup and never falls back to memory if PostgreSQL is unavailable.

## GCP resources

- Cloud Run service: `lotus`, minimum instances `0`, maximum instances `1`, request timeout 600s
- Cloud SQL instance: `lotus-postgres`, PostgreSQL 16, single-zone `db-f1-micro`, 10 GB SSD
- Database/user: `lotus` / `lotus_app`
- Secret Manager secret: `lotus-db-password`
- Runtime service account: `lotus-runtime`
- Artifact Registry repository: `lotus`
- Cloud Run jobs: `lotus-migrate` and `lotus-seed`

The hackathon database has no HA, read replicas, automated backups, or point-in-time recovery.
Cloud SQL incurs continuous cost even when Cloud Run scales to zero.

## Provision and deploy

`infra/provision-cloud-sql.sh` is idempotent. It enables the required APIs, creates the minimum
database configuration, generates the application password once, stores it in Secret Manager, and
grants the runtime identity only Cloud SQL client and secret access.

`infra/deploy-cloud-run-demo.sh` builds one git-SHA-tagged image and uses it for migration, seed,
and service deployment. It deploys a no-traffic candidate, checks health and PostgreSQL readiness,
then sends 100% of traffic to that candidate. Export the public OAuth client ID before running it;
never export or handle the database password manually.

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
./infra/deploy-cloud-run-demo.sh
```

To roll back application traffic, list revisions and route traffic to the prior revision. Database
migrations must remain additive so the prior service remains compatible:

```bash
gcloud run revisions list --service=lotus --region=asia-south1
gcloud run services update-traffic lotus --region=asia-south1 --to-revisions=PREVIOUS_REVISION=100
```

## Cleanup

Cleanup is intentionally explicit because it destroys persistent data. Take any required export
before deleting the instance.

```bash
gcloud run jobs delete lotus-seed --region=asia-south1
gcloud run jobs delete lotus-migrate --region=asia-south1
gcloud sql instances delete lotus-postgres
gcloud secrets delete lotus-db-password
```

## Security invariants

The service is public only so browsers can load the login page. Protected APIs verify Google ID
tokens and require a verified Google account. Cloud SQL has a public IP for the managed connector,
but no authorized client networks; Cloud Run connects through its `/cloudsql/<instance>` Unix
socket. Never commit `.env`, OAuth secrets, database passwords, ADC files, or service-account keys.
Never log a resolved database URL, SQL parameters, prompts, transcript text, bearer tokens, or
credentials. Prompt and response content capture in Cloud Trace stays disabled.

Run migration and seed jobs before every candidate revision even when no new fixture rows are
expected. The API must remain compatible with legacy Cloud SQL rows: historical synthetic
`Scheduled meeting: …` transcript placeholders are ignored at retrieval time rather than treated as
real meeting content. Newly created calendar events no longer create such rows.
