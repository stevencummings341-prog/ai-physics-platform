# AGENTS.md — AI Physics Experiment Platform

This file provides instructions for AI coding agents (Claude Code, Cursor, Copilot) working on this project.

## Project Overview

A GPU-accelerated physics experiment simulation platform on a university Linux server (NVIDIA RTX 5090). Uses NVIDIA Isaac Sim (`isaacsim` Python API + PhysX 5) to replicate real-world physics experiments with quantitative data collection, automated report generation, and future VR headset integration.

## Directory Layout

```
core/                    → Shared framework (experiment base class, scene utils, data recording, reports, VR bridge)
experiments/             → One sub-package per experiment: exptN_name/ with config.yaml + sim.py + analysis.py
configs/                 → Server-level shared configs
report_templates/        → Jinja2 Markdown templates for auto-generated reports
outputs/                 → Timestamped run output directories (gitignored)
run.py                   → CLI entry point
```

## Experiment Lifecycle

Every experiment follows: **Configure → Build Scene → Warmup → Simulate → Analyze → Report**.

- Subclass `core.experiment_base.ExperimentBase`
- Override: `build_scene()`, `apply_initial_conditions()`, `step_callback(step, t)`, `analyze(df)`, `plot(df)`
- Config from YAML, never hardcoded physics values in Python
- Must support `reset()` for VR re-run without restart

## Mandatory Physics Rules

1. **Gravity ON** (-9.81 m/s²) unless the experiment explicitly studies zero-g.
2. **PhysicsMaterial** on every contact surface — explicit friction and restitution.
3. **VisualCuboid** for decorations (grid lines, labels) — never FixedCuboid.
4. **Decouple render (60 Hz) from physics (240 Hz)**.
5. **Warmup phase** (0.3–1.0 s) after world.reset() before applying velocities.

## Isaac Sim Import Order (CRITICAL)

`SimulationApp` must be instantiated before importing `omni.*` or `pxr.*`.

## Code Standards

- Python 3.10+, type hints on public functions
- English only in code, comments, configs, reports
- numpy arrays for all physics vectors
- No blocking `input()` in simulation code — CLI prompts in `run.py` only
- `plt.close(fig)` after saving plots
- Use `logging` module, not print-debugging

## Adding a New Experiment

1. Create `experiments/exptN_name/` with `__init__.py`, `config.yaml`, `sim.py`, `analysis.py`
2. Subclass `ExperimentBase` in `sim.py`
3. Add a Jinja2 template in `report_templates/exptN_name.md.j2`
4. Register in `run.py` CLI

## VR Integration (Future)

- All experiments class-based with `reset()` / `run()` / `shutdown()`
- VR streaming via Omniverse LiveStream / CloudXR extension
- Controller input → config overrides via `core/vr.py` bridge
- Target: render_dt = 1/90 for VR headset refresh rate
