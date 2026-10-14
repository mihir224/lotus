#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-builder-hackthon-vys}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-lotus}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-lotus-runtime}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-lotus-build}"

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

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  --project "$PROJECT_ID"

SERVICE_ACCOUNT_EMAIL="${RUNTIME_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUNTIME_SERVICE_ACCOUNT" \
    --display-name="Lotus Cloud Run runtime" \
    --project "$PROJECT_ID"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null

BUILD_SERVICE_ACCOUNT_EMAIL="${BUILD_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$BUILD_SERVICE_ACCOUNT_EMAIL" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$BUILD_SERVICE_ACCOUNT" \
    --display-name="Lotus Cloud Run source builder" \
    --project "$PROJECT_ID"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.builder" \
  --condition=None >/dev/null

ENV_VARS="^|^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}|GOOGLE_CLOUD_LOCATION=global|EMBEDDING_LOCATION=global|GOOGLE_GENAI_USE_ENTERPRISE=true|GOOGLE_GENAI_USE_VERTEXAI=false|RUNTIME_MODE=agent_platform|STORE_BACKEND=memory|AUTH_MODE=google|GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}|ALLOWED_GOOGLE_EMAILS=${ALLOWED_GOOGLE_EMAILS:-}|ALLOWED_GOOGLE_DOMAINS=${ALLOWED_GOOGLE_DOMAINS:-}|AGENT_RATE_LIMIT_REQUESTS=${AGENT_RATE_LIMIT_REQUESTS:-10}|AGENT_RATE_LIMIT_WINDOW_SECONDS=${AGENT_RATE_LIMIT_WINDOW_SECONDS:-300}"

gcloud run deploy "$SERVICE_NAME" \
  --source=. \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --service-account="$SERVICE_ACCOUNT_EMAIL" \
  --build-service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SERVICE_ACCOUNT_EMAIL}" \
  --allow-unauthenticated \
  --cpu=1 \
  --memory=1Gi \
  --concurrency=10 \
  --min-instances=0 \
  --max-instances=1 \
  --timeout=300 \
  --set-env-vars="$ENV_VARS"

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)')"

echo
echo "Lotus URL: ${SERVICE_URL}"
echo "Add this exact origin to the OAuth client's Authorized JavaScript origins."
echo "Health check: ${SERVICE_URL}/v1/healthz"
