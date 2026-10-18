#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/apps/app"
PYTHON="$ROOT_DIR/venv/bin/python"
OLLAMA_MODEL="gemma3:1b"
OLLAMA_PID=""
API_PID=""
WEB_PID=""

cleanup() {
  for pid in "$WEB_PID" "$API_PID" "$OLLAMA_PID"; do
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$WEB_PID" "$API_PID" "$OLLAMA_PID"; do
    if [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found at $ROOT_DIR/venv."
  echo "Create it and install the backend dependencies before running this script."
  exit 1
fi

if ! "$PYTHON" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "Backend dependencies are missing from $ROOT_DIR/venv."
  echo "Install FastAPI and Uvicorn in that environment, then try again."
  exit 1
fi

if [[ ! -x "$APP_DIR/node_modules/.bin/next" ]]; then
  echo "Frontend dependencies are missing."
  echo "Run 'npm install' from $APP_DIR, then try again."
  exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed or is not on PATH. Install Ollama, then try again."
  exit 1
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting the local Ollama server..."
  ollama serve >/tmp/zeroday-ps2-ollama.log 2>&1 &
  OLLAMA_PID=$!

  for _ in {1..30}; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
      echo "Ollama failed to start. Check /tmp/zeroday-ps2-ollama.log."
      exit 1
    fi
    sleep 1
  done

  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama did not become ready. Check /tmp/zeroday-ps2-ollama.log."
    exit 1
  fi
fi

if ! ollama list | awk 'NR > 1 { print $1 }' | grep -Fxq "$OLLAMA_MODEL"; then
  echo "Downloading Ollama model $OLLAMA_MODEL (this may take a while)..."
  ollama pull "$OLLAMA_MODEL"
fi

if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "Backend is already using port 8000. Stop it before running this script."
  exit 1
fi

export OLLAMA_MODEL
(
  cd "$ROOT_DIR"
  exec "$PYTHON" -m uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000
) &
API_PID=$!

(
  cd "$APP_DIR"
  exec "$APP_DIR/node_modules/.bin/next" dev --port 3000
) &
WEB_PID=$!

echo "Starting ZeroDay PS2..."
echo "Website: http://localhost:3000"
echo "Backend: http://127.0.0.1:8000/health"
echo "Press Ctrl+C to stop the services."

wait "$WEB_PID"
