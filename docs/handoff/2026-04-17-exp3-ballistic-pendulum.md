# Handoff — 2026-04-17 — Experiment 3 (Ballistic Pendulum) integrated

## Context

Experiment 3 (Ballistic Pendulum, replicating PASCO EX-5511 from `Expt_3.pdf`)
has moved from "stub" → "full". Both the web-interactive path
(`core/webrtc_server.py`) and the batch CLI path (`run.py expt3_ballistic_pendulum`)
are online. The entire physics is PhysX-driven — no analytical formula is used
during the live simulation; the ballistic-pendulum formula is applied only
post-sim to derive `v₀_measured` from `θₘₐₓ` and verify the canonical
momentum + energy conservation relation.

## What shipped

### Backend
- **`configs/server.py`**: new `EXP3_*` constants (paths, masses, rod length,
  geometry, solver iteration counts, warmup/settle timings).
- **`core/webrtc_server.py`**:
  - `exp3_*` state variables: `ball_mass`, `pend_mass`, `v0`, `L`,
    `phase` (`idle → firing → swinging → settled`), live `theta`, `omega`,
    `theta_max`, `v0_measured`, auto-settle deadline.
  - `_setup_exp3_scene`: procedural scene builder — kinematic pivot cube,
    compound pendulum body (rod + back/left/right/floor/top walls forming a
    cup that traps the ball by geometry), Y-axis revolute joint, ball
    DynamicCuboid, zero-restitution + high-friction PhysicsMaterials,
    visual floor/grid/support-stand/launcher decoration.
  - `_fire_exp3_ball`: reset poses, warm up, then apply the v₀ muzzle
    velocity through `dynamic_control` and let PhysX evolve the contact.
  - `_reset_exp3`: return the pendulum to vertical and the ball to the
    spawn point without rebuilding the stage.
  - `_read_exp3_pendulum_state`, `_read_exp3_ball_speed`,
    `_exp3_update_swing_metrics`, `_exp3_compute_v0`: live state readback
    and the post-collision apex detector (ω zero-crossing) that snapshots
    `v₀_measured`.
  - Camera preset + deferred re-apply (`_force_exp3_camera`,
    `_deferred_exp3_camera`), wired into `_switch_camera` presets.
  - New WebSocket commands: `set_ball_mass`, `set_pend_mass`, `set_exp3_v0`,
    `set_exp3_L`; legacy `set_projectile_mass` / `set_pendulum_mass` still
    accepted as aliases.
  - `enter_experiment`, `start_simulation`, `reset`, `load_usd` branches for
    `"3"` wired in; telemetry loop emits θ, ω, ball speed, height, θₘₐₓ,
    v₀_input, v₀_measured, error %, KE in/after, KE loss %, plus legacy
    `velocity` / `energy` keys for older UI builds.

### Frontend
- **`frontend/src/experiments.ts`**: exp3 card unlocked. Four sliders
  (ball mass, pendulum mass, v₀, L), four chart traces (θ, ω, ball speed,
  h) and nine extra metric tiles (θₘₐₓ, hₘₐₓ, v₀_measured, v₀_input,
  v₀_error_%, v_after, KE in / after / loss %).

### Batch CLI
- **`experiments/expt3_ballistic_pendulum/sim.py` + `config.yaml`**: a
  self-contained `ExperimentBase` subclass that builds the same compound
  PhysX scene, sweeps `v0_list` (default 3–7 m/s), records per-trial time
  series, plots swing curves + v₀ formula verification, and writes a
  Markdown lab report.
- **`run.py`**: `EXPERIMENT_REGISTRY` extended with
  `expt3_ballistic_pendulum`.

### Camera
- **`camera/usd3.py`** rewritten from the outdated quadcopter preset to
  match the new procedural scene (−X/−Y three-quarter view on the swing
  plane).

### Docs
- `docs/PROJECT_STATE.md` + `state/active_context.json` updated: exp3 ⇒
  implemented, full web + batch + telemetry.

## Physics design rationale

The canonical ballistic-pendulum derivation relies on a *fully inelastic
collision* between the ball and the catcher. We reproduce this in PhysX via:

1. **Compound catcher** — a single rigid body whose colliders form a cup
   opening toward the launcher. Once the ball enters, the back/side/floor
   walls trap it, so the pair must swing together.
2. **Zero restitution, high friction** on both the ball and the catcher
   material (`static=1.2, dynamic=1.0`, restitution=0) — the ball
   decelerates normal-wise on impact and is held by friction + geometry.
3. **CCD enabled** on both bodies — the ball moves fast enough (up to
   ~8 m/s) to tunnel through thin walls without continuous-collision
   detection.
4. **High solver iteration counts** (`pos=96, vel=48`) to keep contact
   impulses accurate.
5. **Explicit CoM** on the pendulum parent at the catcher centre and
   `rod_length` as the joint-to-CoM distance `L`, so the theoretical
   formula `v₀ = (m_ball+m_pend)/m_ball · √(2gL(1−cos θₘₐₓ))` matches the
   simulated geometry to machine precision (up to solver damping).

## How to run

```bash
./launch.sh              # start frontend
# In Isaac Sim Script Editor:
exec(open('/125090599/start_server.py').read())
# Open http://<server-ip>:5173 → pick Experiment 3, adjust sliders, click Fire.

# Or batch mode (headless or GUI):
python run.py expt3_ballistic_pendulum
python run.py expt3_ballistic_pendulum --headless
```

## Follow-ups

- (Optional) Swap the cube ball for a UsdGeom.Sphere — aesthetic only;
  the collision mechanics on a flat back wall are identical.
- (Optional) Add a secondary "photogate" measurement (time-of-flight
  across two line detectors) matching the PDF's verification section.
- (Optional) Sweep over `L` and/or `m_pend` in batch mode to reproduce
  the PDF's uncertainty analysis from multiple trials.
