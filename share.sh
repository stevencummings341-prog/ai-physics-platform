#!/usr/bin/env bash
# ============================================================
# AI Physics Experiment Platform — Public Share Link
#
# Creates a public URL that anyone on any network (including
# your campus LAN) can open in a browser to use the experiments.
# No account, no client install on the viewer side, no campus-
# level port forwarding needed — everything is one outbound
# tunnel from this machine.
#
# Why TWO providers?
#   This container's egress blocks Cloudflare (trycloudflare.com)
#   and ngrok edges. It can reach:
#     • bore.pub           — pure TCP forwarder, HTTP URL, no TTL
#     • localhost.run      — SSH reverse tunnel, HTTPS URL, 1-hour TTL
#   We default to bore (simpler, no TTL); switch to lhr when you
#   need HTTPS (e.g. the viewer's browser blocks mixed content).
#
# Architecture (bore mode):
#     Browser  →  http://bore.pub:<PORT>
#                        │  (bore.pub public edge)
#                        ▼
#     bore client (this container)  →  127.0.0.1:5173 (Vite)
#                        │  Vite proxy routes:
#                        │    /offer, /camera, /load_usd → :8080 (WebRTC HTTP)
#                        │    /ws                        → :30000 (control/telemetry)
#                        │    /video_feed                → :8080 (WS-JPEG fallback)
#                        ▼
#                     Isaac Sim backend
#
# Architecture (lhr mode):   same, but Browser → https://xxx.lhr.life
#                            terminated at localhost.run's TLS edge,
#                            then SSH reverse-tunneled in.
#
# Usage:
#   ./share.sh                   Start tunnel in background (bore, default)
#   ./share.sh --via lhr         Same, but use localhost.run (HTTPS)
#   ./share.sh --foreground      Start in foreground (blocks; Ctrl-C to stop)
#   ./share.sh --url             Print current public URL
#   ./share.sh --status          Show tunnel + backend status
#   ./share.sh --stop            Stop the tunnel
#   ./share.sh --restart         Stop + restart (new URL)
#   ./share.sh --log             Tail tunnel log
#
# Video note:
#   The frontend first tries WebRTC (UDP); public HTTP/SSH tunnels
#   only carry TCP, so WebRTC can't establish. After ~8 s the
#   viewer auto-falls-back to WS-JPEG, which runs fine through the
#   tunnel. Remote viewers therefore see a brief "connecting"
#   spinner before the live image appears. This is expected.
#
# Backend note:
#   Isaac Sim MUST be running locally. Check with
#   ./launch.sh --status  →  WebRTC RUNNING, WebSocket RUNNING.
# ============================================================
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SHARE_DIR="$PROJECT_ROOT/.share"
PID_FILE="$SHARE_DIR/tunnel.pid"
LOG_FILE="$SHARE_DIR/tunnel.log"
URL_FILE="$SHARE_DIR/public_url.txt"
PROVIDER_FILE="$SHARE_DIR/provider.txt"
KNOWN_HOSTS="$SHARE_DIR/known_hosts"

LOCAL_PORT=5173
BORE_BIN="$PROJECT_ROOT/launchers/bin/bore"
LHR_HOST="localhost.run"
LHR_USER="nokey"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

mkdir -p "$SHARE_DIR"
touch "$KNOWN_HOSTS"

# ── Helpers ─────────────────────────────────────────────────

port_open() { (echo >/dev/tcp/127.0.0.1/"$1") 2>/dev/null; }

tunnel_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

extract_url() {
    local provider="${1:-$(cat "$PROVIDER_FILE" 2>/dev/null || echo bore)}"
    case "$provider" in
        bore)
            # bore prints one of:
            #   INFO bore_cli::client: listening at bore.pub:<PORT>    (success)
            #   Error: could not connect to bore.pub:7835              (control-port error)
            # We must match ONLY the success line, otherwise we latch
            # onto "7835" (the control port) on failed retries.
            local port
            port=$(grep -oE 'listening at bore\.pub:[0-9]+' "$LOG_FILE" 2>/dev/null \
                   | tail -1 | awk -F: '{print $NF}')
            [ -n "$port" ] && echo "http://bore.pub:$port"
            ;;
        lhr)
            # localhost.run prints the URL once per session; supervisor may
            # respawn the ssh session → a new URL appears later in the log.
            grep -oE 'https://[a-zA-Z0-9.-]+\.lhr\.life' "$LOG_FILE" 2>/dev/null | tail -1
            ;;
    esac
}

