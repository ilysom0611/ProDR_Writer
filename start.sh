#!/usr/bin/env bash
# Start the ProDR_Writer web UI in the background.
#
# Default: serve the LAN — binds 0.0.0.0, prints this host's LAN URL, and
# auto-generates an access token (persisted to .web-token) because any
# non-loopback bind requires one (the UI can spend your stored LLM API key).
# Loopback-only: PRODR_HOST=127.0.0.1 ./start.sh
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "[ERROR] Not installed yet — run ./install.sh first."; exit 1; fi

HOST=${PRODR_HOST:-0.0.0.0}
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

# Detect the primary LAN address (display only — uvicorn binds HOST).
detect_lan_ip() {
    ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}'
    return 0
}
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$LAN_IP" ] && LAN_IP=$(detect_lan_ip)
[ -z "$LAN_IP" ] && LAN_IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$LAN_IP" ] && LAN_IP="<this-host>"

# Non-loopback binds require a token; generate one on first start and reuse it
# afterwards so the printed URL stays stable across restarts.
DISPLAY_URL="http://$LAN_IP:$PORT"
case "$HOST" in
    localhost|::1|127.*) ;;
    *)
        if [ -z "$PRODR_WEB_TOKEN" ]; then
            if [ -f .web-token ]; then
                PRODR_WEB_TOKEN=$(cat .web-token)
            else
                PRODR_WEB_TOKEN=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(24))")
                printf '%s' "$PRODR_WEB_TOKEN" > .web-token
                chmod 600 .web-token 2>/dev/null || true
            fi
        fi
        export PRODR_WEB_TOKEN
        DISPLAY_URL="$DISPLAY_URL  (access token: $PRODR_WEB_TOKEN)"
        ;;
esac

nohup .venv/bin/python -m prodr_writer web --host "$HOST" --port "$PORT" > prodr-web.log 2>&1 &
echo $! > .web.pid
sleep 2
PID=$(cat .web.pid)
if kill -0 "$PID" 2>/dev/null && looks_like_ours "$PID"; then
    echo "✔ Started (PID $PID)"
    echo "  Local:   http://127.0.0.1:$PORT"
    echo "  Network: $DISPLAY_URL"
    echo "  Log:     prodr-web.log"
else
    rm -f .web.pid
    echo "[ERROR] Failed to start — see prodr-web.log:"; tail -20 prodr-web.log; exit 1
fi
