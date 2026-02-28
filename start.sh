#!/usr/bin/env bash
#
# Launch all trademaxxer services in one shot.
#
# Usage:
#   ./start.sh                  # live: Redis + DBNews + Modal NLI agents
#   ./start.sh --mock           # mock: fake news + fake agents (no Redis/Modal)
#   ./start.sh --local          # live: DBNews + local ONNX (no Redis/Modal)
#   ./start.sh --mock --local   # mock news + real local ONNX inference
#
# Ctrl-C stops everything.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

SERVER_ARGS=""
HAS_MOCK=false
HAS_LOCAL=false
for arg in "$@"; do
    case "$arg" in
        --mock)  HAS_MOCK=true;  SERVER_ARGS="$SERVER_ARGS --mock" ;;
        --local) HAS_LOCAL=true; SERVER_ARGS="$SERVER_ARGS --local" ;;
    esac
done
if [ -z "$SERVER_ARGS" ]; then
    SERVER_ARGS="--mock"
    HAS_MOCK=true
fi

cleanup() {
    echo ""
    echo "[trademaxxer] Shutting down all services..."
    kill $PID_SERVER 2>/dev/null
    kill $PID_CLIENT 2>/dev/null
    [ -n "$PID_REDIS" ] && kill $PID_REDIS 2>/dev/null
    wait 2>/dev/null
    echo "[trademaxxer] All services stopped."
}
trap cleanup EXIT INT TERM

echo "╔══════════════════════════════════════╗"
echo "║         T R A D E M A X X E R       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Redis (only needed for live non-local mode) ────────
PID_REDIS=""
if [ "$HAS_MOCK" = false ] && [ "$HAS_LOCAL" = false ]; then
    echo "[1/3] Starting Redis..."
    redis-server --daemonize no --loglevel warning &
    PID_REDIS=$!
    sleep 0.5
    echo "       Redis PID=$PID_REDIS"
else
    echo "[1/3] Skipping Redis (not needed)"
fi

# ── Server ──────────────────────────────────────────────
echo "[2/3] Starting server ($SERVER_ARGS)..."
cd "$ROOT/server"
source .venv/bin/activate
python3 main.py $SERVER_ARGS &
PID_SERVER=$!
echo "       Server PID=$PID_SERVER"

# ── Frontend ────────────────────────────────────────────
echo "[3/3] Starting frontend..."
cd "$ROOT/client/client"
npm run dev -- --host &
PID_CLIENT=$!
echo "       Frontend PID=$PID_CLIENT"

INFER_MODE="modal"
if [ "$HAS_LOCAL" = true ]; then INFER_MODE="local ONNX"; fi
if [ "$HAS_MOCK" = true ] && [ "$HAS_LOCAL" = false ]; then INFER_MODE="mock (random)"; fi

echo ""
echo "══════════════════════════════════════"
echo "  All services running."
echo "  Dashboard: http://localhost:5173"
echo "  Flags:     $SERVER_ARGS"
echo "  Inference: $INFER_MODE"
echo "  Ctrl-C to stop everything."
echo "══════════════════════════════════════"
echo ""

wait
