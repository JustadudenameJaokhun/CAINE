#!/bin/bash
# CAINE — local AI, public access
# Uses Ollama on your machine. Zero API cost. Zero hosting cost.
cd "$(dirname "$0")"

# ── Ollama ─────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! pgrep -x ollama > /dev/null; then
  echo "Starting Ollama..."
  ollama serve > /dev/null 2>&1 &
  sleep 3
fi

if ! ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
  echo "Pulling llama3.2:3b — one time only (~2GB)..."
  ollama pull llama3.2:3b
fi

# ── cloudflared ────────────────────────────────────────────────
if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /tmp/cloudflared && chmod +x /tmp/cloudflared && sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

# ── start CAINE ────────────────────────────────────────────────
pkill -f "python3 server.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 0.5

CAINE_BACKEND=local python3 server.py > /tmp/caine.log 2>&1 &
SERVER_PID=$!

echo "Starting CAINE (local mode)..."
for i in $(seq 1 30); do
  sleep 0.4
  curl -s http://localhost:5000 > /dev/null 2>&1 && break
done

# ── open tunnel & print URL cleanly ───────────────────────────
cloudflared tunnel --url http://localhost:5000 2>&1 | \
  awk '/trycloudflare\.com/{
    match($0, /https:\/\/[a-z0-9-]+\.trycloudflare\.com/)
    url = substr($0, RSTART, RLENGTH)
    print ""
    print "  ╔══════════════════════════════════════════════╗"
    print "  ║  CAINE  —  local AI  —  public access       ║"
    print "  ╠══════════════════════════════════════════════╣"
    print "  ║  " url "  ║"
    print "  ╠══════════════════════════════════════════════╣"
    print "  ║  Home WiFi:  http://localhost:5000           ║"
    print "  ║  Ctrl+C to stop                              ║"
    print "  ╚══════════════════════════════════════════════╝"
    print ""
  }' &

cloudflared tunnel --url http://localhost:5000 > /dev/null 2>&1
kill $SERVER_PID 2>/dev/null