wait_for_url() {
    local provider="$1" max_wait="${2:-40}" elapsed=0 url
    while [ "$elapsed" -lt "$max_wait" ]; do
        url=$(extract_url "$provider" || true)
        if [ -n "$url" ]; then
            echo "$url" > "$URL_FILE"
            echo "$url"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

stop_tunnel() {
    local killed=0
    if tunnel_running; then
        local pid; pid=$(cat "$PID_FILE")
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        killed=1
    fi
    # Sweep any stragglers with a very specific pattern (to avoid killing our own shell).
    ps -ef | awk "/[b]ore local $LOCAL_PORT /{print \$2}" | xargs -r kill 2>/dev/null || true
    ps -ef | awk "/[s]sh .*-R 80:localhost:$LOCAL_PORT .*$LHR_HOST/{print \$2}" | xargs -r kill 2>/dev/null || true
    rm -f "$PID_FILE" "$URL_FILE" "$PROVIDER_FILE"
    if [ "$killed" = 1 ]; then
        echo -e "  ${GREEN}Tunnel stopped.${NC}"
    else
        echo -e "  ${YELLOW}No tracked tunnel was running.${NC}"
    fi
}

show_status() {
    local provider url
    provider=$(cat "$PROVIDER_FILE" 2>/dev/null || echo "(none)")
    if tunnel_running; then
        # Refresh URL from the log so a respawn doesn't leave us showing a
        # stale public link.
        url=$(extract_url "$provider")
        [ -n "$url" ] && echo "$url" > "$URL_FILE"
    else
        url=$(cat "$URL_FILE" 2>/dev/null || echo "")
    fi
    echo -e "${BOLD}=== Share Tunnel Status ===${NC}"
    if tunnel_running; then
        echo -e "  Tunnel    : ${GREEN}RUNNING${NC} (PID $(cat "$PID_FILE"), via $provider)"
    else
        echo -e "  Tunnel    : ${RED}STOPPED${NC}"
    fi
    if port_open "$LOCAL_PORT"; then
        echo -e "  Frontend  : ${GREEN}RUNNING${NC} (127.0.0.1:$LOCAL_PORT)"
    else
        echo -e "  Frontend  : ${RED}STOPPED${NC}  ${YELLOW}(run ./launch.sh first)${NC}"
    fi
    if port_open 8080 && port_open 30000; then
        echo -e "  Backend   : ${GREEN}RUNNING${NC} (8080 + 30000)"
    else
        echo -e "  Backend   : ${YELLOW}NOT RUNNING${NC}  ${YELLOW}(viewers will see 'connection failed' until Isaac Sim is up)${NC}"
    fi
    if [ -n "$url" ] && tunnel_running; then
        echo -e "  Public URL: ${CYAN}${BOLD}$url${NC}"
    fi
}

ensure_frontend() {
    if ! port_open "$LOCAL_PORT"; then
        echo -e "${RED}Frontend isn't listening on :$LOCAL_PORT.${NC}"
        echo -e "Start it first:  ${CYAN}./launch.sh${NC}   (or ${CYAN}./launch.sh --all${NC} to also start Isaac Sim)"
        exit 1
    fi
}

ensure_bore() {
    if [ ! -x "$BORE_BIN" ]; then
        echo -e "${RED}bore binary missing at $BORE_BIN${NC}"
        echo -e "Install it:"
        echo -e "  ${CYAN}mkdir -p launchers/bin && \\"
        echo -e "    curl -fsSL https://github.com/ekzhang/bore/releases/download/v0.6.0/bore-v0.6.0-x86_64-unknown-linux-musl.tar.gz \\"
        echo -e "    | tar -xz -C launchers/bin && chmod +x launchers/bin/bore${NC}"
        exit 1
    fi
}

print_share_block() {
    local url="$1" provider="$2"
    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║   PUBLIC EXPERIMENT LINK — SEND THIS TO THE OTHER TEAM      ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}${CYAN}${url}${NC}"
    echo ""
    echo -e "  ${YELLOW}• Works from any network (campus, home, mobile) — just open in a browser.${NC}"
    if [ "$provider" = "lhr" ]; then
        echo -e "  ${YELLOW}• HTTPS URL via localhost.run. Anonymous tier expires in ~1 hour;"
        echo -e "    restart with ${CYAN}./share.sh --restart${YELLOW} to get a fresh URL.${NC}"
    else
        echo -e "  ${YELLOW}• HTTP URL via bore.pub (no HTTPS). A NEW port is assigned each run;"
        echo -e "    restart changes the URL. Need HTTPS? ${CYAN}./share.sh --via lhr${YELLOW}${NC}"
    fi
    echo -e "  ${YELLOW}• Backend Isaac Sim must be running locally. Verify with"
    echo -e "    ${CYAN}./launch.sh --status${YELLOW}.${NC}"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo -e "  ${CYAN}./share.sh --url${NC}       Print current URL"
    echo -e "  ${CYAN}./share.sh --status${NC}    Show tunnel + backend status"
    echo -e "  ${CYAN}./share.sh --stop${NC}      Stop the tunnel"
    echo -e "  ${CYAN}./share.sh --restart${NC}   Stop + restart (new URL)"
    echo -e "  ${CYAN}./share.sh --log${NC}       Tail tunnel log"
    echo ""
}

