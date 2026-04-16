#!/bin/bash
cd "$(dirname "$0")"

# kill any previous instance
pkill -f "python3 server.py" 2>/dev/null

# start server
python3 server.py &
SERVER_PID=$!

# wait for server to be ready
for i in $(seq 1 20); do
  sleep 0.3
  if curl -s http://localhost:5000 > /dev/null 2>&1; then
    break
  fi
done

# open browser
if command -v xdg-open &>/dev/null; then
  xdg-open http://localhost:5000
elif command -v open &>/dev/null; then
  open http://localhost:5000
fi

echo "CAINE running at http://localhost:5000  (Ctrl+C to stop)"
wait $SERVER_PID
