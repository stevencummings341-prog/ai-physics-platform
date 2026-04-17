#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — Environment Setup
#
# Run this ONCE after a container restart to restore ALL
# dependencies. Then use ./launch.sh to start services.
#
# What it installs (skips anything already present):
#   - System: curl, ca-certificates
#   - Node.js v20 (direct binary from Tsinghua mirror, bypasses
#     the flaky nodesource / apt install that kept hanging on
#     the university network)
#   - Frontend: npm dependencies via npmmirror registry
#   - Python (Isaac Sim env): pip routed through Tsinghua mirror,
#     base deps + WebRTC server deps + cryptography 44.x pin
#
# Usage:
#   ./setup.sh          Full setup (idempotent, safe to re-run)
#   ./setup.sh --check  Just verify everything (no changes)
#   ./setup.sh --force  Re-install everything even if present
# ============================================================
set -eu
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
ISAAC_PIP="/root/miniconda3/envs/env_isaaclab/bin/pip"
ISAAC_PYTHON="/root/miniconda3/envs/env_isaaclab/bin/python3.11"

# ── Tunables ────────────────────────────────────────────────
NODE_VERSION="20.19.0"                   # LTS at time of writing
NODE_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/nodejs-release"
NPM_REGISTRY="https://registry.npmmirror.com"
PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
CRYPTOGRAPHY_PIN="44.0.0"

CURL_OPTS=(--fail --silent --show-error --location \
           --connect-timeout 10 --max-time 180 --retry 3 --retry-delay 2)

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}·${NC} $1"; }

MODE="install"
for arg in "$@"; do
    case "$arg" in
        --check) MODE="check" ;;
        --force) MODE="force" ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) fail "Unknown arg: $arg"; exit 2 ;;
    esac
done

# ── Check helpers ────────────────────────────────────────────

check_curl()  { command -v curl &>/dev/null; }
check_node()  {
    command -v node &>/dev/null && command -v npx &>/dev/null || return 1
    local ver; ver=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
    [ "${ver:-0}" -ge 18 ]
}
check_npm_deps()       { [ -d "$FRONTEND_DIR/node_modules" ] && [ -f "$FRONTEND_DIR/node_modules/.bin/vite" ]; }
check_python_base()    { "$ISAAC_PYTHON" -c "import numpy, PIL, pandas, matplotlib, jinja2, yaml" 2>/dev/null; }
check_python_webrtc()  { "$ISAAC_PYTHON" -c "import aiortc, aiohttp, av" 2>/dev/null; }
check_cryptography()   {
    "$ISAAC_PYTHON" -c "
import cryptography, sys
v = cryptography.__version__
sys.exit(0 if v.startswith('44.') else 1)
" 2>/dev/null
}

# ── --check mode ─────────────────────────────────────────────

if [ "$MODE" = "check" ]; then
    echo -e "${BOLD}=== Environment Check ===${NC}"
    ALL_OK=true

    if check_curl; then ok "curl ($(curl --version | head -1 | awk '{print $2}'))"; else fail "curl missing"; ALL_OK=false; fi

    if check_node; then
        ok "Node.js $(node --version), npm $(npm --version)"
    else
        if command -v node &>/dev/null; then
            fail "Node.js $(node --version) — too old, need v18+"
        else
            fail "Node.js not installed"
        fi
        ALL_OK=false
    fi

    if check_npm_deps; then ok "Frontend npm dependencies"; else fail "Frontend npm dependencies missing"; ALL_OK=false; fi

    if [ -x "$ISAAC_PYTHON" ]; then
        ok "Isaac Sim Python ($("$ISAAC_PYTHON" --version 2>&1))"
    else
        fail "Isaac Sim Python not found at $ISAAC_PYTHON"
        ALL_OK=false
    fi

    if check_python_base;    then ok "Python base deps";                     else fail "Python base deps incomplete"; ALL_OK=false; fi
    if check_python_webrtc;  then ok "Python WebRTC deps (aiortc/aiohttp/av)"; else fail "Python WebRTC deps missing"; ALL_OK=false; fi
    if check_cryptography;   then ok "cryptography pinned to 44.x";           else fail "cryptography needs 44.x pin"; ALL_OK=false; fi

    echo ""
    if $ALL_OK; then
        echo -e "${GREEN}${BOLD}All dependencies OK. Run ./launch.sh to start.${NC}"
        exit 0
    else
        echo -e "${RED}${BOLD}Some dependencies missing. Run ./setup.sh to fix.${NC}"
        exit 1
    fi
fi

# ============================================================
# Full setup (install / force)
# ============================================================

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   AI Physics Experiment Platform — Setup             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
[ "$MODE" = "force" ] && warn "Running in --force mode: will reinstall even if present"

