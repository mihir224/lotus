#!/usr/bin/env bash
set -euo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

PROJECT_ID="${PROJECT_ID:-ai-builder-hackthon-vys}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-lotus}"
INSTANCE_NAME="${INSTANCE_NAME:-lotus-postgres}"
DATABASE_NAME="${DATABASE_NAME:-lotus}"
DATABASE_USER="${DATABASE_USER:-lotus_app}"
DATABASE_SECRET="${DATABASE_SECRET:-lotus-db-password}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-lotus-runtime}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-lotus-build}"
ARTIFACT_REPOSITORY="${ARTIFACT_REPOSITORY:-lotus}"
MIGRATION_JOB="${MIGRATION_JOB:-lotus-migrate}"
SEED_JOB="${SEED_JOB:-lotus-seed}"

if [[ -z "${GOOGLE_OAUTH_CLIENT_ID:-}" ]]; then
  echo "GOOGLE_OAUTH_CLIENT_ID is required." >&2
  exit 1
fi
if [[ -z "${ALLOWED_GOOGLE_EMAILS:-}" && -z "${ALLOWED_GOOGLE_DOMAINS:-}" ]]; then
  echo "Set ALLOWED_GOOGLE_EMAILS or ALLOWED_GOOGLE_DOMAINS." >&2
  exit 1
fi
if [[ -z "$(gcloud auth list --filter='status:ACTIVE' --format='value(account)' 2>/dev/null)" ]]; then
  echo "No active gcloud account. Run: gcloud auth login" >&2
  exit 1
fi
command -v jq >/dev/null

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/provision-cloud-sql.sh"

gcloud services enable \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  telemetry.googleapis.com \
  --project "$PROJECT_ID"

RUNTIME_SERVICE_ACCOUNT_EMAIL="${RUNTIME_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SERVICE_ACCOUNT_EMAIL="${BUILD_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$BUILD_SERVICE_ACCOUNT_EMAIL" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$BUILD_SERVICE_ACCOUNT" \
    --display-name="Lotus Cloud Build" \
    --project "$PROJECT_ID"
fi

for role in \
  roles/aiplatform.user \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/telemetry.tracesWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT_EMAIL}" \
    --role="$role" \
    --condition=None >/dev/null
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SERVICE_ACCOUNT_EMAIL}" \
  --role=roles/run.builder \
  --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SERVICE_ACCOUNT_EMAIL}" \
  --role=roles/artifactregistry.writer \
  --condition=None >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
BUILD_SOURCE_BUCKET="gs://${PROJECT_ID}_${REGION}_cloudbuild"
BUILD_LOG_BUCKET="gs://${PROJECT_NUMBER}-${REGION}-cloudbuild-logs"
for bucket in "$BUILD_SOURCE_BUCKET" "$BUILD_LOG_BUCKET"; do
  if ! gcloud storage buckets describe "$bucket" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud storage buckets create "$bucket" \
      --project "$PROJECT_ID" \
      --location "$REGION" \
      --uniform-bucket-level-access >/dev/null
  fi
  gcloud storage buckets add-iam-policy-binding "$bucket" \
    --member="serviceAccount:${BUILD_SERVICE_ACCOUNT_EMAIL}" \
    --role=roles/storage.admin >/dev/null
done

INSTANCE_CONNECTION_NAME="$(gcloud sql instances describe "$INSTANCE_NAME" \
  --project "$PROJECT_ID" --format='value(connectionName)')"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

gcloud builds submit . \
  --tag "$IMAGE_URI" \
  --region "$REGION" \
  --service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SERVICE_ACCOUNT_EMAIL}" \
  --default-buckets-behavior=regional-user-owned-bucket \
  --project "$PROJECT_ID"

DATABASE_ENV="^|^STORE_BACKEND=postgres|EMBEDDING_RUNTIME_MODE=fixture|CLOUD_SQL_INSTANCE=${INSTANCE_CONNECTION_NAME}|DB_USER=${DATABASE_USER}|DB_NAME=${DATABASE_NAME}|PYTHONPATH=/workspace/apps/api"

