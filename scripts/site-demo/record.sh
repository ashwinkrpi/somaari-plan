#!/usr/bin/env bash
# Record the somaari.in demo loop (the "Watch demo" video and poster on the site's card) and encode it
# into OUT_DIR: loop.webm, loop.mp4, poster.webp. The site build downloads them from this repo's
# site-demo branch, where .github/workflows/site-demo.yml puts them; run this by hand only to try it.
#
# Runs a throwaway copy of app/ and web/ with an empty database and AI off (no keys, nothing leaves
# the machine, and the same tasks every run), in the Warm Tactile theme. The sample plan's dates are
# filled in relative to today, so the week view always has tasks.
#
#   scripts/site-demo/record.sh
# Env: OUT_DIR (default /tmp/somaari-plan-site-demo), SITE_DIR (a somaari-site checkout, for its
# scripts/demo/encode.sh), PY (python with the app's deps), PW_PY (python with playwright),
# CHROMIUM (browser binary instead of Playwright's own), PORT.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd -- "$HERE/../.." && pwd -P)"
OUT_DIR="${OUT_DIR:-/tmp/somaari-plan-site-demo}"
SITE_DIR="${SITE_DIR:-$REPO/../somaari-website/somaari-site}"
PY="${PY:-$REPO/.venv/bin/python}"
PW_PY="${PW_PY:-python3}"
PORT="${PORT:-8790}"
[[ -x "$SITE_DIR/scripts/demo/encode.sh" ]] || { echo "no somaari-site checkout at SITE_DIR=$SITE_DIR" >&2; exit 1; }

COPY="$(mktemp -d)"
SERVER_PID=""
cleanup() { [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null; rm -rf "$COPY"; }
trap cleanup EXIT

mkdir -p "$COPY/data" "$OUT_DIR"
cp -a "$REPO/app" "$REPO/web" "$COPY/"
cat >"$COPY/config.toml" <<EOF
[server]
host = "127.0.0.1"
port = $PORT
threads = 4

[ai]
mode = "off"

[ui]
date_format = "dd/mm/yyyy"
EOF
d() { TZ=Asia/Kolkata date -d "+$1 day" '+%a %-d %b'; }
sed -e "s/{D0}/$(d 0)/g" -e "s/{D1}/$(d 1)/g" -e "s/{D2}/$(d 2)/g" -e "s/{D4}/$(d 4)/g" -e "s/{D5}/$(d 5)/g" \
  "$HERE/sample-plan.md.in" >"$COPY/sample-plan.md"

(cd "$COPY" && SOMAARI_CONFIG="$COPY/config.toml" TZ=Asia/Kolkata exec "$PY" -m app >"$COPY/server.log" 2>&1) &
SERVER_PID=$!
for ((i = 0; i < 60; i++)); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null || { cat "$COPY/server.log" >&2; exit 1; }

"$PW_PY" "$HERE/record.py" "http://127.0.0.1:$PORT/?theme=warm-tactile#/new" "$COPY/sample-plan.md" "$COPY/rec"
# shellcheck source=/dev/null
source "$COPY/rec/raw.times"
export SEGMENTS="$START-$END" POSTER_AT="${POSTER_AT:-$(awk -v s="$START" -v e="$END" 'BEGIN { printf "%.2f", e - s - 1.5 }')}"
OUT_DIR="$OUT_DIR" "$SITE_DIR/scripts/demo/encode.sh" "$COPY/rec/raw.webm" somaari-plan
