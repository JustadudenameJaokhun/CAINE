#!/bin/bash
# CAINE — permanent public URL setup
#
# This creates a NAMED Cloudflare tunnel so your URL never changes.
# Requires a free Cloudflare account (cloudflare.com — no credit card).
#
# After this runs once, use RunPublic.sh normally.

cd "$(dirname "$0")"

if ! command -v cloudflared &>/dev/null; then
  echo "Installing cloudflared..."
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O /tmp/cloudflared
  chmod +x /tmp/cloudflared
  sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
fi

echo ""
echo "Step 1: Log in to Cloudflare (opens browser)"
echo "  → Go to cloudflare.com and create a FREE account first if you haven't"
echo ""
read -p "Press Enter when ready..."
cloudflared tunnel login

echo ""
echo "Step 2: Creating named tunnel 'caine'..."
cloudflared tunnel create caine

echo ""
echo "Step 3: Routing tunnel to your workers.dev subdomain..."
echo "  Your workers.dev subdomain is your Cloudflare account name."
read -p "Enter your Cloudflare account name (e.g. 'james'): " CF_ACCOUNT

cloudflared tunnel route dns caine caine.$CF_ACCOUNT.workers.dev 2>/dev/null || true

# write permanent tunnel config
mkdir -p ~/.cloudflared
TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep caine | awk '{print $1}')

cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: caine.$CF_ACCOUNT.workers.dev
    service: http://localhost:5000
  - service: http_status:404
EOF

echo ""
echo "  ✓ Done. Your permanent URL is:"
echo "    https://caine.$CF_ACCOUNT.workers.dev"
echo ""
echo "  Update RunPublic.sh to use named tunnel:"
echo "    Replace: cloudflared tunnel --url http://localhost:5000"
echo "    With:    cloudflared tunnel run caine"
echo ""
echo "  When you can afford a domain (even \$1/year .xyz),"
echo "  point it at Cloudflare and CAINE gets a real name instantly."
