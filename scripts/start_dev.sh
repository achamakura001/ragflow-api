#!/usr/bin/env bash
# start_dev.sh – Start the server in development mode
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$ROOT_DIR/.server.pid"
export APP_ENV=dev

echo ">>> [DEV] APP_ENV=$APP_ENV → loading envs/.env.dev"

cd "$ROOT_DIR"

# Activate virtual environment if present
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

echo ">>> [DEV] Starting uvicorn with reload..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level debug &

echo $! > "$PID_FILE"
echo ">>> Server started (PID=$(cat "$PID_FILE")). Stop with: scripts/stop_server.sh"
