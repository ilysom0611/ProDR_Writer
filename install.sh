#!/usr/bin/env bash
# ProDR_Writer one-command installer (Linux/macOS).
#
# Works three ways:
#   1. curl -fsSL <raw-install.sh-url> | bash     # downloads, installs, ready to start
#   2. ./install.sh                                # inside an existing checkout
#   3. PRODR_DEST=/opt/prodr bash install.sh       # choose where the checkout lands (mode 1)
set -e

REPO_URL="https://github.com/ilysom0611/ProDR_Writer"
SRC_TGZ="$REPO_URL/archive/refs/heads/main.tar.gz"

if [ -f pyproject.toml ] && [ -d src/prodr_writer ]; then
    # Already inside a checkout (cloned or downloaded archive) — install in place.
    cd "$(dirname "$0")"
else
    # Bootstrapping from nothing (typical when piped via curl): fetch the source.
    DEST="${PRODR_DEST:-$PWD/ProDR_Writer}"
    echo "==> Downloading ProDR_Writer into $DEST"
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 "$REPO_URL.git" "$DEST"
    elif command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
        mkdir -p "$DEST"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "$SRC_TGZ" | tar -xz -C "$DEST" --strip-components=1
        else
            wget -qO- "$SRC_TGZ" | tar -xz -C "$DEST" --strip-components=1
        fi
    else
        echo "[ERROR] Need either 'git' or 'curl'/'wget'+'tar' to download the source." >&2
        exit 1
    fi
    cd "$DEST"
fi

PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[ERROR] Python 3.10+ is required (tried: $PY). Set PYTHON=/path/to/python3 to override."
    exit 1
fi

if ! "$PY" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>/dev/null; then
    echo "[ERROR] Python 3.10+ is required. Found: $("$PY" --version 2>&1)"
    exit 1
fi

echo "==> Creating virtual environment (.venv)"
"$PY" -m venv .venv

echo "==> Installing ProDR_Writer and dependencies"
# Tolerate a transient network failure during the pip self-upgrade — it is
# optional and must not abort the whole install.
.venv/bin/pip install --upgrade pip -q || true
.venv/bin/pip install -e . -q

echo ""
echo "✔ Installation complete in $(pwd)"
echo "  Start:   cd $(pwd) && ./start.sh      (web UI on this host's LAN address)"
echo "  Stop:    ./stop.sh"
echo "  Update:  ./update.sh"
echo "  CLI:     .venv/bin/prodr-writer --help"
