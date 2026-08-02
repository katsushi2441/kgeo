#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

project="${KGEO_GCP_PROJECT:-dogwood-wharf-469003-n1}"
region="${KGEO_GCP_REGION:-asia-northeast1}"
instance="${KGEO_CLOUD_SQL_INSTANCE_ID:-kgeo-db}"
database="${KGEO_CLOUD_SQL_DATABASE:-kgeo}"
db_user="${KGEO_CLOUD_SQL_USER:-kgeo}"
service_account="${KGEO_CLOUD_RUN_SERVICE_ACCOUNT:-kgeo-cloud-run}"
rqdb_public_url="${KGEO_RQDB4AI_PUBLIC_URL:-https://exbridge.ddns.net:8012/kgeo-rqdb4ai}"

if [[ "$(gcloud billing projects describe "$project" --format='value(billingEnabled)' 2>/dev/null)" != "True" ]]; then
  echo "Cloud Billing is disabled for ${project}. Link an active billing account first:" >&2
  echo "https://console.cloud.google.com/billing/linkedaccount?project=${project}" >&2
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

deepseek_key="${KGEO_DEEPSEEK_API_KEY:-}"
if [[ -z "$deepseek_key" && -n "${KGEO_DEEPSEEK_API_KEY_FILE:-}" && -f "${KGEO_DEEPSEEK_API_KEY_FILE}" ]]; then
  deepseek_key="$(sed -n "s/^${KGEO_DEEPSEEK_API_KEY_NAME:-DEEPSEEK_API_KEY}=//p" "${KGEO_DEEPSEEK_API_KEY_FILE}" | head -1 | tr -d "'\"")"
fi
: "${deepseek_key:?DeepSeek API key is required}"

gcloud services enable \
  run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com \
  --project "$project" --quiet

if ! gcloud iam service-accounts describe \
  "${service_account}@${project}.iam.gserviceaccount.com" --project "$project" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$service_account" \
    --display-name="Kurage GEO Cloud Run" --project "$project"
fi
gcloud projects add-iam-policy-binding "$project" \
  --member="serviceAccount:${service_account}@${project}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client" --quiet >/dev/null

db_password=""
if gcloud secrets describe kgeo-db-password --project "$project" >/dev/null 2>&1; then
  db_password="$(gcloud secrets versions access latest --secret=kgeo-db-password --project "$project")"
else
  db_password="$(openssl rand -hex 24)"
fi

if ! gcloud sql instances describe "$instance" --project "$project" >/dev/null 2>&1; then
  gcloud sql instances create "$instance" \
    --project "$project" --region "$region" --database-version=POSTGRES_16 \
    --tier=db-f1-micro --storage-size=10 --storage-type=SSD \
    --availability-type=zonal --assign-ip \
    --server-ca-mode=GOOGLE_MANAGED_INTERNAL_CA \
    --root-password="$db_password" --quiet
fi
gcloud sql databases describe "$database" --instance "$instance" --project "$project" \
  >/dev/null 2>&1 || gcloud sql databases create "$database" --instance "$instance" --project "$project"
if gcloud sql users list --instance "$instance" --project "$project" \
  --filter="name=${db_user}" --format='value(name)' | grep -qx "$db_user"; then
  gcloud sql users set-password "$db_user" --instance "$instance" \
    --password="$db_password" --project "$project" --quiet
else
  gcloud sql users create "$db_user" --instance "$instance" \
    --password="$db_password" --project "$project"
fi

connection="$(gcloud sql instances describe "$instance" --project "$project" --format='value(connectionName)')"
database_url="postgresql://${db_user}:${db_password}@/${database}?host=/cloudsql/${connection}"

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

put_secret kgeo-db-password "$db_password"
put_secret kgeo-database-url "$database_url"
put_secret kgeo-internal-token "$KGEO_INTERNAL_TOKEN"
put_secret kgeo-deepseek-api-key "$deepseek_key"
put_secret kgeo-rqdb4ai-token "$KGEO_RQDB4AI_TOKEN"

echo "Cloud Run prerequisites created: project=${project} region=${region} instance=${connection}"
echo "Secret values were not printed."
