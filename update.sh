#!/usr/bin/env bash
# Update ProDR_Writer from git and restart if it was running.
#
# Order matters: the pull happens BEFORE stopping anything, so a failed pull
# (local changes, network down) never leaves a previously running service down.
set -e
cd "$(dirname "$0")"

proc_cmdline() {
    if [ -r "/proc/$1/cmdline" ]; then tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null
    else ps -p "$1" -o args= 2>/dev/null; fi
}

looks_like_ours() {
    case "$(proc_cmdline "$1")" in
        *"prodr_writer"*web*) return 0 ;;
        *) return 1 ;;
    esac
}

was_running=0
if [ -f .web.pid ]; then
    PID=$(cat .web.pid 2>/dev/null)
    # Verify the pid really is ours before deciding to restart afterwards.
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null && looks_like_ours "$PID"; then
        was_running=1
    fi
fi

echo "==> Pulling latest code"
if ! git pull --ff-only; then
    echo ""
    echo "[ERROR] git pull failed — your checkout has local changes or cannot reach origin."
    echo "        Nothing was stopped or modified. Resolve with 'git stash' or commit,"
    echo "        then re-run ./update.sh"
    exit 1
fi

echo "==> Reinstalling package"
PIP_ARGS="-e ."
# Mirror install.sh: keep the old-glibc compatibility constraints if they were
# applied at install time.
if [ -f requirements-oldglibc.txt ] && [ "$(uname -s)" = "Linux" ] && command -v ldd >/dev/null 2>&1; then
    GLIBC_VER="$(ldd --version 2>/dev/null | awk 'NR==1{print $NF}')"
    GLIBC_MAJOR="${GLIBC_VER%%.*}"
    GLIBC_MINOR="${GLIBC_VER#*.}"
    if [ "${GLIBC_MAJOR:-0}" -lt 2 ] || { [ "$GLIBC_MAJOR" = "2" ] && [ "${GLIBC_MINOR:-99}" -lt 28 ]; }; then
        PIP_ARGS="-c requirements-oldglibc.txt -e ."
    fi
fi
# shellcheck disable=SC2086
.venv/bin/pip install $PIP_ARGS -q

if [ $was_running -eq 1 ]; then
    ./stop.sh
    exec ./start.sh
else
    echo "✔ Update complete. Start with ./start.sh"
fi
