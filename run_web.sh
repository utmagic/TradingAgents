#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8005}"
FRONTEND_PORT="${FRONTEND_PORT:-5175}"

cleanup() {
  echo ""
  echo "Shutting down..."
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

cd "$ROOT_DIR"

if [[ ! -x "$ROOT_DIR/venv/bin/python" ]]; then
  echo "Error: venv not found at $ROOT_DIR/venv"
  echo "Create it first, then install dependencies."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/web/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$ROOT_DIR/web/frontend" && npm install)
fi

echo "Starting backend on :$BACKEND_PORT"
"$ROOT_DIR/venv/bin/python" -m uvicorn web.backend.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "Starting frontend on :$FRONTEND_PORT"
(
  cd "$ROOT_DIR/web/frontend"
  VITE_API_BASE="http://localhost:$BACKEND_PORT" npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

echo ""
wait "$BACKEND_PID" "$FRONTEND_PID"
