#!/bin/bash
# CAINE — local mode (Ollama, no internet required)
cd "$(dirname "$0")"

# check Ollama is installed
if ! command -v ollama &>/dev/null; then
  echo "Ollama not found. Install it first:"
  echo "  curl -fsSL https://ollama.com/install.sh | sh"
  echo "  ollama pull llama3.2:3b"
  exit 1
fi

# start Ollama service if not already running
if ! pgrep -x ollama > /dev/null; then
  echo "Starting Ollama..."
  ollama serve > /dev/null 2>&1 &
  sleep 2
fi

# check model is pulled
if ! ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
  echo "Pulling llama3.2:3b (one-time, ~2GB)..."
  ollama pull llama3.2:3b
fi

pkill -f "python3 server.py" 2>/dev/null

CAINE_BACKEND=local python3 server.py &
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

echo "CAINE (local) — http://localhost:5000  |  Ctrl+C to stop"
wait $SERVER_PID
