# Project State

## Mission

Build a full-stack physics experiment platform: Isaac Sim simulation backend + React web frontend for real-time interactive physics experiments, with WebRTC video streaming, automated data collection, and future VR integration.

## Architecture (as of 2026-03-29)

```
┌─────────────────────────────────────────────────────────┐
│  Browser (React + TypeScript + Vite + Tailwind)         │
│  frontend/src/                                          │
│  ├── experiments.ts        8 experiment UI definitions   │
│  ├── services/isaacService.ts  WebSocket client         │
│  └── components/                                         │
│      ├── Landing.tsx       Animated splash page          │
│      ├── LevelSelect.tsx   Experiment grid selector      │
│      ├── ExperimentView.tsx Controls + charts + video    │
│      └── WebRTCIsaacViewer.tsx  Live video stream        │
└────────┬──────────────────┬─────────────────────────────┘
         │ WebSocket :30000 │ WebRTC :8080
┌────────┴──────────────────┴─────────────────────────────┐
│  Isaac Sim Python Runtime                                │
│  core/webrtc_server.py     All-in-one server             │
│  configs/server.py         Centralised configuration     │
│  start_server.py           Isaac Sim Script Editor entry  │
│  camera/usd1-8.py          Per-experiment camera presets  │
└────────┬────────────────────────────────────────────────┘
         │ PhysX 5 / USD
┌────────┴────────────────────────────────────────────────┐
│  Experiment/exp.usd        Unified scene (exp1-8 assets) │
│  experiments/               ExperimentBase subclasses     │
│  core/                      Framework (scene, recorder…)  │
└─────────────────────────────────────────────────────────┘
```

**Two parallel experiment paths:**

1. **Web interactive** (`core/webrtc_server.py`): real-time control from browser, live video + telemetry.
2. **Batch CLI** (`run.py` → `ExperimentBase`): offline data collection, analysis, PDF reports.

## Experiment Implementation Status

| # | Name | USD | Web UI | Server handlers | Batch (ExperimentBase) |
|---|------|-----|--------|-----------------|----------------------|
| 1 | Angular Momentum | ✅ | ✅ | ✅ full telemetry | ✅ sim.py + analysis |
| 2 | Large Pendulum | ✅ | ✅ | ✅ full telemetry | ❌ |
| 3 | Ballistic Pendulum | ✅ asset | ✅ locked | ✅ stub | ❌ |
| 4 | Driven Damped Oscillation | ✅ asset | ✅ locked | ✅ stub | ❌ |
| 5 | Rotational Inertia | ✅ asset | ✅ locked | ✅ stub | ❌ |
| 6 | Centripetal Force | ✅ asset | ✅ locked | ✅ stub | ❌ |
| 7 | Momentum Conservation | ✅ procedural | ✅ full | ✅ full telemetry | ✅ sim.py + analysis |
| 8 | Resonance Air Column | ✅ asset | ✅ locked | ✅ stub | ❌ |

**"stub"** = WebSocket command handler exists, camera preset set, telemetry channel open; but USD prim paths may need adjustment once the experiment physics is built.

## Ports and Services

| Service | Port | Protocol | Config key |
|---------|------|----------|------------|
| Frontend dev server | 5173 | HTTP | `vite.config.ts` |
| WebRTC signaling + camera | 8080 | HTTP POST | `PHYS_HTTP_PORT` |
| WebSocket control + telemetry | 30000 | WS | `PHYS_WS_PORT` |

All overridable via environment variables or `configs/server.py`.

## Source Of Truth

Read these in order before any substantial task:

1. `docs/START_HERE.md`
2. `docs/PROJECT_STATE.md` (this file)
3. `state/active_context.json`
4. `docs/ROADMAP.md`
5. `docs/handoff/LATEST.md`
6. Relevant ADRs in `docs/adr/`
7. `AGENTS.md`
8. `.cursor/rules/*.mdc`

## Active Priorities

1. **Implement remaining experiments** (3-6, 8) — USD physics + server telemetry + unlock in frontend.
2. Keep experiments reproducible and physically defensible.
3. Prevent context loss across agent sessions.
4. Version all instruction changes and architecture decisions.

## Quick Start

```bash
./launch.sh              # installs deps + starts frontend
# Then in Isaac Sim Script Editor:
exec(open('start_server.py').read())
```
