# ADR-0004 — Connection Stability Hardening (Backend + Frontend)

- **Status:** Accepted
- **Date:** 2026-04-27
- **Context:** Users reported frequent freezes ("画面突然卡住、突然没画面") during
  experiments. Symptoms included telemetry lag, lost video, silent
  WebSocket death (UI showed LIVE but no data flowed), and inability to
  recover without a manual page refresh.

## Decision

Make the entire client/server pipeline self-healing along all four
transport layers — telemetry WebSocket, WebRTC video, JPEG fallback,
and the application state on top of them.

### Backend (`core/webrtc_server.py`)

1. Both WebSocket endpoints (`/`, `/video_feed`) now use
   `WebSocketResponse(autoping=True, heartbeat=15-20s)`. This keeps
   NAT/proxy mappings warm and forces aiohttp to detect half-open TCP
   within ~2× heartbeat.
2. Telemetry broadcast was sequential (`for ws in clients: await
   ws.send_json(msg)`). One slow client could head-of-line block the
   entire fan-out at 100 Hz. Replaced with `asyncio.gather` + a 0.5 s
   per-client `wait_for`. Slow / dead clients are dropped, healthy
   clients keep streaming.
3. The telemetry loop's bare `except: pass` is now rate-limited and
   logged via `carb.log_error` (max 1 message per 5 s). Failures are
   still recoverable but no longer silent.
4. `IsaacSimVideoTrack.recv()` wraps the capture coroutine in a 250 ms
   `wait_for`; if the capture stalls, the track returns the last good
   frame instead of a green flash. Replicator init has a 2 s cool-down
   (and 10 s after the retry budget is exhausted) so it cannot thrash
   Isaac Sim under repeated failures.
5. WebRTC peers now fall through 4 STUN servers (Google × 2,
   Cloudflare, Twilio). The peer state-change handler also discards the
   `RTCPeerConnection` from the active set on `disconnected` — not just
   `failed`/`closed`.
6. A periodic 15 s sweeper prunes dead `WebSocketResponse` objects and
   closed peer connections that may have leaked from buggy clients on
   bad networks.
7. Per-message handlers in `_handle_ws_message` are now wrapped in
   try/except; a buggy command no longer breaks the WS connection. A
   client-driven `{"type":"ping"}` heartbeat is also supported, with a
   `pong` reply.

### Frontend WebSocket service (`frontend/src/services/isaacService.ts`)

1. Full reconnect state machine. On `onclose` the service schedules a
   reconnect with exponential backoff (1 s → 2 s → … → capped 30 s
   with jitter). Auto-reconnect is suppressed only when the caller
   explicitly invoked `disconnect(true)`.
2. App-layer heartbeat: `{type:"ping"}` every 15 s. A 30 s "no-message"
   stale watchdog forcibly closes a silently dead socket and triggers
   the reconnect path.
3. Last `enter_experiment` is replayed on every reconnect so simulation
   state is restored without user intervention.
4. New `onStatusChange` subscriber API exposes a third state
   (`RECONNECTING`) — UI shows a yellow "REC..." badge instead of red
   "OFF" while the service is recovering.
5. `visibilitychange` listener: when the tab is foregrounded, the
   service triggers an immediate reconnect attempt (skips backoff).

### WebRTC viewer (`frontend/src/components/WebRTCIsaacViewer.tsx`)

1. Two-stage recovery on `connectionState === 'disconnected'`:
   first `pc.restartIce()` after 2.5 s, then a full reconnect after
   8 s if the peer still isn't `connected`.
2. Stall watchdog: if `framesPerSecond === 0` for 6 s, the viewer
   forces a reconnect — covers the case where ICE says "connected"
   but the RTP track has actually frozen.
3. While running on the WS-JPEG fallback the viewer attempts to
   upgrade back to WebRTC every 60 s (lower latency).
4. WS-JPEG handler now retries quickly (5 s) instead of leaving the
   viewport black after a transient drop.
5. Multiple STUN servers, matching the backend.
6. Tab-visibility listener triggers a fast retry when the user
   returns to the tab.

### Application layer (`frontend/src/components/ExperimentView.tsx`)

1. Subscribes to `onStatusChange`. On a CONNECTED transition that was
   preceded by a DOWN state, it re-issues `enter_experiment` and
   re-applies all current slider values via `sendCommand`. This keeps
   the simulation parameters in sync with the UI sliders even when
   the backend has restarted in the middle of a run.
2. The connection badge now has three visual states: green LIVE,
   yellow REC..., red OFF.

## Consequences

- Users no longer need to refresh the page after a transient network
  blip. The UI shows REC... briefly and then resumes.
- Slow / disconnected viewers cannot stall telemetry for the rest of
  the lab — broadcast is now per-client isolated.
- Half-open TCP sockets (corp VPN, Wi-Fi roam, SSH tunnel restart)
  now recover within ~30 s automatically.
- WebRTC `disconnected` (transient packet loss) no longer requires a
  full SDP renegotiation — `restartIce()` recovers in a couple of
  seconds.

## Verification

- `python3 -c "import ast; ast.parse(open('core/webrtc_server.py').read())"`
- `npx tsc --noEmit` (clean)
- `npx vite build` (clean)
- Empirical: kill the Isaac Sim server, frontend shows REC...; restart
  Isaac Sim, frontend resyncs and resumes within 1–2 s without a
  page refresh.
