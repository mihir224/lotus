#!/usr/bin/env bash
set -euo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

PROJECT_ID="${PROJECT_ID:-ai-builder-hackthon-vys}"
REGION="${REGION:-asia-south1}"
INSTANCE_NAME="${INSTANCE_NAME:-lotus-postgres}"
DATABASE_NAME="${DATABASE_NAME:-lotus}"
DATABASE_USER="${DATABASE_USER:-lotus_app}"
DATABASE_SECRET="${DATABASE_SECRET:-lotus-db-password}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-lotus-runtime}"
ARTIFACT_REPOSITORY="${ARTIFACT_REPOSITORY:-lotus}"

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  --project "$PROJECT_ID"

RUNTIME_SERVICE_ACCOUNT_EMAIL="${RUNTIME_SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$RUNTIME_SERVICE_ACCOUNT_EMAIL" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUNTIME_SERVICE_ACCOUNT" \
    --display-name="Lotus Cloud Run runtime" \
    --project "$PROJECT_ID"
fi

if ! gcloud artifacts repositories describe "$ARTIFACT_REPOSITORY" \
  --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$ARTIFACT_REPOSITORY" \
    --repository-format=docker \
    --location "$REGION" \
    --description="Lotus application images" \
    --project "$PROJECT_ID"
fi

if ! gcloud sql instances describe "$INSTANCE_NAME" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud sql instances create "$INSTANCE_NAME" \
    --project "$PROJECT_ID" \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier=db-f1-micro \
    --region="$REGION" \
    --availability-type=zonal \
    --storage-type=SSD \
    --storage-size=10 \
    --no-storage-auto-increase \
    --no-backup \
    --no-final-backup \
    --no-retain-backups-on-delete \
    --no-deletion-protection \
    --assign-ip
fi

if ! gcloud sql databases describe "$DATABASE_NAME" \
  --instance "$INSTANCE_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud sql databases create "$DATABASE_NAME" \
    --instance "$INSTANCE_NAME" \
    --project "$PROJECT_ID"
fi

if ! gcloud secrets describe "$DATABASE_SECRET" \
  --project "$PROJECT_ID" >/dev/null 2>&1; then
  DATABASE_PASSWORD="$(openssl rand -hex 24)"
  printf %s "$DATABASE_PASSWORD" | gcloud secrets create "$DATABASE_SECRET" \
    --replication-policy=automatic \
    --data-file=- \
    --project "$PROJECT_ID"
else
  DATABASE_PASSWORD="$(gcloud secrets versions access latest \
    --secret "$DATABASE_SECRET" --project "$PROJECT_ID")"
fi

if ! gcloud sql users list --instance "$INSTANCE_NAME" --project "$PROJECT_ID" \
  --filter="name=${DATABASE_USER}" --format='value(name)' | grep -qx "$DATABASE_USER"; then
  gcloud sql users create "$DATABASE_USER" \
    --instance "$INSTANCE_NAME" \
    --password "$DATABASE_PASSWORD" \
    --project "$PROJECT_ID"
fi
unset DATABASE_PASSWORD

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT_EMAIL}" \
  --role=roles/cloudsql.client \
  --condition=None >/dev/null
gcloud secrets add-iam-policy-binding "$DATABASE_SECRET" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT_EMAIL}" \
  --role=roles/secretmanager.secretAccessor \
  --project "$PROJECT_ID" >/dev/null

INSTANCE_CONNECTION_NAME="$(gcloud sql instances describe "$INSTANCE_NAME" \
  --project "$PROJECT_ID" --format='value(connectionName)')"
echo "Cloud SQL ready: ${INSTANCE_CONNECTION_NAME}"
echo "Database: ${DATABASE_NAME}; user: ${DATABASE_USER}; secret: ${DATABASE_SECRET}"
