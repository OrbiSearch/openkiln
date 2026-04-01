#!/usr/bin/env bash
# OpenKiln installer
# Usage: curl -fsSL https://openkiln.dev/install.sh | bash

set -euo pipefail

REPO="https://github.com/OrbiSearch/openkiln.git"

# ── colours ───────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }

echo ""
echo -e "  ${BOLD}OpenKiln installer${NC}"
echo ""

# ── python check ──────────────────────────────────────────────

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PYTHON="$cmd"
            PYTHON_VERSION=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            ok "Python ${PYTHON_VERSION}"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.11+ is required. Install from https://python.org"
fi

# ── pipx check/install ───────────────────────────────────────

if ! command -v pipx &>/dev/null; then
    warn "pipx not found — installing..."
    "$PYTHON" -m pip install --user pipx --quiet 2>/dev/null || {
        err "Could not install pipx. Install it manually: ${PYTHON} -m pip install --user pipx"
    }
    "$PYTHON" -m pipx ensurepath 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v pipx &>/dev/null; then
        err "pipx installed but not on PATH. Add ~/.local/bin to your PATH and try again."
    fi
fi

ok "pipx"

# ── install openkiln ─────────────────────────────────────────

echo ""

# get latest release tag (falls back to main if no releases)
LATEST_TAG=""
if command -v curl &>/dev/null; then
    LATEST_TAG=$(curl -fsSL "https://api.github.com/repos/OrbiSearch/openkiln/releases/latest" 2>/dev/null \
        | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('tag_name',''))" 2>/dev/null || echo "")
fi

if [ -n "$LATEST_TAG" ]; then
    ok "Latest release: ${LATEST_TAG}"
    pipx install "git+${REPO}@${LATEST_TAG}"
else
    pipx install "git+${REPO}"
fi

# ── init ──────────────────────────────────────────────────────

echo ""
openkiln init 2>/dev/null || true

echo ""
echo -e "  ${BOLD}${GREEN}OpenKiln installed.${NC}"
echo ""
echo "  Get started:"
echo "    openkiln --help"
echo "    openkiln skill list"
echo "    openkiln skill install crm"
echo ""
echo "  Upgrade anytime:"
echo "    openkiln update"
echo ""
