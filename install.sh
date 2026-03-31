#!/usr/bin/env bash
# OpenKiln installer
# Usage: bash install.sh
# Or paste directly into a Claude Code / agent session

set -e

REPO="https://github.com/OrbiSearch/openkiln"
INSTALL_DIR="openkiln"

# ── colours ───────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }
header() { echo -e "\n${BOLD}$1${NC}"; }

# ── python check ──────────────────────────────────────────────

header "Checking Python version..."

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c 'import sys; print(sys.version_info[:2])')
        if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PYTHON="$cmd"
            ok "Found $cmd ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.11+ is required. Install from https://python.org"
fi

# ── clone or update ───────────────────────────────────────────

header "Setting up OpenKiln repo..."

if [ -d "$INSTALL_DIR/.git" ]; then
    warn "Repo already exists at ./$INSTALL_DIR — pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    if [ -d "$INSTALL_DIR" ]; then
        err "Directory ./$INSTALL_DIR exists but is not a git repo. Remove it and retry."
    fi
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    ok "Cloned to ./$INSTALL_DIR"
fi

# ── venv ──────────────────────────────────────────────────────

header "Creating virtual environment..."

if [ ! -d ".venv" ]; then
    "$PYTHON" -m venv .venv
    ok "Created .venv"
else
    ok ".venv already exists"
fi

source .venv/bin/activate

# ── install ───────────────────────────────────────────────────

header "Installing OpenKiln..."

pip install -e ".[dev]" --quiet
ok "Installed openkiln"

# ── verify ────────────────────────────────────────────────────

header "Verifying installation..."

if ! command -v openkiln &>/dev/null; then
    err "openkiln command not found after install. Something went wrong."
fi

ok "openkiln command available"

# ── init ──────────────────────────────────────────────────────

header "Initialising OpenKiln..."

openkiln init

# ── done ──────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}OpenKiln is ready.${NC}"
echo ""
echo "Next steps:"
echo "  source .venv/bin/activate     # activate the environment"
echo "  openkiln --help               # see all commands"
echo "  openkiln skill list           # see available skills"
echo "  cat AGENTS.md                 # if you're an AI agent, read this first"
echo ""
echo "Quick start:"
echo "  openkiln skill install crm"
echo "  openkiln skill install orbisearch"
echo "  openkiln record inspect your-contacts.csv --skill crm"
echo "  openkiln record import your-contacts.csv --type contact --skill crm --apply"
echo ""
