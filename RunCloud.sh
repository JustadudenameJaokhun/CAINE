#!/bin/bash
# CAINE — cloud mode (Groq + Gemini APIs, no local model needed)
cd "$(dirname "$0")"

pkill -f "python3 server.py" 2>/dev/null

CAINE_BACKEND=cloud python3 server.py &
SERVER_PID=$!

for i in $(seq 1 20); do
  sleep 0.3
  curl -s http://localhost:5000 > /dev/null 2>&1 && break
done

if command -v xdg-open &>/dev/null; then
  xdg-open http://localhost:5000
elif command -v open &>/dev/null; then
  open http://localhost:5000
fi

echo "CAINE (cloud) — http://localhost:5000  |  Ctrl+C to stop"
wait $SERVER_PID
