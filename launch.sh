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
#   ./launch.sh --all --share   Same as --all, then also open a public
#                               share tunnel and print the URL (one-shot
#                               command for daily use: start everything,
#                               get the hyperlink, send it to the other
#                               team)
#   ./launch.sh --isaac-only Start Isaac Sim only
#   ./launch.sh --stop       Stop all services (also stops share tunnel)
#   ./launch.sh --status     Show running services
#   ./launch.sh --open       Re-trigger Cursor SSH port forward for 5173
#                            (run this if the browser still can't open
#                             localhost after --all)
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
    # Kill any straggler Vite processes by port flag, regardless of --host value.
    pkill -f "vite .*--port 5173" 2>/dev/null || true
    pkill -f "node.*vite.*--port 5173" 2>/dev/null || true
    pkill -f "vite.*5173" 2>/dev/null || true
    # Wait up to 5 s for port 5173 to be fully released so the next Vite
    # launch binds cleanly and Cursor re-issues a fresh SSH port forward.
    local waited=0
    while [ "$waited" -lt 5 ] && port_open 5173; do
        sleep 1
        waited=$((waited + 1))
    done
}

# Fires everything needed to make Cursor SSH re-forward :5173 to the
# user's laptop. Safe to run repeatedly.
#
# NOTE: we use 127.0.0.1 (not localhost) so that Cursor's auto port
# forward binds IPv4 explicitly. On this container IPv6 is disabled
# (::1 is unreachable), and browsers frequently resolve "localhost"
# to ::1 first — that's what was making "stop + launchall" intermittent.
trigger_cursor_forward() {
    local url_v4="http://127.0.0.1:5173/"
    local url_local="http://localhost:5173/"
    # 1. Print URL in Vite's exact format — Cursor's auto-port-forward
    #    detector scans terminal output for this pattern.
    echo ""
    echo "  VITE ready"
    echo "  ➜  Local:   ${url_v4}"
    echo "  ➜  Network: http://0.0.0.0:5173/"
    # 2. Ask Cursor's remote browser helper to open the IPv4 URL, which
    #    forces the port forward to be (re-)established without the
    #    IPv6 detour.
    if [ -n "${BROWSER:-}" ] && [ -x "${BROWSER}" ]; then
        "$BROWSER" "$url_v4" >/dev/null 2>&1 &
        # Also open the localhost variant so whichever URL the user
        # types into their browser is freshly forwarded.
        "$BROWSER" "$url_local" >/dev/null 2>&1 &
    fi
    # 3. Fallback: invoke the cursor remote CLI directly in case
    #    $BROWSER is unset.
    if command -v cursor >/dev/null 2>&1; then
        cursor --openExternal "$url_v4" >/dev/null 2>&1 &
    elif command -v code >/dev/null 2>&1; then
        code --openExternal "$url_v4" >/dev/null 2>&1 &
    fi
}

stop_isaac() { "$PROJECT_ROOT/start_isaac.sh" --stop >/dev/null 2>&1 || true; }

stop_share() { "$PROJECT_ROOT/share.sh" --stop >/dev/null 2>&1 || true; }

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

START_ISAAC=0
START_SHARE=0
for arg in "$@"; do
    case "$arg" in
        --all)          START_ISAAC=1 ;;
        --share)        START_SHARE=1 ;;
        --isaac-only)   "$PROJECT_ROOT/start_isaac.sh"; exit 0 ;;
        --stop|stop)    stop_share; stop_frontend; stop_isaac; exit 0 ;;
        --status)       show_status; exit 0 ;;
        --open|--forward)
            :  # handled below so we can still fail cleanly when 5173 is down
            ;;
    esac
done

case "${1:-}" in
    --open|--forward)
        if ! port_open 5173; then
            echo -e "  ${YELLOW}! Frontend is not running on :5173. Run ${CYAN}./launch.sh${YELLOW} first.${NC}"
            exit 1
        fi
        trigger_cursor_forward
        echo ""
        echo -e "  ${GREEN}✓ Asked Cursor to forward 5173. Open ${CYAN}http://localhost:5173${NC}"
        exit 0
        ;;
esac

