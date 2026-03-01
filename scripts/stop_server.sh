#!/usr/bin/env bash
# stop_server.sh – Gracefully stop whichever environment is running
set -euo pipefail
lsof -ti :8000 | xargs kill -9
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo ">>> No PID file found at $PID_FILE. Is the server running?"
  exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
  echo ">>> Stopping server (PID=$PID)..."
  kill -SIGTERM "$PID"
  # Wait up to 10 seconds for graceful shutdown
  for i in $(seq 1 10); do
    sleep 1
    if ! kill -0 "$PID" 2>/dev/null; then
      echo ">>> Server stopped."
      rm -f "$PID_FILE"
      exit 0
    fi
  done
  echo ">>> Graceful shutdown timed out. Sending SIGKILL..."
  kill -SIGKILL "$PID" || true
  rm -f "$PID_FILE"
else
  echo ">>> PID $PID is not running. Cleaning up stale PID file."
  rm -f "$PID_FILE"
fi
