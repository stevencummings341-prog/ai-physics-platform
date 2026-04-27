# AI Physics Experiment Platform

Full-stack physics laboratory: NVIDIA Isaac Sim (PhysX 5) backend + React 19 web
frontend for interactive control. Live WebRTC video, real-time WebSocket
telemetry, automated lab-report generation, and Meta Quest 3S hand-tracking
support.

## Repository Layout

```text
/125090599
├── README.md                 ← you are here
├── AGENTS.md                 ← rules for AI coding agents (read first)
├── requirements.txt          ← Python deps (Isaac Sim conda env + extras)
│
├── launch.sh                 ← one-click launcher (frontend [+ Isaac Sim])
├── start_isaac.sh            ← Isaac Sim launcher (auto-detects DISPLAY)
├── start_server.py           ← Isaac Sim Script Editor entry point
├── share.sh                  ← public tunnel (bore.pub / localhost.run)
├── setup.sh                  ← one-shot environment install (after container restart)
├── bootstrap.sh              ← SSH key + git config bootstrap
├── run.py                    ← batch CLI for offline ExperimentBase runs
│
├── core/                     ← shared backend framework
│   ├── webrtc_server.py      ← unified WebRTC + WebSocket server
│   ├── experiment_base.py    ← ABC for batch experiments
│   ├── scene.py / recorder.py / reporter.py
│   ├── vr.py / vr_hand_receiver.py
│   ├── exp2_analysis.py      ← shared analysis helpers (used by web + batch)
│   ├── exp4_report.py        ← Exp 4 lab-report data pipeline
│   ├── exp5_report.py        ← Exp 5 lab-report data pipeline
│   └── exp8_analysis.py      ← Exp 8 1-D wave solver
│
├── configs/server.py         ← every runtime constant (env-var overridable)
├── frontend/                 ← React 19 + TypeScript + Vite + Tailwind
├── Experiment/               ← USD scene assets (exp1/-exp8/ + exp.usd)
├── experiments/              ← batch experiment subpackages
│   ├── expt1_angular_momentum/
│   ├── expt2_large_pendulum/
│   └── expt3_ballistic_pendulum/
├── report_templates/         ← Jinja2 Markdown lab-report templates
├── camera/                   ← dev-time camera-pose snippets (NOT runtime)
├── vr/                       ← Meta Quest Unity app + setup docs
├── launchers/bin/            ← share-tunnel binaries (bore)
│
├── docs/                     ← persistent project truth
│   ├── START_HERE.md / PROJECT_STATE.md / ROADMAP.md
│   ├── adr/                  ← architecture decision records
│   ├── handoff/              ← session continuity notes
│   ├── experiments/          ← per-experiment docs
│   ├── templates/            ← startup / closeout templates
│   ├── reference/            ← lab manuals and reference PDFs
│   └── legacy/               ← preserved teammate scripts (post-integration)
│
├── state/                    ← machine-readable agent context
│   ├── active_context.json
│   └── artifact_manifest.json
│
└── outputs/                  ← auto-generated run artifacts (gitignored)
```

## Quick Start

```bash
# After a fresh container, one-shot dependency install:
./setup.sh

# Day-to-day launch (frontend only):
./launch.sh

# Frontend + Isaac Sim backend together:
./launch.sh --all

# Frontend + Isaac Sim + public share URL:
./launch.sh --all --share

# Open the UI:
http://<IP>:5173      # campus LAN
http://localhost:5173 # via Cursor's SSH port forward
```

Inside the Isaac Sim Script Editor (alternate Isaac Sim entry):

```python
exec(open('/125090599/start_server.py').read())
```

## Two Experiment Paths

| Path | Trigger | Stack |
|------|---------|-------|
| Web interactive (primary) | Browser sliders / buttons | `frontend/` ↔ `core/webrtc_server.py` ↔ Isaac Sim |
| Batch CLI (secondary) | `python run.py expt1_angular_momentum` | `run.py` → `experiments/exptN_*/sim.py` → CSV + plots + Markdown |

Currently registered batch experiments: `expt1_angular_momentum`,
`expt2_large_pendulum`, `expt3_ballistic_pendulum`. Web-interactive is
available for all eight.

## Ports

| Service | Port | Override env var |
|---------|------|------------------|
| Frontend (Vite) | 5173 | (vite.config.ts) |
| WebRTC HTTP | 8080 | `PHYS_HTTP_PORT` |
| WebSocket | 30000 | `PHYS_WS_PORT` |
| VR hand-tracking (UDP) | 8888 | `PHYS_VR_PORT` |

## Public Sharing

```bash
./launch.sh --status          # confirm Frontend + WebRTC + WebSocket are RUNNING
./share.sh                    # start bore.pub tunnel, prints public URL
./share.sh --via lhr          # HTTPS variant via localhost.run
./share.sh --status / --url / --stop / --restart
```

The video stream automatically falls back from WebRTC (UDP, blocked by TCP
tunnels) to WS-JPEG after ~8 s; remote viewers see a brief spinner.

## Output Policy

- Every web-driven lab-report export and every `run.py` invocation writes a
  timestamped folder under `outputs/`.
- `outputs/` is gitignored — safe to delete at any time; new runs regenerate.

## Continuity for AI Agents

Read order before any substantial change (see `docs/START_HERE.md`):

1. `docs/START_HERE.md`
2. `docs/PROJECT_STATE.md`
3. `state/active_context.json`
4. `docs/ROADMAP.md`
5. `docs/handoff/LATEST.md`
6. Relevant ADRs in `docs/adr/`
7. `AGENTS.md`
8. `.cursor/rules/*.mdc`

Repository truth wins over chat memory. When architecture, workflow, or
priorities change, update `docs/` and `state/` in the same commit.

## Saving Your Work

- SSH disconnect does **not** delete files.
- Use git for durable history.
- For local backup: `scp` or `rsync` from this server.
