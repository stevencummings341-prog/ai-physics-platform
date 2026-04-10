#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — Environment Setup
#
# Run this ONCE after a container restart to restore ALL
# dependencies. Then use ./launch.sh to start services.
#
# What it installs (skips anything already present):
#   - System: curl, Node.js v20 (via nodesource)
#   - Frontend: npm dependencies (react, vite, tailwind, etc.)
#   - Python (Isaac Sim env): base deps + WebRTC server deps
#
# Usage:
#   ./setup.sh          Full setup
#   ./setup.sh --check  Just verify everything (no changes)
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
ISAAC_PIP="/root/miniconda3/envs/env_isaaclab/bin/pip"
ISAAC_PYTHON="/root/miniconda3/envs/env_isaaclab/bin/python3.11"
NODE_MAJOR=20

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

# ── Check helpers ────────────────────────────────────────────

check_curl() { command -v curl &>/dev/null; }

check_node() {
    command -v node &>/dev/null && command -v npx &>/dev/null || return 1
    local ver; ver=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
    [ "${ver:-0}" -ge 18 ]
}

check_npm_deps() {
    [ -d "$FRONTEND_DIR/node_modules" ] && [ -f "$FRONTEND_DIR/node_modules/.bin/vite" ]
}

check_python_webrtc() {
    "$ISAAC_PYTHON" -c "import aiortc, aiohttp, av" 2>/dev/null
}

check_python_base() {
    "$ISAAC_PYTHON" -c "import numpy, PIL, pandas, matplotlib, jinja2, yaml" 2>/dev/null
}

check_cryptography() {
    "$ISAAC_PYTHON" -c "
import cryptography
v = cryptography.__version__
assert v.startswith('44.'), f'need 44.x, got {v}'
" 2>/dev/null
}

# ── --check mode ─────────────────────────────────────────────

if [ "${1:-}" = "--check" ]; then
    echo -e "${BOLD}=== Environment Check ===${NC}"
    ALL_OK=true

    if check_curl; then ok "curl"; else fail "curl missing"; ALL_OK=false; fi

    if check_node; then
        ok "Node.js $(node --version)"
    else
        if command -v node &>/dev/null; then
            fail "Node.js $(node --version) — too old, need v18+"
        else
            fail "Node.js not installed"
        fi
        ALL_OK=false
    fi

    if check_npm_deps; then
        ok "Frontend npm dependencies"
    else
        fail "Frontend npm dependencies missing"
        ALL_OK=false
    fi

    if [ -x "$ISAAC_PYTHON" ]; then
        ok "Isaac Sim Python ($("$ISAAC_PYTHON" --version 2>&1))"
    else
        fail "Isaac Sim Python not found"
        ALL_OK=false
    fi

    if check_python_base; then
        ok "Python base deps (numpy, Pillow, pandas, matplotlib, jinja2, yaml)"
    else
        fail "Python base deps incomplete"
        ALL_OK=false
    fi

    if check_python_webrtc; then
        ok "Python WebRTC deps (aiortc, aiohttp, av)"
    else
        fail "Python WebRTC deps missing"
        ALL_OK=false
    fi

    if check_cryptography; then
        ok "cryptography pinned to 44.x (Isaac Sim compatible)"
    else
        fail "cryptography version wrong (need 44.x for Isaac Sim)"
        ALL_OK=false
    fi

    echo ""
    if $ALL_OK; then
        echo -e "${GREEN}${BOLD}All dependencies OK. Run ./launch.sh to start.${NC}"
    else
        echo -e "${RED}${BOLD}Some dependencies missing. Run ./setup.sh to fix.${NC}"
    fi
    exit 0
fi

# ============================================================
# Full setup
# ============================================================

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   AI Physics Experiment Platform — Setup            ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

STEPS=6
CHANGED=false

# ── 1. System tool: curl ─────────────────────────────────────

echo -e "${BOLD}[1/$STEPS] curl${NC}"
if check_curl; then
    ok "Already installed"
