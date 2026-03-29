#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — One-Click Launcher
#
# Usage:
#   ./launch.sh              Start frontend + print Isaac Sim instructions
#   ./launch.sh --stop       Stop everything
#   ./launch.sh --status     Show running services
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PID_FILE="$PROJECT_ROOT/.frontend.pid"

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

show_status() {
    echo -e "${BOLD}=== Service Status ===${NC}"
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "  Frontend: ${GREEN}RUNNING${NC} (PID $(cat "$PID_FILE"))"
    else
        echo -e "  Frontend: ${RED}STOPPED${NC}"
    fi
    if ss -tlnp 2>/dev/null | grep -q ":8080"; then
        echo -e "  WebRTC  : ${GREEN}RUNNING${NC} (port 8080)"
    else
        echo -e "  WebRTC  : ${RED}STOPPED${NC} — start Isaac Sim and run start_server.py"
    fi
    if ss -tlnp 2>/dev/null | grep -q ":30000"; then
        echo -e "  WebSocket: ${GREEN}RUNNING${NC} (port 30000)"
    else
        echo -e "  WebSocket: ${RED}STOPPED${NC}"
    fi
}

case "${1:-}" in
    --stop)
        stop_frontend
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
echo -e "${BOLD}${YELLOW}⚠  Isaac Sim backend — you need to do ONE more thing:${NC}"
echo ""
echo -e "  Open Isaac Sim → Window → Script Editor → paste and run:"
echo ""
echo -e "    ${CYAN}exec(open('${PROJECT_ROOT}/start_server.py').read())${NC}"
echo ""
echo -e "  Or if using headless Isaac Sim:"
echo ""
echo -e "    ${CYAN}~/.local/share/ov/pkg/isaac-sim-*/python.sh ${PROJECT_ROOT}/start_server.py${NC}"
echo ""
echo -e "${BOLD}Once the server prints 'Server running!', open your browser to:${NC}"
echo -e "  ${CYAN}http://${IP}:5173${NC}"
echo ""
echo -e "Management commands:"
echo -e "  ${CYAN}./launch.sh --status${NC}   Check services"
echo -e "  ${CYAN}./launch.sh --stop${NC}     Stop frontend"
echo ""
