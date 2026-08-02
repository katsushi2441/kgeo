#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
. /home/kojima/work/aixec/.env
set +a

remote="/web/kurage_exbridge_jp"
upload() {
  local source_file="$1"
  local remote_file="$2"
  curl --fail --silent --show-error --ftp-create-dirs -T "$source_file" \
    "ftp://${FTP_USER}:${FTP_PASS}@${FTP_HOST}${remote}/${remote_file}"
  echo "deployed: ${remote_file}"
}

upload public/kgeo.php kgeo.php
upload public/kgeo_billing.php kgeo_billing.php
upload public/kgeo_data/.htaccess kgeo_data/.htaccess
upload static/index.html kgeo_app.html
upload static/styles.css assets/kgeo.css
upload static/app.js assets/kgeo.js
upload static/images/kgeo-ogp.png images/kgeo-ogp.png
if [[ -f public/kgeo_config.php ]]; then
  upload public/kgeo_config.php kgeo_config.php
else
  echo "missing public/kgeo_config.php; run scripts/configure_runtime.py first" >&2
  exit 1
fi

echo "published: https://kurage.exbridge.jp/kgeo.php"
