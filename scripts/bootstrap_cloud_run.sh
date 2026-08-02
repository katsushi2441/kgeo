#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

project="${KGEO_GCP_PROJECT:-dogwood-wharf-469003-n1}"
service_account="${KGEO_CLOUD_RUN_SERVICE_ACCOUNT:-kgeo-cloud-run}"
rqdb_public_url="${KGEO_RQDB4AI_PUBLIC_URL:-https://exbridge.ddns.net:8012/kgeo-rqdb4ai}"

if [[ "$(gcloud billing projects describe "$project" --format='value(billingEnabled)' 2>/dev/null)" != "True" ]]; then
  echo "Cloud Billing is disabled for ${project}. Deployment was not attempted." >&2
  exit 2
fi
if [[ ! "$rqdb_public_url" =~ ^https:// ]]; then
  echo "KGEO_RQDB4AI_PUBLIC_URL must be an HTTPS RQDB4AI endpoint." >&2
  exit 2
fi
curl --fail --silent --show-error --max-time 15 "${rqdb_public_url%/}/healthz" >/dev/null

set -a
. ./.env
set +a
: "${KGEO_INTERNAL_TOKEN:?KGEO_INTERNAL_TOKEN is required in .env}"
: "${KGEO_RQDB4AI_TOKEN:?KGEO_RQDB4AI_TOKEN is required in .env}"
: "${KGEO_STORAGE_API_TOKEN:?KGEO_STORAGE_API_TOKEN is required in .env}"
: "${KGEO_STORAGE_API_URL:?KGEO_STORAGE_API_URL is required in .env}"

deepseek_key="${KGEO_DEEPSEEK_API_KEY:-}"
if [[ -z "$deepseek_key" && -n "${KGEO_DEEPSEEK_API_KEY_FILE:-}" && -f "${KGEO_DEEPSEEK_API_KEY_FILE}" ]]; then
  deepseek_key="$(sed -n "s/^${KGEO_DEEPSEEK_API_KEY_NAME:-DEEPSEEK_API_KEY}=//p" "${KGEO_DEEPSEEK_API_KEY_FILE}" | head -1 | tr -d "'\"")"
fi
: "${deepseek_key:?DeepSeek API key is required}"

gcloud services enable \
  run.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com \
  --project "$project" --quiet

if ! gcloud iam service-accounts describe \
  "${service_account}@${project}.iam.gserviceaccount.com" --project "$project" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$service_account" \
    --display-name="Kurage GEO Cloud Run" --project "$project"
fi

put_secret() {
  local name="$1"
  local value="$2"
  if ! gcloud secrets describe "$name" --project "$project" >/dev/null 2>&1; then
    gcloud secrets create "$name" --replication-policy=automatic --project "$project"
  fi
  printf '%s' "$value" | gcloud secrets versions add "$name" \
    --data-file=- --project "$project" >/dev/null
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${service_account}@${project}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" --project "$project" --quiet >/dev/null
}

put_secret kgeo-internal-token "$KGEO_INTERNAL_TOKEN"
put_secret kgeo-deepseek-api-key "$deepseek_key"
put_secret kgeo-rqdb4ai-token "$KGEO_RQDB4AI_TOKEN"
put_secret kgeo-storage-api-token "$KGEO_STORAGE_API_TOKEN"

echo "Cloud Run prerequisites created for Heteml storage: project=${project}"
echo "Secret values were not printed."
