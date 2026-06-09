#!/bin/sh
set -e

# Start Python FastAPI social OAuth backend on port 8000
cd /app
uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level warning &
PYTHON_PID=$!

# Start Node.js main server on port 7860
node src/index.js &
NODE_PID=$!

# Forward signals to both child processes
_term() {
  kill -TERM "$PYTHON_PID" 2>/dev/null || true
  kill -TERM "$NODE_PID"   2>/dev/null || true
}
trap _term TERM INT

wait "$NODE_PID"
wait "$PYTHON_PID"