STEPS=7

# ── 0. Defensive cleanup (no hangs next run) ─────────────────

echo -e "${BOLD}[0/$STEPS] Preflight cleanup (apt locks, stale nodesource, zombie curl)${NC}"
# Kill any previous stuck installers from a cancelled run
pkill -9 -f "apt-get|apt install|dpkg|deb.nodesource" 2>/dev/null || true
pkill -9 -f "^curl .*(nodesource|deb\\.nodesource)" 2>/dev/null || true
# Release apt locks if they were left behind
for lk in /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend \
          /var/lib/apt/lists/lock /var/cache/apt/archives/lock; do
    [ -e "$lk" ] && rm -f "$lk" 2>/dev/null || true
done
dpkg --configure -a >/dev/null 2>&1 || true
# Remove any nodesource apt source files — they cause `apt-get update` to
# hang on deb.nodesource.com on this network
if ls /etc/apt/sources.list.d/nodesource* >/dev/null 2>&1; then
    rm -f /etc/apt/sources.list.d/nodesource* 2>/dev/null || true
    info "Removed stale nodesource apt source(s)"
fi
ok "Environment cleaned"

# ── 1. System tool: curl ─────────────────────────────────────

echo -e "${BOLD}[1/$STEPS] curl${NC}"
if check_curl && [ "$MODE" != "force" ]; then
    ok "Already installed ($(curl --version | head -1 | awk '{print $2}'))"
else
    warn "Installing curl + ca-certificates via apt..."
    DEBIAN_FRONTEND=noninteractive apt-get update -qq -o Acquire::Retries=2 \
        -o Acquire::http::Timeout=20 2>&1 | tail -1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        -o Acquire::Retries=2 -o Acquire::http::Timeout=20 \
        curl ca-certificates 2>&1 | tail -2
    check_curl || { fail "Could not install curl"; exit 1; }
    ok "Installed"
fi

# ── 2. Node.js (direct tarball from Tsinghua, NOT nodesource) ─

echo -e "${BOLD}[2/$STEPS] Node.js v${NODE_VERSION} (Tsinghua mirror, direct binary)${NC}"
if check_node && [ "$MODE" != "force" ]; then
    ok "Already installed: $(node --version) / npm $(npm --version)"
