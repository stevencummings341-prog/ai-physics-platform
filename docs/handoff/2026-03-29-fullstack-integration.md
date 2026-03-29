# Handoff: Full-Stack Integration Complete

**Date:** 2026-03-29  
**Previous:** 2026-03-28-startup-workflow-upgrade.md

## What Changed

### Architecture
- Integrated senior's `physical-lab` (Y-xvan/physical-lab) frontend + WebRTC server into the project
- New layer: `frontend/` (React 19 + TypeScript + Vite + Tailwind)
- New layer: `core/webrtc_server.py` (WebRTC signaling + WebSocket control/telemetry)
- New layer: `configs/server.py` (centralised config with env-var overrides)
- New layer: `camera/` (per-experiment camera presets from senior's project)
- New entry: `start_server.py` (Isaac Sim Script Editor launcher)
- New entry: `launch.sh` (one-click frontend + instructions)

### What Works Now
- **Exp 1 (Angular Momentum):** Full web interactive — video + sliders + real-time angular velocity chart
- **Exp 2 (Large Pendulum):** Full web interactive — angle + period detection
- **Exp 7 (Momentum Conservation):** Web UI visible and unlocked; server handler is stub (needs USD prim path wiring)
- **Exp 3-6, 8:** Frontend UI exists but locked ("Coming Soon"); server has placeholder handlers

### Key Design Decisions
1. All hardcoded IPs replaced with `frontend/src/config.ts` auto-detection
2. CDN Tailwind removed in favour of PostCSS Tailwind via Vite
3. `pause_simulation` mapped to `stop_simulation` (server has no separate pause)
4. Unimplemented experiments marked `isLocked: true` in experiments.ts

## For Next Agent

### To unlock an experiment:
See `AGENTS.md` → "Adding a New Experiment" — 6-step checklist covering USD, server, frontend, config, docs, and optional batch mode.

### Open items:
- `core/webrtc_server.py` uses guessed USD prim paths for exp3-8 (e.g., `/World/exp3/projectile`) — these must be verified against actual USD structure
- Exp7 batch mode exists (`experiments/expt7_momentum/`) but the WebRTC server handler for exp7 is still a stub
- The `ExperimentBase` batch path and the WebRTC interactive path are independent — no bridge exists yet

### Ports:
- Frontend: 5173
- WebRTC HTTP: 8080 (env: `PHYS_HTTP_PORT`)
- WebSocket: 30000 (env: `PHYS_WS_PORT`)
