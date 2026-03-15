#!/usr/bin/env bash
#
# Starts both the backend API and frontend dev server.
# Scans for available ports and increments if something's already listening.
#
# Usage:
#   ./start.sh                  # backend=8000, frontend=5173 (or next available)
#   ./start.sh 9000 3000        # try these ports first instead
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Dependency check ───────────────────────────────────────────────────────
# Make sure the Python that runs this has everything it needs.

check_deps() {
  local missing=()
  for mod in pysam yaml fastapi uvicorn; do
    if ! python3 -c "import $mod" 2>/dev/null; then
      missing+=("$mod")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    echo "Missing Python packages: ${missing[*]}"
    echo "Installing..."
    pip3 install pysam pyyaml fastapi uvicorn 2>&1 | tail -3
    echo ""
  fi

  if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    echo "Frontend dependencies not installed. Running npm install..."
    (cd "$SCRIPT_DIR/frontend" && npm install) 2>&1 | tail -3
    echo ""
  fi
}

check_deps

# ─── Port finder ─────────────────────────────────────────────────────────────

find_open_port() {
  local port="$1"
  local max_attempts=20
  local attempt=0

  while (( attempt < max_attempts )); do
    if ! lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$port"
      return 0
    fi
    echo "  Port $port is busy, trying $((port + 1))..." >&2
    port=$((port + 1))
    attempt=$((attempt + 1))
  done

  echo "ERROR: Could not find an open port after $max_attempts attempts (started at $1)" >&2
  return 1
}

# ─── Cleanup on exit ────────────────────────────────────────────────────────

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null && echo "  Backend stopped."
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Frontend stopped."
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# ─── Find ports ──────────────────────────────────────────────────────────────

BACKEND_PORT_HINT="${1:-8000}"
FRONTEND_PORT_HINT="${2:-5173}"

echo "Finding available ports..."

BACKEND_PORT=$(find_open_port "$BACKEND_PORT_HINT")
FRONTEND_PORT=$(find_open_port "$FRONTEND_PORT_HINT")

echo ""
echo "  Backend  → http://localhost:$BACKEND_PORT"
echo "  Frontend → http://localhost:$FRONTEND_PORT"
echo ""

# ─── Start backend ───────────────────────────────────────────────────────────
# Use python3 -m uvicorn so it runs under the same Python where pysam lives,
# rather than whichever uvicorn binary happens to be first in PATH.

echo "Starting backend..."
cd "$SCRIPT_DIR"
python3 -m uvicorn backend.app:app \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" \
  --reload \
  --log-level info &
BACKEND_PID=$!

# Give uvicorn a moment to bind
sleep 1

# ─── Start frontend ─────────────────────────────────────────────────────────

echo "Starting frontend..."
cd "$SCRIPT_DIR/frontend"
BACKEND_PORT="$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!

# ─── Wait ────────────────────────────────────────────────────────────────────

echo ""
echo "Both servers running. Open http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop."
echo ""

wait
