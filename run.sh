#!/usr/bin/env bash
# run.sh — Start PriSm (FastAPI + Streamlit) in one terminal
# Usage: bash run.sh

set -e

echo "🔷 PriSm — starting servers..."
echo ""

echo "⚙️  Starting FastAPI backend on http://localhost:8000 ..."
uv run uvicorn api:app --reload --port 8000 &
API_PID=$!

sleep 2  # give uvicorn a moment to bind

echo "🖥️  Starting Streamlit frontend on http://localhost:8501 ..."
uv run streamlit run app.py --server.port 8501 &
ST_PID=$!

echo ""
echo "✅ PriSm is running."
echo "   API docs  : http://localhost:8000/docs"
echo "   App UI    : http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $API_PID $ST_PID 2>/dev/null; echo 'PriSm stopped.'" EXIT
wait