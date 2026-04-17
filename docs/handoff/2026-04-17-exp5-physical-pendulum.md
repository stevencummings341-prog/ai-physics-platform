# Handoff — 2026-04-17 — Experiment 5 (Physical Pendulum) integrated

## Context

The teammate's standalone script `实验5/expt5_pendulum_sim.py` was integrated
into the web platform. Experiment 5 moves from "stub" → "full".

## What shipped

- **`configs/server.py`**: added `EXP5_*` constants (paths, defaults, solver
  iterations, geometry).
- **`core/webrtc_server.py`**:
  - Replaced the `exp5_pivot / exp5_angle` stub state with
    `exp5_m, exp5_L, exp5_x, exp5_theta0_deg`, phase tracking, and
    period-measurement buffers.
  - Added `_setup_exp5_scene` — builds ground/grid/pivot/bar/revolute-joint/
    physics-material procedurally (same pattern as exp7).
  - Added `_start_exp5_sim` — applies the current θ₀ as the bar's default
    pose and starts the timeline.
  - Added `_reset_exp5`, `_read_exp5_state`, `_exp5_update_period_measurement`,
    `_exp5_T_theory`, `_exp5_x_min_period`.
  - Added camera preset + deferred re-apply for exp5 (eye on +Y looking at
    the XZ swing plane).
  - New WebSocket message types: `set_exp5_m`, `set_exp5_L`, `set_exp5_x`,
    `set_exp5_theta0`.
  - `enter_experiment` / `start_simulation` / `reset` / telemetry loop
    branches for `"5"` wired in.
- **`frontend/src/experiments.ts`**: exp5 card unlocked with the four
  physics sliders (m, L, x, θ₀), θ–ω chart, and extra metrics
  `period`, `T_theory`, `inertia`, `x_min_period`.
- `state/active_context.json` + `docs/PROJECT_STATE.md` updated.

## Physics deviation vs. the original file

The original script uses a **Z-axis** revolute joint. Under Isaac Sim's
default Z-up gravity, a Z-axis pivot produces **zero torque from gravity**
(the pendulum wouldn't swing). To faithfully implement the formula
`T = 2π √((L²/12 + x²) / (g·x))` that the original code itself uses for
verification, the joint axis was changed to **Y** so the bar swings in the
vertical XZ plane. All other physics (frictionless, high-iteration solver,
mass = `m`, bar scale = `L × t × t`, CM-to-pivot distance = `x`) is
preserved.

## How to run

```bash
./launch.sh              # start frontend
# In Isaac Sim Script Editor:
exec(open('/125090599/start_server.py').read())
# Open http://<server-ip>:5173 → pick Experiment 5.
# Adjust m / L / x / θ₀ sliders → click "Run Pendulum".
```

## Follow-ups

- (Optional) Build a batch-mode `experiments/expt5_rotational_inertia/`
  subpackage that sweeps `x` and regenerates the teammate's Markdown report.
- (Optional) Add a camera preset script `camera/usd5.py` mirroring the
  in-server preset so the batch path uses the same viewpoint.
