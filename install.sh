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

# ---- Locate a usable Python 3.10+ -------------------------------------
python_ok() {
    "$1" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>/dev/null
}

PY=""
if [ -n "$PYTHON" ]; then
    python_ok "$PYTHON" && PY="$PYTHON"
else
    for cand in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && python_ok "$cand"; then
            PY="$cand"
            break
        fi
    done
fi

# ---- No usable Python? Provision a standalone CPython 3.11 -------------
# (CentOS 7 et al. ship 3.6 as the system python; python-build-standalone's
# install_only builds are static enough for glibc >= 2.17.)
if [ -z "$PY" ]; then
    if [ "$(uname -s)" != "Linux" ]; then
        echo "[ERROR] Python 3.10+ is required. Install it, then re-run this script."
        exit 1
    fi
    case "$(uname -m)" in
        x86_64)  PSA_ARCH="x86_64" ;;
        aarch64|arm64) PSA_ARCH="aarch64" ;;
        *) echo "[ERROR] Unsupported architecture: $(uname -m). Install Python 3.10+ manually."; exit 1 ;;
    esac
    PSA_VER="3.11.7"
    PSA_REL="20240107"
    PSA_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PSA_REL}/cpython-${PSA_VER}%2B${PSA_REL}-${PSA_ARCH}-unknown-linux-gnu-install_only.tar.gz"
    PSA_DIR="$PWD/.python"
    echo "==> Python 3.10+ not found — provisioning standalone CPython ${PSA_VER} (${PSA_ARCH})"
    mkdir -p "$PSA_DIR"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$PSA_URL" | tar -xz -C "$PSA_DIR" --strip-components=1 || true
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$PSA_URL" | tar -xz -C "$PSA_DIR" --strip-components=1 || true
    fi
    if [ -x "$PSA_DIR/bin/python3" ] && python_ok "$PSA_DIR/bin/python3"; then
        PY="$PSA_DIR/bin/python3"
    else
        echo "[ERROR] Could not provision Python automatically. Install Python 3.10+ manually,"
        echo "        then re-run with: PYTHON=/path/to/python3 bash install.sh"
        rm -rf "$PSA_DIR"
        exit 1
    fi
fi

echo "==> Using Python: $("$PY" --version 2>&1) ($("$PY" -c 'import sys; print(sys.executable)'))"

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
