#!/bin/bash

echo "🔄 Killing any process on port 8000..."
kill -9 $(lsof -ti tcp:8000) 2>/dev/null && echo "✅ Killed old process" || echo "⚠️ No process found on port 8000"

echo "🚀 Starting FastAPI server (correct entrypoint)..."
# Use project root `main:app` as the entrypoint (main.py lives at repo root)
uvicorn main:app --reload --host 127.0.0.1 --port 8000
