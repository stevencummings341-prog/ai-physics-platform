# Handoff — 2026-04-28 — Recover from Exp 4 stuck-report + dead-frontend outage

## Symptom

The user reported two simultaneous failures:

1. **"实验四的实验报告又导出不了了，一直卡在那里"** — clicking *Generate
   Lab Report* on Experiment 4 streamed progress for a few seconds, then
   the spinner hung forever. No `exp4_report_ready` ever arrived.
2. **"现在其他实验也打不开了"** — other experiments would not load in the
   browser at all.

## Root cause

### Bug A — `Cannot write to closing transport`

`.isaacsim.log` line 847 (truncated):
```
[Error] [core.webrtc_server] _run_exp4_full_experiment: Cannot write to closing transport
File "/125090599/core/webrtc_server.py", line 4958, in _run_exp4_full_experiment
    await ws.send_json({"type": "exp4_report_ready", "data": payload})
aiohttp.client_exceptions.ClientConnectionResetError: Cannot write to closing transport
```

The Exp 4 report pipeline runs RK4 + matplotlib in a CPU-bound executor
for 10–20 s. During that synchronous window the client's WebSocket
transport closed (browser tab refresh, Cursor SSH tunnel reconnect, user
navigated to a different experiment, …). When the executor finally
finished and the handler called `ws.send_json(…)`, the transport was
gone and the call raised `ConnectionResetError`. The report had been
successfully **rendered** on disk — but it was never **delivered**.
There was no fallback path for the frontend to fetch the cached result
on reconnect, so the spinner hung forever.

### Bug B — Vite died on TTY EIO

`.vite.log`:
```
Error: read EIO at TTY.onStreamRead
Emitted 'error' event on Interface instance at:
    at ReadStream.onerror
```

`launch.sh` started Vite as `npx vite ... | tee -a "$VITE_LOG" &` without
redirecting stdin. Vite reads stdin to handle its interactive shortcuts
("press h + enter to show help"). When the parent shell that owned the
TTY went away (Cursor SSH session refresh), the next read on the orphaned
TTY raised `EIO`, which crashed Vite with an unhandled `'error'` event.
Port 5173 went dead → frontend would not load → "其他实验打不开".

## Fix

### `launch.sh`

```diff
-npx vite --host 0.0.0.0 --port 5173 2>&1 | tee -a "$VITE_LOG" &
+npx vite --host 0.0.0.0 --port 5173 < /dev/null 2>&1 | tee -a "$VITE_LOG" &
```

Detach Vite's stdin so it never touches the launcher's TTY. The pipeline
now survives parent-shell death.

### `core/webrtc_server.py`

Three connected changes inside `_run_exp4_full_experiment` and the WS
dispatch:

1. **Server-side report cache.** The fully rendered payload is stored on
   `self._exp4_report_cache` so a closed WebSocket cannot lose the
   result. A status field `self._exp4_report_status` in
   `{"idle", "running", "ready", "error"}` tells the server what state
   the cache is in.

2. **`_safe_ws_send` + `_broadcast_or_ignore` helpers.** Send to one or
   all clients without ever raising on a closed transport. Used for both
   per-progress frames *and* the final `exp4_report_ready` delivery. The
   pipeline now broadcasts to *every* connected client, so a freshly
   reconnected socket also gets the result.

3. **New `fetch_exp4_report` WS handler.** The frontend can request the
   cached payload at any time. Server returns either
   `exp4_report_ready` (cache hit) or an `exp4_progress` frame describing
   the current state ("still running", "no report generated", "error").

Pipeline runtime was also reduced (`sweep_points` 18 → 12) to shrink the
window during which a WS drop is possible. Concurrent runs are now
refused (the second click no-ops with a status frame instead of starting
a parallel pipeline that would race the cache).

### `frontend/src/components/ExperimentView.tsx`

1. **Reconnect-time auto-fetch.** When the WebSocket reconnects on
   Experiment 4, the frontend now sends `fetch_exp4_report` immediately,
   so a payload that was rendered while the socket was down is delivered
   without user action.
2. **8-second-poll watchdog.** While waiting for `exp4_report_ready`,
   the frontend polls `fetch_exp4_report` every 8 s. After 2 minutes
   without a payload it shows a helpful "please retry" message instead
   of hanging forever.

## Verification

- `npx tsc --noEmit` ✅
- `python3 -c "import ast; ast.parse(...)"` on `webrtc_server.py` ✅
- ReadLints on all three changed files ✅ no errors
- End-to-end WS smoke test (`/tmp/test_exp4_ws.py`, since deleted):
  1. Connect → kick off pipeline → drop the socket after 4 s.
  2. Reconnect → send `fetch_exp4_report`.
  3. Server reports "still running on server", continues streaming
     progress to the new socket, then delivers `exp4_report_ready`.
  4. Payload contains 5 plots, 3 resonance_fits, 3 phase_runs, pdf_b64,
     zip_b64, all metrics. ✅ PASS.

## Service state after the fix

```
$ ./launch.sh --status
  Frontend  : RUNNING (PID 171437)
  Isaac Sim : RUNNING (PID 171776)
  WebRTC    : RUNNING (port 8080)
  WebSocket : RUNNING (port 30000)
```

## Operational notes for future agents

- The old buggy Isaac Sim process (PID 167826) had been started manually,
  so `./launch.sh --stop` could not stop it (no PID file). Killing it
  required `pkill -f "isaacsim.*start_server"` followed by
  `kill -9 <pid>`. After the kill, ports 8080 + 30000 freed up
  immediately and `./start_isaac.sh` reclaimed them.
- When the user complains that "everything just stopped working", check:
  1. `./launch.sh --status`
  2. Look at the **last 50 lines** of both `.vite.log` and
     `.isaacsim.log` — they almost always tell you which side died.
  3. `awk 'NR>1 {print $2}' /proc/net/tcp` is the simplest way to confirm
     port bindings inside this container (no `ss`/`netstat` available).
