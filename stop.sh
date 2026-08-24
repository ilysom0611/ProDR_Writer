#!/usr/bin/env bash
# Stop the ProDR_Writer web UI
cd "$(dirname "$0")"

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

stopped=0
if [ -f .web.pid ]; then
    PID=$(cat .web.pid 2>/dev/null)
    # Only trust the pidfile if the process is alive AND is really ours.
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        if looks_like_ours "$PID"; then
            kill "$PID" && echo "✔ Stopped (PID $PID)"
            stopped=1
        else
            echo "Ignoring stale .web.pid (PID $PID is not ProDR_Writer)."
        fi
    fi
    rm -f .web.pid
fi

# Fallback: match the exact module invocation, then double-check each hit so we
# never kill an unrelated process that merely mentions "prodr_writer".
if [ $stopped -eq 0 ]; then
    for pid in $(pgrep -f -- "-m prodr_writer web"); do
        case "$(proc_cmdline "$pid")" in
            *"prodr_writer"*web*) kill "$pid"; stopped=1 ;;
        esac
    done
    [ $stopped -eq 1 ] && echo "✔ Stopped matching processes"
fi

[ $stopped -eq 0 ] && echo "Not running."
