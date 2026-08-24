#!/usr/bin/env bash
# Start the ProDR_Writer web UI in the background
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "[ERROR] Not installed yet — run ./install.sh first."; exit 1; fi

HOST=${PRODR_HOST:-127.0.0.1}
PORT=${PRODR_PORT:-8000}
# server.py derives its Host allowlist / token requirement from this env var,
# so keep it in sync with the address uvicorn actually binds (see cli.py).
export PRODR_WEB_HOST="$HOST"

proc_cmdline() {
    # Linux: /proc; macOS/BSD fallback: ps
    if [ -r "/proc/$1/cmdline" ]; then tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null
    else ps -p "$1" -o args= 2>/dev/null; fi
}

looks_like_ours() {
    case "$(proc_cmdline "$1")" in
        *"prodr_writer"*web*) return 0 ;;
        *) return 1 ;;
    esac
}

if [ -f .web.pid ]; then
    OLD=$(cat .web.pid 2>/dev/null)
    if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
        if looks_like_ours "$OLD"; then
            echo "Already running (PID $OLD). Use ./stop.sh first."
            exit 0
        fi
        echo "Replacing stale .web.pid (PID $OLD is not ProDR_Writer)."
    fi
    rm -f .web.pid
fi

# 127.0.0.1 by default: the web UI can read/write the stored LLM API key
# config — only expose it on your LAN deliberately (PRODR_WEB_TOKEN is then
# required by the server).
nohup .venv/bin/python -m prodr_writer web --host "$HOST" --port "$PORT" > prodr-web.log 2>&1 &
echo $! > .web.pid
sleep 2
PID=$(cat .web.pid)
if kill -0 "$PID" 2>/dev/null && looks_like_ours "$PID"; then
    echo "✔ Started (PID $PID): http://$HOST:$PORT  (log: prodr-web.log)"
else
    rm -f .web.pid
    echo "[ERROR] Failed to start — see prodr-web.log:"; tail -20 prodr-web.log; exit 1
fi