# ── Tunnel backends ─────────────────────────────────────────

start_bore() {
    ensure_bore
    ensure_frontend
    echo -e "${BOLD}Starting bore.pub tunnel for http://127.0.0.1:$LOCAL_PORT ...${NC}"
    : > "$LOG_FILE"; rm -f "$URL_FILE"
    echo "bore" > "$PROVIDER_FILE"
    # Supervisor loop: bore v0.6.0 does NOT auto-reconnect. bore.pub's
    # server will drop the control channel after a period of inactivity
    # or on any network blip, and the client then exits. Wrap it so it
    # respawns. Note that bore.pub assigns a fresh remote port on each
    # reconnect, so the public URL may change — `./share.sh --url` always
    # reads the latest from the log.
    setsid bash -c "
        while true; do
            echo \"[\$(date -u +%FT%TZ)] supervisor: starting bore\"
            '$BORE_BIN' local $LOCAL_PORT --to bore.pub
            code=\$?
            echo \"[\$(date -u +%FT%TZ)] supervisor: bore exited with code \$code, respawning in 3 s\"
            sleep 3
        done" \
        </dev/null >> "$LOG_FILE" 2>&1 &
    local bash_pid=$!
    disown "$bash_pid" 2>/dev/null || true
    echo "$bash_pid" > "$PID_FILE"
}

start_lhr() {
    ensure_frontend
    echo -e "${BOLD}Starting localhost.run SSH tunnel for http://127.0.0.1:$LOCAL_PORT ...${NC}"
    : > "$LOG_FILE"; rm -f "$URL_FILE"
    echo "lhr" > "$PROVIDER_FILE"
    # No -N: localhost.run needs an interactive session to print the URL banner.
    # Supervisor loop: SSH also dies on idle / network blips; respawn.
    setsid bash -c "
        while true; do
            echo \"[\$(date -u +%FT%TZ)] supervisor: starting ssh to ${LHR_HOST}\"
            ssh -tt \
                -o StrictHostKeyChecking=accept-new \
                -o UserKnownHostsFile='$KNOWN_HOSTS' \
                -o ServerAliveInterval=30 \
                -o ServerAliveCountMax=3 \
                -o ExitOnForwardFailure=yes \
                -R 80:localhost:$LOCAL_PORT \
                ${LHR_USER}@${LHR_HOST}
            code=\$?
            echo \"[\$(date -u +%FT%TZ)] supervisor: ssh exited with code \$code, respawning in 3 s\"
            sleep 3
        done" \
        </dev/null >> "$LOG_FILE" 2>&1 &
    local bash_pid=$!
    disown "$bash_pid" 2>/dev/null || true
    echo "$bash_pid" > "$PID_FILE"
}

