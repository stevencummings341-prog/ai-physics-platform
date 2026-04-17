# Handoff — Experiment 4: Driven Damped Harmonic Oscillations (2026-04-17)

## Summary

Experiment 4 is now fully interactive end-to-end. An aluminium disk is mounted on a kinematic pivot through a Z-axis `RevoluteJoint`. The joint carries a `UsdPhysics.DriveAPI` (type `force`) that supplies the torsional spring (`stiffness = κ`) and the magnetic damper (`damping = b`). A lightweight async task updates `targetPosition = A·sin(2π·f·t)` at 120 Hz, so PhysX integrates the full equation of motion

```
I·θ̈ + b·θ̇ + κ·θ = κ·A·sin(ω_d·t)
```

at its native 240 Hz sub-step rate. No analytical shortcut is used for the motion — the resonance curve and phase lag emerge from PhysX.

## What changed

- `configs/server.py` — added `EXP4_*` USD paths and default physics parameters (κ, γ=b/I, A, f, disk mass/radius/thickness, pivot height, solver iteration counts, driver update rate).
- `core/webrtc_server.py`:
  - Imports the new `EXP4_*` constants.
  - `__init__`: full set of `self.exp4_*` state variables (κ, γ, A, f, disk geometry, phase, peak |θ|, driver task handle, cached USD attrs).
  - `_handle_ws_message`:
    - `start_simulation` → `_start_exp4_sim`
    - `stop_simulation` → cancels driver task, phase="stopped"
    - `reset` → `_reset_exp4`
    - `load_usd` / `enter_experiment` → `_setup_exp4_scene`
    - New typed setters: `set_exp4_frequency`, `set_exp4_damping`, `set_exp4_spring`, `set_exp4_drive_amplitude` (with `set_damping`/`set_frequency` kept as legacy aliases).
    - New command `exp4_free_oscillation` → `_start_exp4_free_oscillation` (kicks the disk with an initial ω, drive amp = 0, so the ringdown measures ω₀ directly).
  - New scene + physics logic:
    - `_setup_exp4_scene` — procedurally builds ground/grid, support stand, kinematic pivot, dynamic disk, visual driver arm, decorative springs/magnet; attaches joint + drive + frictionless material.
    - `_exp4_make_disk` — `DynamicCuboid` with an explicit `MassAPI.CreateDiagonalInertiaAttr` to enforce I_z = ½MR² (thin-disk).
    - `_exp4_make_joint` — Z-axis `RevoluteJoint` with `DriveAPI(angular, force)`; stiffness/damping scaled by π/180 because USD revolute drives operate in degrees.
    - `_apply_exp4_drive_params`, `_start_exp4_sim`, `_start_exp4_free_oscillation`, `_reset_exp4`, `_run_exp4_drive_loop`, `_read_exp4_state`, `_exp4_update_peak`.
    - Analytical companions (shown on UI, never fed back to PhysX): `_exp4_natural_freq_hz`, `_exp4_Q`, `_exp4_theory_amplitude`, `_exp4_theory_phase_deg`.
  - Camera preset `_EXP4_CAM_EYE/TGT/FL` + `_force_exp4_camera` + `_deferred_exp4_camera` wired through `_switch_camera`.
  - `_telemetry_loop` exp-4 branch streams live θ/ω, driver angle, peak amplitude, kinetic/potential energy, plus theoretical references (f₀, f_d, Q, phase lag, closed-form amplitude).
- `frontend/src/experiments.ts` — unlocked exp-04, new description, four sliders (f / γ / A / κ), three buttons (Start Driver / Free Oscillation / Reset), chart config (θ, θ_d on left axis, ω on right), six extra metrics (peak |θ|, theory |θ₀|, f₀, f_d, φ, Q).

## How to run

1. Start the frontend: `cd /125090599 && ./launch.sh` (→ http://<IP>:5173).
2. Start Isaac Sim and run in the Script Editor:
   ```
   exec(open('/125090599/start_server.py').read())
   ```
3. Open the UI, pick **Experiment 4**. The scene is built procedurally; no USD file needed.
4. Click **Start Driver** and sweep *Drive Frequency f* across the natural frequency f₀ (shown in extra metrics) — the peak |θ| curve traces the resonance peak; the Disk θ trace develops a visible phase lag w.r.t. the Driver θ_d trace.
5. Click **Free Oscillation** to measure ω₀: the drive switches off and the disk is given an initial angular kick so its ringdown period = 2π/√(ω₀² − γ²/4).

## Key physics notes

- **DriveAPI units.** Revolute `DriveAPI` uses degrees for position and deg/s for velocity, so `stiffness_usd = κ · π/180` and `damping_usd = b · π/180`. The driver target is pushed in degrees.
- **Disk inertia.** A plain `DynamicCuboid` of side 2R has I_zz = (2/3)MR², 33 % too large for a disk. `MassAPI.CreateDiagonalInertiaAttr` sets `(¼MR² + M·t²/12, ¼MR² + M·t²/12, ½MR²)` so PhysX treats the body as a thin disk.
- **Body-level damping OFF.** `PhysxRigidBodyAPI.CreateAngularDampingAttr(0.0)` — all damping must come from the joint drive to stay faithful to the magnetic-brake model in the PDF.
- **Free oscillation** sets the drive amp to zero but keeps the spring and damping on, so the ringdown exactly obeys the homogeneous equation.

## Validation performed

- `configs/server.py` — re-reviewed EXP4 constants block.
- `core/webrtc_server.py` — reviewed imports, state init, all dispatcher branches, scene builder, drive loop, read-state, telemetry block, camera preset.
- `frontend/src/experiments.ts` — exp-04 entry visible, `isLocked: false`, command IDs match backend dispatcher.

Runtime validation (frame-rate, resonance peak shape, Q-factor curve) should be done in Isaac Sim with the browser attached; follow the "How to run" section above.

## Follow-ups (not blocking)

- Optional: add a batch-mode `experiments/expt4_driven_damped/` sweep that scans f across (0.2, 3.0) Hz and produces a resonance-curve plot + Markdown report (mirrors the exp7 / exp3 pattern).
- Optional: tune `EXP4_DRIVER_UPDATE_HZ` after real-hardware testing — 120 Hz is a safe default, but 240 Hz matches PhysX sub-stepping and may smooth the driver arm.
