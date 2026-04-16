#!/bin/bash
# CAINE — public mode via Cloudflare Tunnel
# Runs on YOUR machine. Cloudflare gives it a public HTTPS URL.
# No account, no domain, no cost.
cd "$(dirname "$0")"

# install cloudflared if missing
if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /tmp/cloudflared
  chmod +x /tmp/cloudflared
  sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

# kill previous instances
pkill -f "python3 server.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null

# start CAINE
python3 server.py &
SERVER_PID=$!

# wait for server
for i in $(seq 1 20); do
  sleep 0.3
  curl -s http://localhost:5000 > /dev/null 2>&1 && break
done

echo ""
echo "CAINE is running locally."
echo "Starting Cloudflare tunnel... your public URL will appear below."
echo ""

# start tunnel — prints the public URL
cloudflared tunnel --url http://localhost:5000

# cleanup on exit
kill $SERVER_PID 2>/dev/null
