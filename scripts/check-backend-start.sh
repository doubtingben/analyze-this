#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PORT=${PORT:-8000}
HOST=${HOST:-127.0.0.1}

export APP_ENV=${APP_ENV:-development}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID"
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

pushd "$ROOT_DIR" >/dev/null

python -m uvicorn main:app --app-dir backend --host "$HOST" --port "$PORT" --log-level warning &
SERVER_PID=$!

for attempt in {1..20}; do
  if curl -fsS "http://$HOST:$PORT/" >/dev/null; then
    echo "Backend responded on http://$HOST:$PORT/"
    exit 0
  fi
  sleep 1
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Backend process exited before responding." >&2
    exit 1
  fi
  echo "Waiting for backend to start ($attempt/20)..."
done

echo "Backend did not respond within timeout." >&2
exit 1
