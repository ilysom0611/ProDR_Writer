#!/usr/bin/env bash
# Stop the ProDR_Writer web UI
cd "$(dirname "$0")"
stopped=0
if [ -f .web.pid ]; then
    PID=$(cat .web.pid)
    if kill -0 "$PID" 2>/dev/null; then kill "$PID"; echo "✔ Stopped (PID $PID)"; stopped=1; fi
    rm -f .web.pid
fi
if [ $stopped -eq 0 ] && pkill -f "prodr_writer web" 2>/dev/null; then
    echo "✔ Stopped matching processes"
    stopped=1
fi
[ $stopped -eq 0 ] && echo "Not running."
