#!/usr/bin/env bash
# Start the ProDR_Writer web UI in the background
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "[ERROR] Not installed yet — run ./install.sh first."; exit 1; fi
if [ -f .web.pid ] && kill -0 "$(cat .web.pid)" 2>/dev/null; then
    echo "Already running (PID $(cat .web.pid)). Use ./stop.sh first."
    exit 0
fi
# 127.0.0.1 by default: the web UI has no authentication and can read/write
# the stored LLM API key config — only expose it on your LAN deliberately.
HOST=${PRODR_HOST:-127.0.0.1}
PORT=${PRODR_PORT:-8000}
nohup .venv/bin/python -m prodr_writer web --host "$HOST" --port "$PORT" > prodr-web.log 2>&1 &
echo $! > .web.pid
sleep 2
if kill -0 "$(cat .web.pid)" 2>/dev/null; then
    echo "✔ Started (PID $(cat .web.pid)): http://$HOST:$PORT  (log: prodr-web.log)"
else
    echo "[ERROR] Failed to start — see prodr-web.log:"; tail -20 prodr-web.log; exit 1
fi
