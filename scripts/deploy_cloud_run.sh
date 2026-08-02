#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

project="${KGEO_GCP_PROJECT:-dogwood-wharf-469003-n1}"
region="${KGEO_GCP_REGION:-asia-northeast1}"
service="${KGEO_CLOUD_RUN_SERVICE:-kgeo-api}"
instance="${KGEO_CLOUD_SQL_INSTANCE_ID:-kgeo-db}"
database="${KGEO_CLOUD_SQL_DATABASE:-kgeo}"
db_user="${KGEO_CLOUD_SQL_USER:-kgeo}"
service_account="${KGEO_CLOUD_RUN_SERVICE_ACCOUNT:-kgeo-cloud-run}"
rqdb_public_url="${KGEO_RQDB4AI_PUBLIC_URL:-}"

if [[ "$(gcloud billing projects describe "$project" --format='value(billingEnabled)' 2>/dev/null)" != "True" ]]; then
  echo "Cloud Billing is disabled for ${project}. Deployment was not attempted." >&2
  echo "https://console.cloud.google.com/billing/linkedaccount?project=${project}" >&2
  exit 2
fi
if [[ ! "$rqdb_public_url" =~ ^https:// ]]; then
  echo "KGEO_RQDB4AI_PUBLIC_URL must be an HTTPS RQDB4AI endpoint." >&2
  exit 2
fi
curl --fail --silent --show-error --max-time 15 "${rqdb_public_url%/}/healthz" >/dev/null

connection="$(gcloud sql instances describe "$instance" --project "$project" --format='value(connectionName)')"

gcloud run deploy "$service" \
  --project "$project" --region "$region" --source . \
  --service-account="${service_account}@${project}.iam.gserviceaccount.com" \
  --execution-environment=gen2 --port=8080 --timeout=600 \
  --cpu=1 --memory=512Mi --concurrency=8 --min=0 --max-instances=2 \
  --ingress=all --allow-unauthenticated \
  --add-cloudsql-instances="$connection" \
  --set-env-vars="KGEO_ADMIN_USERS=xb_bittensor,KGEO_RQDB4AI_URL=${rqdb_public_url%/},KGEO_RQDB4AI_FUNCTION=kgeo.jobs.ollama_chat_job,KGEO_RQDB4AI_WAIT_TIMEOUT=300,KGEO_OLLAMA_MODEL=gemma4:12b-it-qat,KGEO_DEEPSEEK_BASE_URL=https://api.deepseek.com,KGEO_DEEPSEEK_MODEL=deepseek-v4-flash,KGEO_FREE_MONITOR_RUNS_PER_MONTH=5,KGEO_MAX_SITES_PER_USER=20" \
  --set-secrets="KGEO_DATABASE_URL=kgeo-database-url:latest,KGEO_INTERNAL_TOKEN=kgeo-internal-token:latest,KGEO_DEEPSEEK_API_KEY=kgeo-deepseek-api-key:latest,KGEO_RQDB4AI_TOKEN=kgeo-rqdb4ai-token:latest" \
  --quiet

db_password="$(gcloud secrets versions access latest --secret=kgeo-db-password --project "$project")"
KGEO_CLOUD_SQL_INSTANCE="$connection" \
KGEO_CLOUD_SQL_DATABASE="$database" \
KGEO_CLOUD_SQL_USER="$db_user" \
KGEO_CLOUD_SQL_PASSWORD="$db_password" \
  .venv/bin/python scripts/migrate_sqlite_to_cloud_sql.py
unset db_password KGEO_CLOUD_SQL_PASSWORD

service_url="$(gcloud run services describe "$service" --region "$region" \
  --project "$project" --format='value(status.url)')"
set -a
. ./.env
set +a
curl --fail --silent --show-error \
  -H "X-KGeo-Token: ${KGEO_INTERNAL_TOKEN}" -H "X-KGeo-User: cloud-run-smoke" \
  "${service_url}/health" >/dev/null

.venv/bin/python scripts/set_api_endpoint.py "$service_url"
scripts/deploy.sh
echo "KGeo Cloud Run migration completed and PHP gateway switched: ${service_url}"
