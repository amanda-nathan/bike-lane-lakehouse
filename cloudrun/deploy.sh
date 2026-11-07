#!/bin/bash
# Deploy the public MCP server to Google Cloud Run. Safe to re-run.
#
# Needs: gcloud signed in (gcloud auth login), a billing account, and the R2_* values in .env.
# Usage: cloudrun/deploy.sh <billing-account-id>      first time
#        cloudrun/deploy.sh                           redeploy
#        SKIP_BUILD=1 cloudrun/deploy.sh              redeploy settings, reuse the last image
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=${PROJECT:-bike-lane-lakehouse}
REGION=${REGION:-us-east1}
SERVICE=bikelake-mcp
REPO=bikelake
IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE
# Settings go in as plain environment variables; credentials go in Secret Manager.
SETTINGS=(R2_CATALOG_URI R2_WAREHOUSE R2_ENDPOINT)
SECRETS=(R2_READ_TOKEN R2_READ_ACCESS_KEY_ID R2_READ_SECRET_ACCESS_KEY MCP_ACCESS_KEY)

set -a; source .env; set +a

# Project and billing
gcloud projects describe "$PROJECT" >/dev/null 2>&1 || gcloud projects create "$PROJECT"
gcloud config set project "$PROJECT" >/dev/null
if [ -n "${1:-}" ]; then
  gcloud billing projects link "$PROJECT" --billing-account "$1" >/dev/null
fi

gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Image registry
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION"
# Keep only the newest image, so storage stays near the free 0.5 GB.
gcloud artifacts repositories set-cleanup-policies "$REPO" --location "$REGION" \
  --policy cloudrun/cleanup-policy.json --no-dry-run >/dev/null

# Credentials as secrets, named lowercase with dashes. A new version is added only when the value changed.
RUNTIME_SA="$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')-compute@developer.gserviceaccount.com"
SECRET_FLAGS=""
for var in "${SECRETS[@]}"; do
  name=$(echo "$var" | tr '[:upper:]_' '[:lower:]-')
  gcloud secrets describe "$name" >/dev/null 2>&1 || gcloud secrets create "$name" --replication-policy automatic >/dev/null
  if [ "$(gcloud secrets versions access latest --secret "$name" 2>/dev/null)" != "${!var}" ]; then
    printf '%s' "${!var}" | gcloud secrets versions add "$name" --data-file - >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$name" --member "serviceAccount:$RUNTIME_SA" \
    --role roles/secretmanager.secretAccessor >/dev/null
  SECRET_FLAGS+="$var=$name:latest,"
done
ENV_FLAGS=""
for var in "${SETTINGS[@]}"; do
  ENV_FLAGS+="$var=${!var}@"
done

# Build in Cloud Build (Cloud Run needs linux/amd64; this Mac is arm64). Same image as space/.
if [ -z "${SKIP_BUILD:-}" ]; then
  gcloud builds submit --config cloudrun/cloudbuild.yaml --substitutions "_IMAGE=$IMAGE" .
fi

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --port 7860 \
  --cpu 2 \
  --memory 4Gi \
  --cpu-boost \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 20 \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars "^@^${ENV_FLAGS%@}" \
  --set-secrets "${SECRET_FLAGS%,}"

# Accept requests addressed to the service's own hostnames only. Cloud Run gives it two.
URLS=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(metadata.annotations."run.googleapis.com/urls")')
HOSTS=$(echo "$URLS" | tr -d '[]" ' | sed 's#https://##g')
URL=$(echo "$URLS" | tr -d '[]" ' | cut -d, -f1)
gcloud run services update "$SERVICE" --region "$REGION" --update-env-vars "^@^MCP_ALLOWED_HOSTS=$HOSTS"

echo "MCP endpoint: $URL/mcp"
echo "Clients must send: Authorization: Bearer <MCP_ACCESS_KEY from .env>"