else
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  NODE_ARCH=linux-x64 ;;
        aarch64) NODE_ARCH=linux-arm64 ;;
        armv7l)  NODE_ARCH=linux-armv7l ;;
        *) fail "Unsupported arch: $ARCH"; exit 1 ;;
    esac
    TARBALL="node-v${NODE_VERSION}-${NODE_ARCH}.tar.xz"
    URL="${NODE_MIRROR}/v${NODE_VERSION}/${TARBALL}"
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT

    info "Downloading ${URL}"
    if ! curl "${CURL_OPTS[@]}" -o "$TMP_DIR/$TARBALL" "$URL"; then
        fail "Download failed from Tsinghua mirror"
        fail "Check network connectivity or try: curl -v $URL"
        exit 1
    fi
    info "Extracting..."
    tar -xJf "$TMP_DIR/$TARBALL" -C "$TMP_DIR"
    NODE_SRC="$TMP_DIR/node-v${NODE_VERSION}-${NODE_ARCH}"
    info "Installing into /usr/local"
    # Copy instead of rsync to avoid extra dependency
    cp -r "$NODE_SRC"/bin/*      /usr/local/bin/      2>/dev/null || true
    cp -r "$NODE_SRC"/include/*  /usr/local/include/  2>/dev/null || true
    cp -r "$NODE_SRC"/lib/*      /usr/local/lib/      2>/dev/null || true
    cp -r "$NODE_SRC"/share/*    /usr/local/share/    2>/dev/null || true
    hash -r

    if check_node; then
        ok "Installed: $(node --version) / npm $(npm --version)"
    else
        fail "Node.js binary install failed"
        exit 1
    fi
fi

# Point npm at npmmirror for reliable package fetches
if command -v npm &>/dev/null; then
    current_registry=$(npm config get registry 2>/dev/null || echo "")
    if [ "$current_registry" != "$NPM_REGISTRY/" ] && [ "$current_registry" != "$NPM_REGISTRY" ]; then
        npm config set registry "$NPM_REGISTRY" >/dev/null 2>&1 || true
        info "npm registry set to $NPM_REGISTRY"
    fi
fi

# ── 3. pip mirror (Tsinghua) ─────────────────────────────────

echo -e "${BOLD}[3/$STEPS] pip index URL → Tsinghua mirror${NC}"
if [ ! -x "$ISAAC_PIP" ]; then
    fail "$ISAAC_PIP not found — is the Isaac Sim conda env installed?"
    exit 1
fi
CURRENT_INDEX=$("$ISAAC_PIP" config get global.index-url 2>/dev/null || echo "")
if [ "$CURRENT_INDEX" = "$PIP_INDEX_URL" ] && [ "$MODE" != "force" ]; then
    ok "Already pointing at Tsinghua"
else
    "$ISAAC_PIP" config set global.index-url "$PIP_INDEX_URL" >/dev/null
    "$ISAAC_PIP" config set global.trusted-host "pypi.tuna.tsinghua.edu.cn" >/dev/null
    ok "Configured: $PIP_INDEX_URL"
fi

# ── 4. Frontend npm dependencies ─────────────────────────────

echo -e "${BOLD}[4/$STEPS] Frontend npm dependencies${NC}"
if check_npm_deps && [ "$MODE" != "force" ]; then
    ok "Already installed"
else
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        fail "No frontend/package.json found at $FRONTEND_DIR"
        exit 1
    fi
    warn "Running npm install (registry: $NPM_REGISTRY)..."
    (
        cd "$FRONTEND_DIR"
        npm install --registry "$NPM_REGISTRY" --no-audit --no-fund 2>&1 | tail -8
    )
    if check_npm_deps; then
        ok "Installed"
    else
        fail "npm install failed"
        exit 1
    fi
fi

# ── 5. Python base deps ──────────────────────────────────────

echo -e "${BOLD}[5/$STEPS] Python base deps (numpy, Pillow, pandas, matplotlib, jinja2, pyyaml)${NC}"
if check_python_base && [ "$MODE" != "force" ]; then
    ok "Already installed"
else
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        warn "Installing from requirements.txt..."
        "$ISAAC_PIP" install -q -r "$PROJECT_ROOT/requirements.txt" 2>&1 | tail -5
    else
        warn "requirements.txt missing; installing explicit base set..."
        "$ISAAC_PIP" install -q numpy Pillow pandas matplotlib jinja2 pyyaml 2>&1 | tail -5
    fi
    if check_python_base; then
        ok "Installed"
    else
        fail "pip install failed"
        exit 1
    fi
fi

# ── 6. Python WebRTC server deps ─────────────────────────────

echo -e "${BOLD}[6/$STEPS] Python WebRTC deps (aiortc, aiohttp, av)${NC}"
if check_python_webrtc && [ "$MODE" != "force" ]; then
    ok "Already installed"
else
    warn "Installing aiortc, aiohttp, av..."
    "$ISAAC_PIP" install -q aiortc aiohttp av 2>&1 | tail -5
    if check_python_webrtc; then
        ok "Installed"
    else
        fail "Failed to install WebRTC deps"
        exit 1
    fi
fi

# ── 7. Pin cryptography to 44.x (Isaac Sim compatibility) ───

echo -e "${BOLD}[7/$STEPS] cryptography pin (Isaac Sim needs 44.x)${NC}"
if check_cryptography && [ "$MODE" != "force" ]; then
    ok "Already pinned: $("$ISAAC_PYTHON" -c 'import cryptography; print(cryptography.__version__)')"
else
    warn "Pinning cryptography==${CRYPTOGRAPHY_PIN}..."
    "$ISAAC_PIP" install -q "cryptography==${CRYPTOGRAPHY_PIN}" 2>&1 | tail -3
    if check_cryptography; then
        ok "Pinned: $CRYPTOGRAPHY_PIN"
    else
        fail "Could not pin cryptography"
        exit 1
    fi
fi

# ── Final verification ───────────────────────────────────────

echo ""
echo -e "${BOLD}Final verification${NC}"
FAIL=false
check_curl            && ok "curl"                   || { fail "curl";            FAIL=true; }
check_node            && ok "Node.js $(node --version)" || { fail "node";         FAIL=true; }
check_npm_deps        && ok "frontend node_modules"  || { fail "frontend deps";   FAIL=true; }
check_python_base     && ok "python base deps"       || { fail "python base";     FAIL=true; }
check_python_webrtc   && ok "python webrtc deps"     || { fail "python webrtc";   FAIL=true; }
check_cryptography    && ok "cryptography 44.x"      || { fail "cryptography";    FAIL=true; }

echo ""
if $FAIL; then
    echo -e "${RED}${BOLD}Setup incomplete. Re-run ./setup.sh or investigate failures above.${NC}"
    exit 1
fi
echo -e "${GREEN}${BOLD}Setup complete. All dependencies installed.${NC}"
echo ""
echo -e "Next step: ${CYAN}./launch.sh${NC}   (frontend only, safe in SSH)"
echo -e "          ${CYAN}./launch.sh --all${NC}   (frontend + Isaac Sim backend)"
echo ""
