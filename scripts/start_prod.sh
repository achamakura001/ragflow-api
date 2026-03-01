#!/usr/bin/env bash
# start_prod.sh – Start the server in production mode (gunicorn + uvicorn workers)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$ROOT_DIR/.server.pid"
export APP_ENV=prod

echo ">>> [PROD] APP_ENV=$APP_ENV → loading envs/.env.prod"

cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

echo ">>> [PROD] Starting gunicorn with uvicorn workers..."
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --log-level warning \
  --access-logfile - \
  --error-logfile - \
  --daemon \
  --pid "$PID_FILE"

echo ">>> Server started (PID=$(cat "$PID_FILE")). Stop with: scripts/stop_server.sh"
