#!/bin/bash
# CAINE — cloud AI (Groq + Gemini), public access
# Faster responses. Uses API keys from config.py.
cd "$(dirname "$0")"

if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /tmp/cloudflared && chmod +x /tmp/cloudflared && sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

pkill -f "python3 server.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 0.5

CAINE_BACKEND=cloud python3 server.py > /tmp/caine.log 2>&1 &
SERVER_PID=$!

echo "Starting CAINE (cloud mode)..."
for i in $(seq 1 30); do
  sleep 0.4
  curl -s http://localhost:5000 > /dev/null 2>&1 && break
done

cloudflared tunnel --url http://localhost:5000 2>&1 | \
  awk '/trycloudflare\.com/{
    match($0, /https:\/\/[a-z0-9-]+\.trycloudflare\.com/)
    url = substr($0, RSTART, RLENGTH)
    print ""
    print "  ╔══════════════════════════════════════════════╗"
    print "  ║  CAINE  —  cloud AI  —  public access       ║"
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
