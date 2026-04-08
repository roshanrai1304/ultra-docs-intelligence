#!/usr/bin/env bash
set -e

PORT=8000

# Kill any stale process on the port first
if lsof -ti :$PORT &>/dev/null; then
  echo "Killing stale process on port $PORT..."
  lsof -ti :$PORT | xargs kill -9
  sleep 1
fi

echo "Starting backend on port $PORT..."
source .venv/bin/activate
uvicorn backend.main:app --port $PORT --log-level warning
