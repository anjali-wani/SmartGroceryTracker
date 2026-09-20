#!/bin/bash
# =============================================================================
# Smart Grocery Tracker - Backend Server Restart Script
# Restarts the FastAPI uvicorn server on port 8001.
# =============================================================================

set -e

# Resolve repository root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PORT=8001
HOST="127.0.0.1"
LOG_FILE="$PROJECT_ROOT/uvicorn.log"

echo "=========================================================="
echo "  Restarting Smart Grocery Tracker Backend (Port $PORT)"
echo "=========================================================="

# 1. Locate Python / uvicorn in venv
if [ -f "$PROJECT_ROOT/venv/bin/uvicorn" ]; then
    UVICORN_BIN="$PROJECT_ROOT/venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
    UVICORN_BIN="$(command -v uvicorn)"
else
    echo "❌ Error: Could not find uvicorn in $PROJECT_ROOT/venv/bin or system PATH."
    exit 1
fi

# 2. Stop any process running on port 8001 or matching uvicorn app.main:app
echo "🔍 Checking for existing server on port $PORT..."
EXISTING_PIDS=$(lsof -ti :$PORT 2>/dev/null || true)

if [ -n "$EXISTING_PIDS" ]; then
    echo "🛑 Terminating process(es) on port $PORT (PIDs: $EXISTING_PIDS)..."
    for pid in $EXISTING_PIDS; do
        kill -15 "$pid" 2>/dev/null || true
    done

    # Wait up to 5 seconds for process to exit
    for i in {1..5}; do
        if ! lsof -ti :$PORT >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Force kill if still holding port
    REMAINING_PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
    if [ -n "$REMAINING_PIDS" ]; then
        echo "⚠️  Process still lingering; force killing PIDs: $REMAINING_PIDS..."
        for pid in $REMAINING_PIDS; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
    echo "✅ Port $PORT released."
else
    echo "ℹ️  No existing process found listening on port $PORT."
fi

# 3. Start uvicorn server in background
echo "🚀 Starting uvicorn on http://$HOST:$PORT (logging to uvicorn.log)..."
nohup "$UVICORN_BIN" app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --app-dir "$PROJECT_ROOT" \
    --reload > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "   Launched process PID: $NEW_PID"

# 4. Health check wait loop
echo "⏳ Waiting for server to become responsive..."
READY=false
for i in {1..15}; do
    if curl -s -m 1 "http://$HOST:$PORT/" >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 0.5
done

if [ "$READY" = true ]; then
    echo "=========================================================="
    echo "✅ Server restarted successfully and is healthy!"
    echo "   URL      : http://$HOST:$PORT"
    echo "   API Docs : http://$HOST:$PORT/docs"
    echo "   PID      : $NEW_PID"
    echo "   Log File : $LOG_FILE"
    echo "=========================================================="
else
    echo "❌ Server failed to respond within 8 seconds. Showing recent log output:"
    echo "----------------------------------------------------------"
    tail -n 25 "$LOG_FILE" 2>/dev/null || true
    echo "----------------------------------------------------------"
    exit 1
fi
