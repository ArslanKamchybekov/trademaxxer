#!/usr/bin/env bash
#
# Launch all trademaxxer services in one shot.
#
# Usage:
#   ./start.sh           # live mode: Redis + DBNews + Modal NLI agents
#   ./start.sh --mock    # mock mode: fake news + fake agents (no Redis/Modal)
#
# Ctrl-C stops everything.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:---mock}"

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

# ── Redis (live mode only) ──────────────────────────────
PID_REDIS=""
if [ "$MODE" != "--mock" ]; then
    echo "[1/3] Starting Redis..."
    redis-server --daemonize no --loglevel warning &
    PID_REDIS=$!
    sleep 0.5
    echo "       Redis PID=$PID_REDIS"
else
    echo "[1/3] Skipping Redis (mock mode)"
fi

# ── Server ──────────────────────────────────────────────
echo "[2/3] Starting server ($MODE)..."
cd "$ROOT/server"
source .venv/bin/activate
python3 main.py $MODE &
PID_SERVER=$!
echo "       Server PID=$PID_SERVER"

# ── Frontend ────────────────────────────────────────────
echo "[3/3] Starting frontend..."
cd "$ROOT/client/client"
npm run dev -- --host &
PID_CLIENT=$!
echo "       Frontend PID=$PID_CLIENT"

echo ""
echo "══════════════════════════════════════"
echo "  All services running."
echo "  Dashboard: http://localhost:5173"
echo "  Mode:      ${MODE#--}"
echo "  Ctrl-C to stop everything."
echo "══════════════════════════════════════"
echo ""

wait
