#!/usr/bin/env bash
# ProDR_Writer one-click installer (Linux/macOS)
set -e
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[ERROR] Python 3.10+ is required (tried: $PY). Set PYTHON=/path/to/python3 to override."
    exit 1
fi

echo "==> Creating virtual environment (.venv)"
"$PY" -m venv .venv

echo "==> Installing ProDR_Writer and dependencies"
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -e . -q

echo ""
echo "✔ Installation complete."
echo "  Start:   ./start.sh      (web UI, default http://0.0.0.0:8000)"
echo "  Stop:    ./stop.sh"
echo "  Update:  ./update.sh"
echo "  CLI:     .venv/bin/prodr-writer --help"
