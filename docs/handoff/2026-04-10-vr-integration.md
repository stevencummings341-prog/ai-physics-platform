# 2026-04-10 — VR Hand Tracking Integration

## What was done

Integrated the Meta Quest 3S hand tracking system (from `vr/` directory, by
teammate yuzhixuan) into the main WebRTC server pipeline.

### New files
- `core/vr_hand_receiver.py` — Threaded UDP receiver for Quest hand data.
  Ported from `vr/visionpro_isaaclab_advanced.py` with all Isaac Lab
  dependencies removed.  Features: EMA smoothing, velocity estimation,
  stale-tracking timeout, ACK heartbeat.

### Modified files
- `core/vr.py` — Replaced the empty stub with a full `VRBridge` class that
  creates kinematic hand prims (VisualCuboid, no collision), updates their
  positions each tick, and implements proximity-based grab/release.
- `configs/server.py` — Added `VR_*` configuration constants (port, scale,
  thresholds, prim paths).  All overridable via env vars.
- `core/webrtc_server.py` — Integrated VRBridge:
  - Instantiated in `__init__`, started/stopped in lifecycle.
  - Hand prims created on `enter_experiment`.
  - VR tick + telemetry injected into every telemetry broadcast.
  - New WS commands: `vr_enable`, `vr_disable`, `get_vr_status`.
  - `_vr_graspable_paths()` returns experiment-specific grabbable prims.
- `frontend/src/components/ExperimentView.tsx` — Added `vrConnected` state
  extracted from telemetry `data.vr.vr_connected`; purple "VR" badge in all
  three top-bar variants (exp1, exp7, generic).
- `AGENTS.md`, `docs/PROJECT_STATE.md`, `state/active_context.json` — Updated
  with VR architecture, ports, and current focus.

## What is NOT done yet

1. **Live headset test** — All code is syntax-verified and builds, but has not
   been tested with a real Quest 3S on the LAN.
2. **Experiment-specific VR interactions** — The grab logic is generic
   proximity-based.  Per-experiment actions (e.g., VR hand spins the disk in
   exp1, VR hand pushes a cart in exp7) would need experiment-aware callbacks.
3. **VR-only mode** — The system requires the browser frontend + WebRTC server
   to be running.  A standalone "VR-only" mode (no browser) is not implemented.
4. **Haptic feedback** — No feedback channel to the Quest yet.

## How to test without a Quest

```bash
# Terminal 1: start the server in Isaac Sim Script Editor
exec(open('/125090599/start_server.py').read())

# Terminal 2: simulate Quest hand data
cd /125090599/vr
python3 test_hand_tracking.py --mode circle --host 127.0.0.1 --port 8888
```

The server should log VR hand tracking packets and the frontend should show
the purple "VR" badge.

## Dependencies on `vr/` directory

The `vr/` directory is a **reference** — it contains the Unity C# scripts
(must be built into a Quest APK via Unity), standalone Isaac Lab Python demos,
and comprehensive setup documentation.  The main project does NOT import from
`vr/` at runtime; all needed logic was ported to `core/`.
