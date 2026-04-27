# Project State

## Mission

Build a full-stack physics experiment platform: Isaac Sim simulation backend + React web frontend for real-time interactive physics experiments, with WebRTC video streaming, automated data collection, and future VR integration.

## Architecture (as of 2026-04-27 — post-cleanup)

```
┌─────────────────────────────────────────────────────────┐
│  Browser (React 19 + TypeScript + Vite + Tailwind)      │
│  frontend/src/                                          │
│  ├── experiments.ts            8 experiment UI defs     │
│  ├── services/isaacService.ts  WebSocket client         │
│  ├── utils/                    chart helpers            │
│  └── components/                                         │
│      ├── Landing.tsx           Animated splash          │
│      ├── LevelSelect.tsx       Experiment grid          │
│      ├── ExperimentView.tsx    Controls + charts + video│
│      ├── WebRTCIsaacViewer.tsx Live video               │
│      └── Exp{1..7}ReportPDF.tsx   react-pdf lab reports │
└────────┬──────────────────┬─────────────────────────────┘
         │ WebSocket :30000 │ WebRTC :8080  (or WS-JPEG fallback)
┌────────┴──────────────────┴─────────────────────────────┐
│  Isaac Sim Python Runtime                                │
│  start_server.py            Script Editor / standalone   │
│  core/webrtc_server.py      All-in-one server (WS+RTC)   │
│  core/exp{2,4,5,8}_*.py     Analysis & report pipelines  │
│  core/vr*.py                Quest 3S hand tracking       │
│  configs/server.py          Centralised configuration    │
└────────┬────────────────────────────────────────────────┘
         │ PhysX 5 / USD
┌────────┴────────────────────────────────────────────────┐
│  Experiment/exp.usd         Unified scene (exp1-8)       │
│  experiments/exptN_*/       Batch ExperimentBase classes │
│  core/{scene,recorder,reporter,experiment_base}.py       │
│  report_templates/*.md.j2   Markdown templates           │
└─────────────────────────────────────────────────────────┘
```

**Two parallel experiment paths:**

1. **Web interactive** (`core/webrtc_server.py`): real-time control from browser, live video + telemetry.
2. **Batch CLI** (`run.py` → `ExperimentBase`): offline data collection, analysis, PDF reports.

## Experiment Implementation Status

| # | Name | USD | Web UI | Server handlers | Batch CLI | Lab-report PDF |
|---|------|-----|--------|-----------------|-----------|----------------|
| 1 | Angular Momentum | ✅ | ✅ | ✅ full telemetry | ✅ sim.py + analysis | ✅ Exp1ReportPDF.tsx |
| 2 | Large Pendulum | ✅ procedural | ✅ | ✅ full telemetry (RK4) | ✅ sim.py + sweep | ✅ Exp2ReportPDF.tsx |
| 3 | Ballistic Pendulum | ✅ procedural | ✅ | ✅ full telemetry (PhysX compound + joint) | ✅ sim.py + v0 sweep | ✅ Exp3ReportPDF.tsx |
| 4 | Driven Damped Oscillation | ✅ procedural | ✅ | ✅ full + RK4 ringdown analysis | report-only (core/exp4_report.py) | ✅ Exp4ReportPDF.tsx |
| 5 | Rotational Inertia | ✅ procedural | ✅ | ✅ full telemetry + report data | — | ✅ Exp5ReportPDF.tsx |
| 6 | Centripetal Force | ✅ procedural | ✅ | ✅ full telemetry (PhysX prismatic spring) | — | ✅ Exp6ReportPDF.tsx |
| 7 | Momentum Conservation | ✅ procedural | ✅ | ✅ full telemetry | ✅ sim.py + analysis | ✅ Exp7ReportPDF.tsx |
| 8 | Resonance Air Column | ✅ asset | ✅ | ✅ full (1-D wave solver in core/exp8_analysis.py) | — | analysis pipeline only |

All 8 experiments are unlocked in the frontend. Lab-report PDFs render
client-side via `@react-pdf/renderer` in the formal CUHK-Shenzhen PHY1002
layout (cover page, codecogs LaTeX, academic tables, running header,
page numbers).

## Ports and Services

| Service | Port | Protocol | Config key |
|---------|------|----------|------------|
| Frontend dev server | 5173 | HTTP | `vite.config.ts` |
| WebRTC signaling + camera | 8080 | HTTP POST | `PHYS_HTTP_PORT` |
| WebSocket control + telemetry | 30000 | WS | `PHYS_WS_PORT` |

| VR Hand Tracking (UDP) | 8888 | UDP | `PHYS_VR_PORT` |

All overridable via environment variables or `configs/server.py`.

## VR Integration

Meta Quest 3S hand tracking is integrated via UDP on port 8888.  The Quest
Unity app sends hand position, rotation and pinch data at 60 Hz.  The
server creates translucent hand prims in the USD scene and supports
proximity-based grab/release of experiment objects.

Key modules: `core/vr_hand_receiver.py`, `core/vr.py`, `vr/` (Quest app code + docs).

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
