# AGENTS.md — AI Physics Experiment Platform

Instructions for AI coding agents working on this project.

## Deep Thinking Protocol

When the user says **"好好思考"** (think deeply), activate the SOTA multi-agent reasoning protocol defined in `.cursor/rules/deep-thinking.mdc`. This triggers a 5-phase process: DECOMPOSE → INVESTIGATE → IMPLEMENT → VERIFY → VALIDATE. No shortcuts. Every assumption must be verified against live data. Every fix must be build-tested before declaring done.

## Project Overview

Full-stack physics experiment platform on a university Linux server (NVIDIA RTX 5090):
- **Backend:** NVIDIA Isaac Sim (isaacsim + PhysX 5) with WebRTC video streaming and WebSocket control
- **Frontend:** React 19 + TypeScript + Vite + Tailwind web UI
- **Launch:** `./launch.sh` starts frontend; `start_server.py` runs inside Isaac Sim

## Directory Layout

```
core/                    → Shared framework
  experiment_base.py     → ABC for batch experiments (configure → run → analyze → report)
  webrtc_server.py       → WebRTC + WebSocket server (runs inside Isaac Sim)
  scene.py, recorder.py  → Scene utils, data recording
  reporter.py            → Jinja2 → Markdown/PDF reports
frontend/                → React web UI
  src/experiments.ts     → Experiment UI definitions (controls, charts, difficulty)
  src/config.ts          → Server URL config (auto-detects or reads .env)
  src/services/          → WebSocket client service
  src/components/        → Landing, LevelSelect, ExperimentView, WebRTCViewer
configs/server.py        → All server config (ports, paths, defaults) — env-var overridable
camera/                  → Per-experiment camera preset scripts (usd1.py–usd8.py)
experiments/             → Batch experiment subpackages (exptN_name/)
Experiment/              → USD scene assets (exp1/–exp8/ + exp.usd)
start_server.py          → Isaac Sim Script Editor entry point
launch.sh                → One-click frontend launcher
run.py                   → CLI batch entry point
docs/                    → Project state, roadmap, ADRs, handoffs
state/                   → Machine-readable context (active_context.json)
```

## Quick Start

```bash
./launch.sh              # install deps + start frontend on :5173
# In Isaac Sim Script Editor:
exec(open('start_server.py').read())
# Open browser: http://<IP>:5173
```

## Agent Startup Protocol

Before any substantial task, read in order:
1. `docs/START_HERE.md`
2. `docs/PROJECT_STATE.md`
3. `state/active_context.json`
4. `docs/ROADMAP.md`
5. `docs/handoff/LATEST.md`
6. `AGENTS.md` (this file)
7. `.cursor/rules/*.mdc`

Repository truth wins over chat memory.

## Two Experiment Paths

### Path A: Web Interactive (primary)
Browser → `frontend/` → WebSocket → `core/webrtc_server.py` → Isaac Sim timeline
- User adjusts sliders → commands sent to server → server applies to USD/PhysX
- Server reads back physics state → sends telemetry → frontend renders charts
- WebRTC streams live viewport video to browser

### Path B: Batch CLI (secondary)
`run.py` → `ExperimentBase` subclass → CSV + plots + Markdown report
- Offline data collection and analysis
- Used for reproducible quantitative results

## Adding a New Experiment (complete checklist)

### Step 1: USD Scene
- Build physics in `Experiment/expN/` (rigid bodies, joints, materials)
- Ensure the experiment is part of the unified `Experiment/exp.usd` stage

### Step 2: Server Backend (`core/webrtc_server.py`)
- Add state variables in `__init__` (e.g., `self.expN_mass = 1.0`)
- Add `elif mtype == "set_whatever":` cases in `_handle_ws_message()`
- Add telemetry readback in `_telemetry_loop()` (`elif self.current_experiment == "N":`)
- Add `_read_*()` helper methods for physics readback (velocity, angle, etc.)
- Add camera preset in `_switch_camera()` presets dict
- If needed, add `_apply_expN_params()` method for USD attribute setup

### Step 3: Frontend (`frontend/src/experiments.ts`)
- Set `isLocked: false` for the experiment
- Adjust `controls` array (slider/button configs with `command` field matching server)
- Adjust `chartConfig` array (telemetry keys matching what server sends)
- Update `description` (remove "Coming Soon")

### Step 4: Config (`configs/server.py`)
- Add any experiment-specific constants (prim paths, defaults)

### Step 5: Documentation
- Update `state/active_context.json` experiment status
- Update `docs/PROJECT_STATE.md` table

### Step 6 (Optional): Batch Mode
- Create `experiments/exptN_name/` with `sim.py`, `config.yaml`, `analysis.py`
- Register in `run.py` EXPERIMENT_REGISTRY

## Current Experiment Status

| # | Name | Web | Batch | Status |
|---|------|-----|-------|--------|
| 1 | Angular Momentum | ✅ | ✅ | Full |
| 2 | Large Pendulum | ✅ | - | Full |
| 3 | Ballistic Pendulum | 🔒 | - | Stub |
| 4 | Driven Damped | 🔒 | - | Stub |
| 5 | Rotational Inertia | 🔒 | - | Stub |
| 6 | Centripetal Force | 🔒 | - | Stub |
| 7 | Momentum Conservation | ✅ | ✅ | Full (procedural scene + telemetry) |
| 8 | Resonance Air Column | 🔒 | - | Stub |

🔒 = UI exists but locked; server handler is placeholder.

## Ports

| Service | Port | Override env var |
|---------|------|-----------------|
| Frontend | 5173 | (vite.config.ts) |
| WebRTC HTTP | 8080 | `PHYS_HTTP_PORT` |
| WebSocket | 30000 | `PHYS_WS_PORT` |

## Mandatory Physics Rules

1. **Gravity ON** (-9.81 m/s²) unless experiment studies zero-g.
2. **PhysicsMaterial** on every contact surface — explicit friction and restitution.
3. **VisualCuboid** for decorations — never FixedCuboid.
4. **Decouple render (60 Hz) from physics (240 Hz)**.
5. **Warmup phase** (0.3–1.0 s) after world.reset() before applying velocities.

## Isaac Sim Import Order (CRITICAL)

`SimulationApp` must be instantiated before importing `omni.*` or `pxr.*`.

## Code Standards

- Python 3.10+, type hints on public functions
- TypeScript strict mode for frontend
- English only in code, comments, configs
- numpy arrays for physics vectors
- No blocking `input()` in simulation code
- `plt.close(fig)` after saving plots
- Use `logging` module, not print-debugging

## Session Close Checklist

1. Update `state/active_context.json` if project status changed
2. Add handoff note in `docs/handoff/` if context needed
3. Update `docs/handoff/LATEST.md` pointer
4. Add ADR if architecture decision changed
5. Commit continuity changes with related code