# If only one arg was given and it matched above (stop/status/open), we've already exited.
# Continue to main launch path.

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
#
# Bind IPv4 only (--host 0.0.0.0). This container has IPv6 disabled
# at the kernel level (net.ipv6.conf.lo.disable_ipv6 = 1 → ::1 is
# unreachable), so dual-stack IPv6 binding is pointless here. All
# reliable connection paths — Cursor's SSH tunnel, 127.0.0.1, the
# server's external IP — are IPv4.
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
    # Sanity check on IPv4 — this is the path Cursor's SSH tunnel uses.
    v4_ok=$(curl -4 -sS --max-time 2 http://127.0.0.1:5173/ -o /dev/null -w '%{http_code}' 2>/dev/null || echo "000")
    if [ "$v4_ok" = "200" ]; then
        echo -e "  ${GREEN}✓ IPv4 loopback reachable (HTTP $v4_ok)${NC}"
    else
        echo -e "  ${RED}✗ IPv4 loopback not reachable (HTTP $v4_ok) — Vite may have failed${NC}"
    fi
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
    # Auto-detect an X server if DISPLAY isn't set. On this box a VNC
    # session lives on :1 (socket /tmp/.X11-unix/X1); from an SSH shell
    # DISPLAY is empty and Isaac Sim refuses to start — we fix that by
    # discovering any live X socket and pointing DISPLAY at it.
    if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
        for sock in /tmp/.X11-unix/X*; do
            [ -e "$sock" ] || continue
            dnum="${sock##*/X}"
            if command -v xdpyinfo >/dev/null 2>&1 && \
               DISPLAY=":$dnum" xdpyinfo >/dev/null 2>&1; then
                export DISPLAY=":$dnum"
                echo -e "  ${CYAN}Auto-detected X display :$dnum${NC}"
                break
            elif ! command -v xdpyinfo >/dev/null 2>&1; then
                # No xdpyinfo available — just trust the socket.
                export DISPLAY=":$dnum"
                echo -e "  ${CYAN}Using X display :$dnum (socket present)${NC}"
                break
            fi
        done
    fi

    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        echo -e "  Starting Isaac Sim with DISPLAY=${DISPLAY:-$WAYLAND_DISPLAY}..."
        "$PROJECT_ROOT/start_isaac.sh" || true
        # Wait up to 120 s for the backend ports to come up so the
        # frontend has a live server to connect to on first browser open.
        echo -n "  Waiting for backend ports 8080 + 30000"
        waited=0
        while [ "$waited" -lt 120 ]; do
            if port_open 8080 && port_open 30000; then
                echo ""
                echo -e "  ${GREEN}${BOLD}✓ Backend ready${NC}"
                break
            fi
            echo -n "."
            sleep 3
            waited=$((waited + 3))
        done
        if ! port_open 8080 || ! port_open 30000; then
            echo ""
            echo -e "  ${YELLOW}! Backend still loading after ${waited}s; frontend may briefly show 'connection failed' until it's ready.${NC}"
            echo -e "  ${YELLOW}  Check: ${CYAN}tail -f .isaacsim.log${NC}"
        fi
    else
        echo -e "  ${YELLOW}! No X display found (DISPLAY empty, no /tmp/.X11-unix/X* sockets).${NC}"
        echo -e "  ${YELLOW}  Start it from your VNC desktop:  ${CYAN}./start_isaac.sh${NC}"
    fi
else
    echo -e "  ${YELLOW}! Isaac Sim is not running.${NC}"
    echo -e "  ${YELLOW}  Start it from your VNC desktop:  ${CYAN}./start_isaac.sh${NC}"
fi

# ── 3. Open browser via Cursor/VS Code ──────────────────────

echo ""
if is_ssh_tunnel; then
    trigger_cursor_forward
    echo ""
    echo -e "  ${BOLD}Open in browser (pick whichever works):${NC}"
    echo -e "    1. ${CYAN}${BOLD}http://127.0.0.1:5173${NC}   ${GREEN}← most reliable (IPv4, via Cursor SSH tunnel)${NC}"
    echo -e "    2. ${CYAN}http://localhost:5173${NC}   (may hit IPv6 first on some browsers)"
    echo -e "    3. ${CYAN}http://${IP}:5173${NC}        ${YELLOW}← direct, bypasses SSH tunnel entirely${NC}"
else
    echo -e "  Open in browser: ${CYAN}http://${IP}:5173${NC}"
fi

# ── 4. Optional: public share tunnel ─────────────────────────

if [ "${START_SHARE:-0}" = "1" ]; then
    echo ""
    echo -e "${BOLD}[Extra] Opening public share tunnel ...${NC}"
    # share.sh is idempotent: if a tunnel is already up, it prints the URL
    # and exits. Otherwise it starts a new background tunnel.
    if ! "$PROJECT_ROOT/share.sh" --status 2>/dev/null | grep -q 'RUNNING (PID'; then
        "$PROJECT_ROOT/share.sh"
    else
        echo -e "  ${GREEN}✓ Share tunnel already running.${NC}"
        "$PROJECT_ROOT/share.sh" --status
    fi
fi

echo ""
echo -e "${BOLD}Commands:${NC}"
echo -e "  ${CYAN}./launch.sh --status${NC}      Check services"
echo -e "  ${CYAN}./launch.sh --stop${NC}        Stop all (frontend + Isaac + share)"
echo -e "  ${CYAN}./launch.sh --open${NC}        Re-trigger Cursor port forward if the URL won't open"
echo -e "  ${CYAN}./share.sh${NC}                Open a public URL to send the other team"
echo -e "  ${CYAN}./share.sh --url${NC}          Print the current public URL"
echo -e "  ${CYAN}cat .vite.log${NC}             Vite log"
echo -e "  ${CYAN}tail -f .isaacsim.log${NC}     Isaac Sim log"
echo ""

# Second nudge 2 s later: re-print the URL and re-invoke the browser
# helper, so Cursor's auto-detect has a second chance if it missed the
# first one (common after a stop/launch cycle).
if is_ssh_tunnel; then
    ( sleep 2
      echo "  ➜  Local:   http://127.0.0.1:5173/"
      if [ -n "${BROWSER:-}" ] && [ -x "${BROWSER}" ]; then
          "$BROWSER" "http://127.0.0.1:5173/" >/dev/null 2>&1 &
      fi
    ) &
fi
