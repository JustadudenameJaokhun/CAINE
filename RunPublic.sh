#!/bin/bash
# CAINE — fully local, publicly accessible
#
# What this does:
#   1. Starts Ollama (local AI, free, no API keys)
#   2. Starts CAINE on your machine
#   3. Opens a Cloudflare tunnel so anyone can reach it
#
# Cost: $0. Everything runs on your machine.
# Your public URL prints below after startup.

cd "$(dirname "$0")"

# ── install cloudflared if missing ─────────────────────────────
if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /tmp/cloudflared
  chmod +x /tmp/cloudflared
  sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

# ── check Ollama ───────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

# ── start Ollama service if not running ────────────────────────
if ! pgrep -x ollama > /dev/null; then
  echo "Starting Ollama..."
  ollama serve > /dev/null 2>&1 &
  sleep 3
fi

# ── pull model if not downloaded ───────────────────────────────
if ! ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
  echo "Pulling llama3.2:3b — one time only (~2GB)..."
  ollama pull llama3.2:3b
fi

# ── kill previous CAINE instance ───────────────────────────────
pkill -f "python3 server.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1

# ── start CAINE in local mode (Ollama only, zero API calls) ────
CAINE_BACKEND=local python3 server.py > /tmp/caine.log 2>&1 &
SERVER_PID=$!

echo "Starting CAINE..."
for i in $(seq 1 30); do
  sleep 0.4
  curl -s http://localhost:5000 > /dev/null 2>&1 && break
done

echo ""
echo "  CAINE is online locally."
echo "  Opening public tunnel..."
echo ""

# ── Cloudflare tunnel ──────────────────────────────────────────
# Suppress all the log noise — just show the URL
cloudflared tunnel --url http://localhost:5000 2>&1 | grep -E "(trycloudflare|Your quick Tunnel)" | while read line; do
  url=$(echo "$line" | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com')
  if [ -n "$url" ]; then
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  CAINE is live at:                          │"
    echo "  │  $url"
    echo "  └─────────────────────────────────────────────┘"
    echo ""
    echo "  Open that URL on any device, anywhere."
    echo "  Ctrl+C to stop."
    echo ""
  fi
done &

# keep tunnel running in foreground (clean exit on Ctrl+C)
cloudflared tunnel --url http://localhost:5000 > /dev/null 2>&1

kill $SERVER_PID 2>/dev/null
pkill -x ollama 2>/dev/null
