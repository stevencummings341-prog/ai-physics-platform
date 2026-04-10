#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — Service Launcher
#
# Starts frontend + optionally Isaac Sim. Does NOT install
# anything — run ./setup.sh first after a container restart.
#
# Usage:
#   ./launch.sh              Start frontend only
#   ./launch.sh --all        Start frontend + Isaac Sim (needs DISPLAY)
#   ./launch.sh --isaac-only Start Isaac Sim only
#   ./launch.sh --stop       Stop all services
#   ./launch.sh --status     Show running services
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$PROJECT_ROOT/.frontend.pid"
ISAAC_PID_FILE="$PROJECT_ROOT/.isaacsim.pid"
VITE_LOG="$PROJECT_ROOT/.vite.log"
ISAAC_PYTHON="/root/miniconda3/envs/env_isaaclab/bin/python3.11"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

detect_ip() { hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost"; }

is_ssh_tunnel() {
    [ -n "${SSH_CONNECTION:-}" ] || [ -n "${SSH_CLIENT:-}" ] || [ -n "${VSCODE_IPC_HOOK_CLI:-}" ]
}

port_open() { (echo >/dev/tcp/127.0.0.1/"$1") 2>/dev/null; }

wait_for_port() {
    local port="$1" max_wait="${2:-15}" elapsed=0
    while [ "$elapsed" -lt "$max_wait" ]; do
        if port_open "$port"; then return 0; fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

stop_frontend() {
    if [ -f "$PID_FILE" ]; then
        local pid; pid=$(cat "$PID_FILE")
        kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null && \
            echo -e "  ${GREEN}Frontend stopped (PID $pid)${NC}"
        rm -f "$PID_FILE"
    fi
    pkill -f "vite.*--port 5173" 2>/dev/null || true
}

stop_isaac() { "$PROJECT_ROOT/start_isaac.sh" --stop >/dev/null 2>&1 || true; }

# ── Status ───────────────────────────────────────────────────

show_status() {
    echo -e "${BOLD}=== Service Status ===${NC}"

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "  Frontend  : ${GREEN}RUNNING${NC} (PID $(cat "$PID_FILE"))"
    else
        echo -e "  Frontend  : ${RED}STOPPED${NC}"
    fi

    if [ -f "$ISAAC_PID_FILE" ] && kill -0 "$(cat "$ISAAC_PID_FILE")" 2>/dev/null; then
        echo -e "  Isaac Sim : ${GREEN}RUNNING${NC} (PID $(cat "$ISAAC_PID_FILE"))"
    else
        echo -e "  Isaac Sim : ${RED}STOPPED${NC}"
    fi

    for pair in "WebRTC:8080" "WebSocket:30000"; do
        label="${pair%%:*}"; port="${pair##*:}"
        if port_open "$port"; then
            echo -e "  ${label}    : ${GREEN}RUNNING${NC} (port $port)"
        else
            echo -e "  ${label}    : ${RED}STOPPED${NC} (port $port)"
        fi
    done

    echo ""
    if is_ssh_tunnel; then
        echo -e "  ${BOLD}Browser URL: ${CYAN}http://localhost:5173${NC} (SSH tunnel)"
    else
        echo -e "  Browser URL: ${CYAN}http://$(detect_ip):5173${NC}"
    fi
}

# ── Dispatch ─────────────────────────────────────────────────

case "${1:-}" in
    --all)        START_ISAAC=1 ;;
    --isaac-only) "$PROJECT_ROOT/start_isaac.sh"; exit 0 ;;
    --stop)       stop_frontend; stop_isaac; exit 0 ;;
    --status)     show_status; exit 0 ;;
esac

# ============================================================
# Preflight: check that setup.sh has been run
# ============================================================

MISSING=""
command -v node &>/dev/null   || MISSING="${MISSING} Node.js"
command -v npx  &>/dev/null   || MISSING="${MISSING} npx"
[ -d "$FRONTEND_DIR/node_modules" ] || MISSING="${MISSING} npm-deps"
"$ISAAC_PYTHON" -c "import aiortc, aiohttp" 2>/dev/null || MISSING="${MISSING} python-webrtc-deps"

if [ -n "$MISSING" ]; then
    echo ""
    echo -e "${RED}${BOLD}Missing dependencies:${NC}${MISSING}"
    echo -e "Run ${CYAN}./setup.sh${NC} first, then re-run ${CYAN}./launch.sh${NC}"
    echo ""
    exit 1
