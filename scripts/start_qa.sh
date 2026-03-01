#!/usr/bin/env bash
# start_qa.sh – Start the server in QA / staging mode
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$ROOT_DIR/.server.pid"
export APP_ENV=qa

echo ">>> [QA] APP_ENV=$APP_ENV → loading envs/.env.qa"

cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

echo ">>> [QA] Starting uvicorn with 2 workers..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --log-level info &

echo $! > "$PID_FILE"
echo ">>> Server started (PID=$(cat "$PID_FILE")). Stop with: scripts/stop_server.sh"
