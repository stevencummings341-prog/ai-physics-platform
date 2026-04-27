# 2026-04-27 — Connection Stability Hardening

## TL;DR

Made the entire pipeline (WS telemetry / WebRTC video / WS-JPEG
fallback / application state) self-healing. Users no longer need to
refresh after a transient network drop. Slow clients can no longer
freeze the rest of the lab.

See `docs/adr/ADR-0004-stability-hardening.md` for the full rationale
and decision record.

## Files Changed

| File | Change |
|------|--------|
| `core/webrtc_server.py` | aiohttp heartbeat on both WS endpoints, parallel telemetry fan-out with per-client timeout, video-track timeout + last-good-frame cache, multi-STUN, dead-client sweeper, error-isolated `_handle_ws_message`, ping/pong support, throttled Replicator re-init |
| `frontend/src/services/isaacService.ts` | Full reconnect state machine (exp backoff + jitter), 15 s heartbeat, 30 s stale watchdog, replay `enter_experiment` on reconnect, `onStatusChange` subscribers, visibilitychange fast retry |
| `frontend/src/components/WebRTCIsaacViewer.tsx` | Two-stage ICE recovery (restartIce → full reconnect), 6 s stall watchdog, periodic WS-JPEG → WebRTC upgrade, multi-STUN, tab-visibility retry |
| `frontend/src/components/ExperimentView.tsx` | New three-state status badge (LIVE / REC... / OFF), post-reconnect resync of `enter_experiment` + slider values |
| `frontend/src/types.ts` | New `ConnectionStatus.RECONNECTING` enum value |
| `docs/adr/ADR-0004-stability-hardening.md` | Decision record |

## How To Verify Locally

1. Start the platform normally (`./launch.sh` + Script Editor `start_server.py`).
2. Open the frontend, enter any experiment, observe the green LIVE badge.
3. Stop Isaac Sim. The badge should turn yellow REC... within ~2 s and
   the WebRTC viewer should switch to its retry/reconnect logic.
4. Re-run `start_server.py` in Isaac Sim. The badge returns to LIVE
   within ~5 s, telemetry resumes, slider values are still in sync,
   and the video reconnects without a page refresh.
5. Slow client test: open three browser tabs. On one, throttle the
   network with DevTools to 50 kbps. The other two tabs should keep
   receiving 100 Hz telemetry without stalling.

## Things Future Agents Should Know

- `_telemetry_loop()` no longer silently swallows exceptions; if you
  see `[telemetry] loop error:` in the Isaac Sim log, that is a real
  bug, not a transient hiccup.
- Per-experiment commands inside `_handle_ws_message` should still
  raise on programmer error — the wrapper turns them into a
  `{"type":"error", ...}` message back to the client; it does NOT
  hide the error.
- The frontend's `enterExperiment()` is now idempotent because the
  service replays it on reconnect. If you add a new experiment that
  has expensive one-time setup, gate it on a `scene_built` flag in
  the backend (existing experiments already do this).
- `ConnectionStatus.RECONNECTING` is a new enum value — TypeScript
  switch statements that match on it should be reviewed in any future
  components.
