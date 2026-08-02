#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

project="${KGEO_GCP_PROJECT:-dogwood-wharf-469003-n1}"
region="${KGEO_GCP_REGION:-asia-northeast1}"
service="${KGEO_CLOUD_RUN_SERVICE:-kgeo-api}"
service_account="${KGEO_CLOUD_RUN_SERVICE_ACCOUNT:-kgeo-cloud-run}"
rqdb_public_url="${KGEO_RQDB4AI_PUBLIC_URL:-https://exbridge.ddns.net:8012/kgeo-rqdb4ai}"

set -a
. ./.env
set +a
: "${KGEO_STORAGE_API_URL:?KGEO_STORAGE_API_URL is required}"
: "${KGEO_STORAGE_API_TOKEN:?KGEO_STORAGE_API_TOKEN is required}"

if [[ "$(gcloud billing projects describe "$project" --format='value(billingEnabled)' 2>/dev/null)" != "True" ]]; then
  echo "Cloud Billing is disabled for ${project}. Deployment was not attempted." >&2
  exit 2
fi
if [[ ! "$rqdb_public_url" =~ ^https:// || ! "$KGEO_STORAGE_API_URL" =~ ^https:// ]]; then
  echo "RQDB4AI and Heteml storage endpoints must use HTTPS." >&2
  exit 2
fi
curl --fail --silent --show-error --max-time 15 "${rqdb_public_url%/}/healthz" >/dev/null
.venv/bin/python -c 'from app import remote_store; print(remote_store.call("table_counts"))' >/dev/null

gcloud run deploy "$service" \
  --project "$project" --region "$region" --source . \
  --service-account="${service_account}@${project}.iam.gserviceaccount.com" \
  --execution-environment=gen2 --port=8080 --timeout=600 \
  --cpu=1 --memory=512Mi --concurrency=8 --min=0 --max-instances=2 \
  --ingress=all --allow-unauthenticated --clear-cloudsql-instances \
  --set-env-vars="KGEO_ADMIN_USERS=xb_bittensor,KGEO_STORAGE_API_URL=${KGEO_STORAGE_API_URL},KGEO_RQDB4AI_URL=${rqdb_public_url%/},KGEO_RQDB4AI_FUNCTION=kgeo.jobs.ollama_chat_job,KGEO_RQDB4AI_WAIT_TIMEOUT=300,KGEO_OLLAMA_MODEL=gemma4:12b-it-qat,KGEO_DEEPSEEK_BASE_URL=https://api.deepseek.com,KGEO_DEEPSEEK_MODEL=deepseek-v4-flash,KGEO_FREE_MONITOR_RUNS_PER_MONTH=5,KGEO_MAX_SITES_PER_USER=20" \
  --set-secrets="KGEO_INTERNAL_TOKEN=kgeo-internal-token:latest,KGEO_DEEPSEEK_API_KEY=kgeo-deepseek-api-key:latest,KGEO_RQDB4AI_TOKEN=kgeo-rqdb4ai-token:latest,KGEO_STORAGE_API_TOKEN=kgeo-storage-api-token:latest" \
  --quiet

service_url="$(gcloud run services describe "$service" --region "$region" \
  --project "$project" --format='value(status.url)')"
curl --fail --silent --show-error \
  -H "X-KGeo-Token: ${KGEO_INTERNAL_TOKEN}" -H "X-KGeo-User: xb_bittensor" \
  "${service_url}/health" >/dev/null
curl --fail --silent --show-error \
  -H "X-KGeo-Token: ${KGEO_INTERNAL_TOKEN}" -H "X-KGeo-User: xb_bittensor" \
  "${service_url}/api/sites" >/dev/null

.venv/bin/python scripts/set_api_endpoint.py "$service_url"
scripts/deploy.sh
echo "KGeo Cloud Run deployment completed with Heteml MySQL storage: ${service_url}"
