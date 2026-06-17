#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/frontend"

echo "==> Starting Eidon"

# Backend
echo "==> Starting backend (port 8000)..."
cd "$BACKEND"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "    Created .env from .env.example — edit it to add API keys"
fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend
echo "==> Starting frontend (port 5173)..."
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
  echo "    Installing frontend dependencies..."
  npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop"

cleanup() {
  echo "Stopping..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

wait
