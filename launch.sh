#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — One-Click Launcher
#
# Usage:
#   ./launch.sh              Start frontend only
#   ./launch.sh --all        Start frontend + Isaac Sim (from VNC session)
#   ./launch.sh --isaac-only Start Isaac Sim only
#   ./launch.sh --stop       Stop frontend + Isaac Sim
#   ./launch.sh --status     Show running services
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$PROJECT_ROOT/.frontend.pid"
ISAAC_PID_FILE="$PROJECT_ROOT/.isaacsim.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

detect_ip() {
    hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost"
}

stop_frontend() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo -e "${GREEN}Frontend stopped (PID $pid)${NC}"
        fi
        rm -f "$PID_FILE"
    else
        echo "No frontend PID file found."
    fi
}

stop_isaac() {
    "$PROJECT_ROOT/start_isaac.sh" --stop >/dev/null 2>&1 || true
}

show_status() {
    echo -e "${BOLD}=== Service Status ===${NC}"
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "  Frontend: ${GREEN}RUNNING${NC} (PID $(cat "$PID_FILE"))"
    else
        echo -e "  Frontend: ${RED}STOPPED${NC}"
    fi
    if [ -f "$ISAAC_PID_FILE" ] && kill -0 "$(cat "$ISAAC_PID_FILE")" 2>/dev/null; then
        echo -e "  Isaac Sim: ${GREEN}RUNNING${NC} (PID $(cat "$ISAAC_PID_FILE"))"
    else
        echo -e "  Isaac Sim: ${RED}STOPPED${NC}"
    fi
    python3 - <<'PY'
import socket
for label, port in [("WebRTC", 8080), ("WebSocket", 30000)]:
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        print(f"  {label:<9}: \033[0;32mRUNNING\033[0m (port {port})")
    except Exception:
        print(f"  {label:<9}: \033[0;31mSTOPPED\033[0m (port {port})")
    finally:
        s.close()
PY
}

case "${1:-}" in
    --all)
        START_ISAAC=1
        ;;
    --isaac-only)
        "$PROJECT_ROOT/start_isaac.sh"
        exit 0
        ;;
    --stop)
        stop_frontend
        stop_isaac
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
esac

# ============================================================
# Main launch
# ============================================================
IP=$(detect_ip)

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   AI Physics Experiment Platform — Launcher         ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# --- Step 1: Install frontend deps if needed ---
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}[1/2] Installing frontend dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install --registry https://registry.npmmirror.com 2>&1 | tail -3
    cd "$PROJECT_ROOT"
else
    echo -e "${GREEN}[1/2] Frontend dependencies already installed.${NC}"
fi

# --- Step 2: Start frontend dev server ---
stop_frontend 2>/dev/null  # kill old instance if any

echo -e "${GREEN}[2/2] Starting frontend dev server...${NC}"
cd "$FRONTEND_DIR"
npx vite --host 0.0.0.0 --port 5173 > /dev/null 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$PID_FILE"
cd "$PROJECT_ROOT"

sleep 2

echo ""
echo -e "${BOLD}${GREEN}✓ Frontend running${NC}"
echo -e "  URL: ${CYAN}http://${IP}:5173${NC}"
echo ""

if [ "${START_ISAAC:-0}" = "1" ]; then
    echo -e "${GREEN}Starting Isaac Sim as requested (--all)...${NC}"
    "$PROJECT_ROOT/start_isaac.sh"
    echo ""
else
    echo -e "${BOLD}${YELLOW}⚠  Isaac Sim backend — you need to do ONE more thing:${NC}"
    echo ""
    echo -e "  If you are inside a VNC desktop terminal, you can now run:"
    echo ""
    echo -e "    ${CYAN}./start_isaac.sh${NC}"
    echo ""
    echo -e "  Or manually inside Isaac Sim Script Editor:"
    echo ""
    echo -e "    ${CYAN}exec(open('${PROJECT_ROOT}/start_server.py').read())${NC}"
    echo ""
fi

echo -e "${BOLD}Once the server prints 'Server running!', open your browser to:${NC}"
echo -e "  ${CYAN}http://${IP}:5173${NC}"
echo ""
echo -e "Management commands:"
echo -e "  ${CYAN}./launch.sh --all${NC}      Frontend + Isaac Sim together"
echo -e "  ${CYAN}./launch.sh --isaac-only${NC} Start Isaac Sim only"
echo -e "  ${CYAN}./launch.sh --status${NC}   Check services"
echo -e "  ${CYAN}./launch.sh --stop${NC}     Stop frontend"
echo ""
