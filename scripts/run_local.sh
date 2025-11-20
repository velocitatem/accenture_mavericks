#!/usr/bin/env bash
set -euo pipefail

# Simple helper to run the Streamlit review cockpit locally without Docker.
# - Boots a Python virtualenv in .venv
# - Installs dependencies from requirements.txt
# - Starts Redis if available (optional caching)
# - Launches Streamlit on the requested port (defaults to 8501)

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3}
PORT=${PORT:-8501}
ADDRESS=${ADDRESS:-0.0.0.0}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[run_local] Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

# Create venv if missing
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Start Redis if present; cache will self-disable if Redis is unavailable.
REDIS_STARTED=0
if command -v redis-server >/dev/null 2>&1; then
  if ! redis-cli ping >/dev/null 2>&1; then
    echo "[run_local] Starting redis-server for caching…"
    redis-server --daemonize yes
    REDIS_STARTED=1
  fi
else
  echo "[run_local] redis-server not found; caching will be disabled automatically."
fi

# Run Streamlit UI
STREAMLIT_PORT_FLAG="--server.port=${PORT}"
STREAMLIT_ADDR_FLAG="--server.address=${ADDRESS}"

export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}

echo "[run_local] Launching Streamlit on ${ADDRESS}:${PORT}"
streamlit run src/app.py "$STREAMLIT_ADDR_FLAG" "$STREAMLIT_PORT_FLAG"

# Cleanup Redis if we started it
if [ "$REDIS_STARTED" -eq 1 ]; then
  echo "[run_local] Shutting down redis-server…"
  redis-cli shutdown || true
fi
