#!/usr/bin/env bash
# Retake the docs/screenshots that show task lists (README, GUIDE, and the somaari.in detail page,
# which downloads the theme-*.png files). Not run by tests or CI; run it by hand after a UI change.
#
# Runs a throwaway copy of app/ and web/ with AI off and the demo seed moved to the week of
# 12 Oct 2026; the browser clock is fixed at Wed 14 Oct, so every run gives the same pictures.
#
#   scripts/screenshots/take.sh            # writes into docs/screenshots/
# Env: OUT_DIR, PY (python with the app's deps), PW_PY (python with playwright; default uses
# `uv run --with playwright`, which installs nothing into the project), CHROMIUM, PORT.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd -- "$HERE/../.." && pwd -P)"
OUT_DIR="${OUT_DIR:-$REPO/docs/screenshots}"
PY="${PY:-$REPO/.venv/bin/python}"
PORT="${PORT:-8791}"
# Playwright's own browser is often not downloaded on the Pi; use the system one when it is there.
[[ -z "${CHROMIUM:-}" && -x /usr/bin/chromium ]] && export CHROMIUM=/usr/bin/chromium

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

# Seed, then move every date one week on (seed week 5 Oct -> 12 Oct).
(cd "$COPY" && "$PY" - <<'EOF'
from datetime import date, datetime, timedelta
from app.db import connect
from app.seed import seed
db = "data/somaari.db"
seed(db)
wk = timedelta(days=7)
conn = connect(db)
for i, due, created, closed in conn.execute("SELECT id, due_date, created_at, closed_at FROM tasks").fetchall():
    shift = lambda s: (datetime.fromisoformat(s) + wk).isoformat(timespec="minutes") if s else None
    conn.execute("UPDATE tasks SET due_date=?, created_at=?, closed_at=? WHERE id=?",
                 ((date.fromisoformat(due) + wk).isoformat(), shift(created), shift(closed), i))
conn.commit()
EOF
)

(cd "$COPY" && SOMAARI_CONFIG="$COPY/config.toml" TZ=Asia/Kolkata exec "$PY" -m app >"$COPY/server.log" 2>&1) &
SERVER_PID=$!
for ((i = 0; i < 60; i++)); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.25; done
curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null || { cat "$COPY/server.log" >&2; exit 1; }

if [[ -n "${PW_PY:-}" ]]; then
  "$PW_PY" "$HERE/take.py" "http://127.0.0.1:$PORT/" "$OUT_DIR"
else
  uv run --no-project --with playwright python "$HERE/take.py" "http://127.0.0.1:$PORT/" "$OUT_DIR"
fi
