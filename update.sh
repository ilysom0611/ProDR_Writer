#!/usr/bin/env bash
# Update ProDR_Writer from git and restart if it was running
set -e
cd "$(dirname "$0")"
was_running=0
[ -f .web.pid ] && kill -0 "$(cat .web.pid)" 2>/dev/null && was_running=1
[ $was_running -eq 1 ] && ./stop.sh

echo "==> Pulling latest code"
git pull --ff-only
echo "==> Reinstalling package"
.venv/bin/pip install -e . -q

if [ $was_running -eq 1 ]; then ./start.sh; else echo "✔ Update complete. Start with ./start.sh"; fi