else
    warn "Installing curl..."
    apt-get update -qq 2>&1 | tail -1
    apt-get install -y -qq curl 2>&1 | tail -2
    check_curl && ok "Installed" || { fail "Could not install curl"; exit 1; }
    CHANGED=true
fi

# ── 2. Node.js v20 via nodesource ────────────────────────────

echo -e "${BOLD}[2/$STEPS] Node.js (>= v18 required, v${NODE_MAJOR} target)${NC}"
if check_node; then
    ok "Already installed: $(node --version)"
else
    warn "Installing Node.js v${NODE_MAJOR} from nodesource..."
    apt-get update -qq 2>&1 | tail -1
    # Install nodesource repo if not present
    if ! grep -rq "nodesource" /etc/apt/sources.list.d/ 2>/dev/null; then
        curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - 2>&1 | tail -3
    fi
    apt-get install -y -qq nodejs 2>&1 | tail -3
    if check_node; then
        ok "Installed: $(node --version)"
        CHANGED=true
    else
        fail "Node.js installation failed"
        exit 1
    fi
fi

# ── 3. Frontend npm dependencies ─────────────────────────────

echo -e "${BOLD}[3/$STEPS] Frontend npm dependencies${NC}"
if check_npm_deps; then
    ok "Already installed"
else
    warn "Running npm install..."
    cd "$FRONTEND_DIR"
    npm install --registry https://registry.npmmirror.com 2>&1 | tail -5
    cd "$PROJECT_ROOT"
    if check_npm_deps; then
        ok "Installed"
        CHANGED=true
    else
        fail "npm install failed"
        exit 1
    fi
fi

# ── 4. Python base deps ─────────────────────────────────────

echo -e "${BOLD}[4/$STEPS] Python base dependencies (numpy, Pillow, pandas, matplotlib, jinja2, pyyaml)${NC}"
if check_python_base; then
    ok "Already installed"
else
    warn "Installing from requirements.txt..."
    "$ISAAC_PIP" install -q -r "$PROJECT_ROOT/requirements.txt" 2>&1 | tail -5
    if check_python_base; then
        ok "Installed"
        CHANGED=true
    else
        fail "pip install requirements.txt failed"
        exit 1
    fi
fi

# ── 5. Python WebRTC server deps ────────────────────────────

echo -e "${BOLD}[5/$STEPS] Python WebRTC server dependencies (aiortc, aiohttp, av)${NC}"
if check_python_webrtc; then
    ok "Already installed"
else
    warn "Installing aiortc, aiohttp, av..."
    "$ISAAC_PIP" install -q aiortc aiohttp av 2>&1 | tail -5
    if check_python_webrtc; then
        ok "Installed"
        CHANGED=true
    else
        fail "Failed to install WebRTC deps"
        exit 1
    fi
fi

# ── 6. Pin cryptography to 44.x (Isaac Sim compatibility) ───

echo -e "${BOLD}[6/$STEPS] cryptography version pin (Isaac Sim requires 44.x)${NC}"
if check_cryptography; then
    ok "Already pinned: $("$ISAAC_PYTHON" -c 'import cryptography; print(cryptography.__version__)')"
else
    warn "Pinning cryptography==44.0.0..."
    "$ISAAC_PIP" install -q "cryptography==44.0.0" 2>&1 | tail -3
    if check_cryptography; then
        ok "Pinned: 44.0.0"
        CHANGED=true
    else
        fail "Could not pin cryptography"
        exit 1
    fi
fi

# ── Summary ──────────────────────────────────────────────────

echo ""
if $CHANGED; then
    echo -e "${GREEN}${BOLD}Setup complete. All dependencies installed.${NC}"
else
    echo -e "${GREEN}${BOLD}Everything was already installed. No changes needed.${NC}"
fi
echo ""
echo -e "Next step: ${CYAN}./launch.sh${NC} or ${CYAN}./launch.sh --all${NC}"
echo ""