fi

# ============================================================
# Main launch
# ============================================================
IP=$(detect_ip)

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   AI Physics Experiment Platform — Launcher         ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Start frontend ───────────────────────────────────────

stop_frontend 2>/dev/null

echo -e "${BOLD}[1/2] Starting frontend (Vite)...${NC}"
cd "$FRONTEND_DIR"
: > "$VITE_LOG"

# Vite output goes to BOTH terminal AND log file.
# Terminal output is what triggers Cursor SSH auto port-forwarding.
npx vite --host 0.0.0.0 --port 5173 2>&1 | tee -a "$VITE_LOG" &
TEE_PID=$!
cd "$PROJECT_ROOT"

sleep 2
FRONTEND_PID=$(pgrep -f "node.*vite.*--port 5173" | head -1)
if [ -n "$FRONTEND_PID" ]; then
    echo "$FRONTEND_PID" > "$PID_FILE"
else
    echo "$TEE_PID" > "$PID_FILE"
fi

echo -n "  Waiting for port 5173"
if wait_for_port 5173 20; then
    echo ""
    echo -e "  ${GREEN}${BOLD}✓ Frontend ready${NC} (PID ${FRONTEND_PID:-$TEE_PID})"
else
    echo ""
    echo -e "  ${RED}✗ Frontend failed to start${NC}"
    echo -e "  Log: ${CYAN}cat $VITE_LOG${NC}"
    exit 1
fi

# ── 2. Isaac Sim ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}[2/2] Isaac Sim backend...${NC}"

ISAAC_RUNNING=false
if [ -f "$ISAAC_PID_FILE" ] && kill -0 "$(cat "$ISAAC_PID_FILE")" 2>/dev/null; then
    ISAAC_RUNNING=true
elif pgrep -f "isaacsim.*start_server" >/dev/null 2>&1; then
    ISAAC_RUNNING=true
fi

if $ISAAC_RUNNING; then
    echo -e "  ${GREEN}✓ Isaac Sim process is running${NC}"
    if port_open 8080 && port_open 30000; then
        echo -e "  ${GREEN}✓ Backend ports 8080 + 30000 are open${NC}"
    else
        echo -e "  ${YELLOW}! Isaac Sim running but backend ports not yet open${NC}"
        echo -e "  ${YELLOW}  (it may still be loading — check ${CYAN}.isaacsim.log${YELLOW})${NC}"
    fi
elif [ "${START_ISAAC:-0}" = "1" ]; then
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        echo -e "  Starting Isaac Sim..."
        "$PROJECT_ROOT/start_isaac.sh" || true
    else
        echo -e "  ${YELLOW}! Cannot start Isaac Sim from SSH (no DISPLAY).${NC}"
        echo -e "  ${YELLOW}  Start it from your VNC desktop:  ${CYAN}./start_isaac.sh${NC}"
    fi
else
    echo -e "  ${YELLOW}! Isaac Sim is not running.${NC}"
    echo -e "  ${YELLOW}  Start it from your VNC desktop:  ${CYAN}./start_isaac.sh${NC}"
fi

# ── 3. Open browser via Cursor/VS Code ──────────────────────

echo ""
FRONTEND_URL="http://localhost:5173"
if is_ssh_tunnel; then
    if [ -n "${BROWSER:-}" ] && [ -x "${BROWSER}" ]; then
        "$BROWSER" "$FRONTEND_URL" >/dev/null 2>&1 &
        echo -e "  ${GREEN}Opening ${CYAN}${FRONTEND_URL}${NC}${GREEN} in your browser...${NC}"
    else
        echo -e "  Open in browser: ${CYAN}${FRONTEND_URL}${NC}"
    fi
    echo -e "  ${YELLOW}(Ignore any http://${IP}:5173 URL — use localhost)${NC}"
else
    echo -e "  Open in browser: ${CYAN}http://${IP}:5173${NC}"
fi

echo ""
echo -e "${BOLD}Commands:${NC}"
echo -e "  ${CYAN}./launch.sh --status${NC}   Check services"
echo -e "  ${CYAN}./launch.sh --stop${NC}     Stop all"
echo -e "  ${CYAN}cat .vite.log${NC}          Vite log"
echo -e "  ${CYAN}tail -f .isaacsim.log${NC}  Isaac Sim log"
echo ""