gcloud run jobs deploy "$MIGRATION_JOB" \
  --image "$IMAGE_URI" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT_EMAIL" \
  --set-cloudsql-instances "$INSTANCE_CONNECTION_NAME" \
  --set-env-vars "$DATABASE_ENV" \
  --set-secrets="DB_PASSWORD=${DATABASE_SECRET}:latest" \
  --command=alembic \
  --args=upgrade,head \
  --task-timeout=10m \
  --max-retries=0 \
  --execute-now \
  --wait

gcloud run jobs deploy "$SEED_JOB" \
  --image "$IMAGE_URI" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT_EMAIL" \
  --set-cloudsql-instances "$INSTANCE_CONNECTION_NAME" \
  --set-env-vars "$DATABASE_ENV" \
  --set-secrets="DB_PASSWORD=${DATABASE_SECRET}:latest" \
  --command=python \
  --args=-m,lotus_api.seed \
  --task-timeout=10m \
  --max-retries=0 \
  --execute-now \
  --wait

SERVICE_ENV="^|^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}|GOOGLE_CLOUD_LOCATION=global|EMBEDDING_LOCATION=global|GOOGLE_GENAI_USE_ENTERPRISE=true|GOOGLE_GENAI_USE_VERTEXAI=false|RUNTIME_MODE=agent_platform|EMBEDDING_RUNTIME_MODE=fixture|STORE_BACKEND=postgres|CLOUD_SQL_INSTANCE=${INSTANCE_CONNECTION_NAME}|DB_USER=${DATABASE_USER}|DB_NAME=${DATABASE_NAME}|AUTH_MODE=google|GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}|ALLOWED_GOOGLE_EMAILS=${ALLOWED_GOOGLE_EMAILS:-}|ALLOWED_GOOGLE_DOMAINS=${ALLOWED_GOOGLE_DOMAINS:-}|AGENT_TIMEOUT_SECONDS=${AGENT_TIMEOUT_SECONDS:-90}|WEB_AGENT_TIMEOUT_SECONDS=${WEB_AGENT_TIMEOUT_SECONDS:-180}|AGENT_RATE_LIMIT_REQUESTS=${AGENT_RATE_LIMIT_REQUESTS:-10}|AGENT_RATE_LIMIT_WINDOW_SECONDS=${AGENT_RATE_LIMIT_WINDOW_SECONDS:-300}|TELEMETRY_ENABLED=true|ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false|OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT|OTEL_SERVICE_NAME=lotus-api|OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental"

gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_URI" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT_EMAIL" \
  --set-cloudsql-instances "$INSTANCE_CONNECTION_NAME" \
  --set-env-vars "$SERVICE_ENV" \
  --set-secrets="DB_PASSWORD=${DATABASE_SECRET}:latest" \
  --allow-unauthenticated \
  --cpu=1 \
  --memory=1Gi \
  --concurrency=10 \
  --min-instances=0 \
  --max-instances=1 \
  --timeout=600 \
  --tag=candidate \
  --no-traffic

SERVICE_JSON="$(gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" --region "$REGION" --format=json)"
CANDIDATE_URL="$(jq -r '.status.traffic[] | select(.tag == "candidate") | .url' <<<"$SERVICE_JSON")"
if [[ -z "$CANDIDATE_URL" || "$CANDIDATE_URL" == "null" ]]; then
  echo "Candidate revision URL was not created." >&2
  exit 1
fi

HEALTH_JSON="$(curl --fail --retry 3 --retry-delay 2 --silent --show-error \
  "${CANDIDATE_URL}/v1/healthz")"
READY_JSON="$(curl --fail --retry 3 --retry-delay 2 --silent --show-error \
  "${CANDIDATE_URL}/v1/readyz")"
jq -e '.status == "ok"' <<<"$HEALTH_JSON" >/dev/null
jq -e '.status == "ready" and .store == "postgres"' <<<"$READY_JSON" >/dev/null

gcloud run services update-traffic "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --to-tags=candidate=100

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
LATEST_REVISION="$(gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.latestReadyRevisionName)')"
echo "Lotus revision ${LATEST_REVISION} is serving 100% of traffic."
echo "Lotus URL: ${SERVICE_URL}"
echo "Health check: ${SERVICE_URL}/v1/healthz"
