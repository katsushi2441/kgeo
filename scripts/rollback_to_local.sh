#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Restart so the fallback process reloads the current Heteml storage settings.
systemctl --user restart kgeo.service
.venv/bin/python scripts/set_api_endpoint.py http://exbridge.ddns.net:18308
scripts/deploy.sh
echo "KGeo PHP gateway rolled back to the local API."
