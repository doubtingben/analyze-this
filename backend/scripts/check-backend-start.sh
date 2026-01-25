#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

# 1. Environment Management
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing/Updating requirements..."
pip install -r requirements.txt

# 2. Random Port Selection
# Try finding an open port using python
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
HOST=${HOST:-127.0.0.1}

echo "Selected random port: $PORT"

export APP_ENV=${APP_ENV:-development}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID"
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# 3. Code Verification
echo "Verifying application import..."
if ! python3 -c "from main import app; print('App import successful')"; then
    echo "Failed to import main application. Check your code."
    exit 1
fi

# 4. Server Startup
echo "Starting server on port $PORT..."
python -m uvicorn main:app --app-dir . --host "$HOST" --port "$PORT" --log-level warning &
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
