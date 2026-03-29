#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_ROOT/.isaacsim.pid"
LOG_FILE="$PROJECT_ROOT/.isaacsim.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

find_isaacsim() {
    if command -v isaacsim >/dev/null 2>&1; then
        command -v isaacsim
        return
    fi
    if [ -x "/root/miniconda3/envs/env_isaaclab/bin/isaacsim" ]; then
        echo "/root/miniconda3/envs/env_isaaclab/bin/isaacsim"
        return
    fi
    if [ -x "$HOME/miniconda3/envs/env_isaaclab/bin/isaacsim" ]; then
        echo "$HOME/miniconda3/envs/env_isaaclab/bin/isaacsim"
        return
    fi
    return 1
}

stop_isaac() {
    if [ -f "$PID_FILE" ]; then
        pid="$(cat "$PID_FILE")"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo -e "${GREEN}Isaac Sim stopped (PID $pid)${NC}"
        fi
        rm -f "$PID_FILE"
    else
        echo "No Isaac Sim PID file found."
    fi
}

show_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "  Isaac Sim : ${GREEN}RUNNING${NC} (PID $(cat "$PID_FILE"))"
        echo -e "  Log file  : ${CYAN}$LOG_FILE${NC}"
    else
        echo -e "  Isaac Sim : ${RED}STOPPED${NC}"
    fi
}

case "${1:-}" in
    --stop)
        stop_isaac
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
esac

ISAACSIM_BIN="$(find_isaacsim || true)"
if [ -z "$ISAACSIM_BIN" ]; then
    echo -e "${RED}Could not find isaacsim executable.${NC}"
    exit 1
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo -e "${RED}No graphical display detected.${NC}"
    echo -e "${YELLOW}Run this script from your VNC terminal / desktop session, not from a pure SSH shell.${NC}"
    exit 1
fi

stop_isaac >/dev/null 2>&1 || true

echo -e "${GREEN}Starting Isaac Sim from:${NC} $ISAACSIM_BIN"
echo -e "${GREEN}Using display:${NC} ${DISPLAY:-$WAYLAND_DISPLAY}"
echo -e "${GREEN}Auto-running:${NC} $PROJECT_ROOT/start_server.py"

AI_PHYSICS_PROJECT_ROOT="$PROJECT_ROOT" OMNI_KIT_ALLOW_ROOT=1 nohup "$ISAACSIM_BIN" --allow-root \
    --exec "$PROJECT_ROOT/start_server.py" \
    >"$LOG_FILE" 2>&1 &

ISAAC_PID=$!
echo "$ISAAC_PID" > "$PID_FILE"

sleep 3

if kill -0 "$ISAAC_PID" 2>/dev/null; then
    echo -e "${GREEN}Isaac Sim launched (PID $ISAAC_PID).${NC}"
    echo -e "${CYAN}Watch startup log:${NC} tail -f \"$LOG_FILE\""
else
    echo -e "${RED}Isaac Sim exited immediately. Check:${NC} $LOG_FILE"
    exit 1
fi