start_tunnel() {
    local provider="$1" foreground="$2"
    if tunnel_running; then
        echo -e "${YELLOW}Tunnel is already running (PID $(cat "$PID_FILE")).${NC}"
        [ -s "$URL_FILE" ] && echo -e "  URL: ${CYAN}$(cat "$URL_FILE")${NC}"
        echo -e "Stop it first with ${CYAN}./share.sh --stop${NC}."
        exit 1
    fi
    case "$provider" in
        bore) start_bore ;;
        lhr)  start_lhr ;;
        *)    echo -e "${RED}Unknown provider: $provider${NC}"; exit 1 ;;
    esac
    echo -n "  Waiting for public URL"
    local url
    if url=$(wait_for_url "$provider" 40); then
        echo ""
        print_share_block "$url" "$provider"
    else
        echo ""
        echo -e "${RED}Failed to obtain a public URL within 40 s. Log tail:${NC}"
        tail -20 "$LOG_FILE"
        stop_tunnel
        exit 1
    fi
    if [ "$foreground" = "1" ]; then
        echo -e "${YELLOW}Foreground mode — Ctrl-C to stop.${NC}"
        trap 'stop_tunnel; exit 0' INT TERM
        wait "$(cat "$PID_FILE")" 2>/dev/null || true
    fi
}

# ── CLI dispatch ────────────────────────────────────────────

PROVIDER="bore"
FOREGROUND=0
CMD=""

while [ $# -gt 0 ]; do
    case "$1" in
        --via)
            shift
            case "$1" in
                bore|lhr|localhost.run) PROVIDER="${1/localhost.run/lhr}" ;;
                *) echo -e "${RED}--via accepts 'bore' or 'lhr'${NC}"; exit 1 ;;
            esac
            shift
            ;;
        --foreground|--fg|-f)   FOREGROUND=1; shift ;;
        --bg|--background|-d)   FOREGROUND=0; shift ;;
        --stop|stop)            CMD=stop; shift ;;
        --status|status)        CMD=status; shift ;;
        --url|url)              CMD=url; shift ;;
        --restart|restart)      CMD=restart; shift ;;
        --log|log)              CMD=log; shift ;;
        --help|-h|help)         CMD=help; shift ;;
        "")                     shift ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; echo "Run ${CYAN}./share.sh --help${NC}"; exit 1 ;;
    esac
done

case "$CMD" in
    stop)    stop_tunnel ;;
    status)  show_status ;;
    url)
        if ! tunnel_running; then
            echo -e "${RED}No active tunnel.${NC}  Run ${CYAN}./share.sh${NC} first." >&2
            exit 1
        fi
        # Re-extract from the log so we pick up any URL change caused by
        # the supervisor respawning bore/ssh on a dropped connection.
        fresh=$(extract_url "$(cat "$PROVIDER_FILE" 2>/dev/null)")
        if [ -n "$fresh" ]; then
            echo "$fresh" > "$URL_FILE"
            echo "$fresh"
        elif [ -s "$URL_FILE" ]; then
            cat "$URL_FILE"
        else
            echo -e "${RED}Tunnel process is running but no URL has been published yet. Try again in a few seconds.${NC}" >&2
            exit 1
        fi
        ;;
    restart)
        stop_tunnel || true
        sleep 2
        start_tunnel "$PROVIDER" 0
        ;;
    log)
        [ -f "$LOG_FILE" ] && tail -f "$LOG_FILE" || { echo -e "${YELLOW}No log yet.${NC}"; exit 1; }
        ;;
    help)
        sed -n '3,60p' "$0"
        ;;
    "")
        start_tunnel "$PROVIDER" "$FOREGROUND"
        ;;
esac
