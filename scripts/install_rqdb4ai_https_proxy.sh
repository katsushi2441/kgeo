#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
target="/etc/nginx/conf.d/exbridge-8012-mcp.conf"
snippet="${project_dir}/deploy/nginx-kgeo-rqdb4ai-location.conf"
begin_marker="    # BEGIN KGEO RQDB4AI HTTPS GATEWAY"
end_marker="    # END KGEO RQDB4AI HTTPS GATEWAY"

if [[ "$EUID" -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 2
fi
if [[ ! -f "$target" || ! -f "$snippet" ]]; then
  echo "Required Nginx configuration is missing." >&2
  exit 2
fi

backup="${target}.bak.$(date +%Y%m%d%H%M%S)"
cp -a "$target" "$backup"
temporary="$(mktemp)"
trap 'rm -f "$temporary"' EXIT

awk -v begin="$begin_marker" -v end="$end_marker" -v snippet="$snippet" '
  BEGIN { in_managed = 0 }
  $0 == begin { in_managed = 1; next }
  $0 == end { in_managed = 0; next }
  !in_managed { lines[++count] = $0 }
  END {
    last = 0
    for (i = 1; i <= count; i++) {
      if (lines[i] == "}") last = i
    }
    if (!last) exit 3
    for (i = 1; i <= count; i++) {
      if (i == last) {
        print begin
        while ((getline line < snippet) > 0) print line
        close(snippet)
        print end
      }
      print lines[i]
    }
  }
' "$target" >"$temporary"

install -o root -g root -m 0644 "$temporary" "$target"
if ! nginx -t; then
  cp -a "$backup" "$target"
  nginx -t
  echo "Nginx validation failed; restored ${backup}." >&2
  exit 1
fi
systemctl reload nginx

curl --fail --silent --show-error --max-time 15 \
  https://exbridge.ddns.net:8012/kgeo-rqdb4ai/healthz >/dev/null
echo "KGeo RQDB4AI HTTPS gateway installed. Backup: ${backup}"
