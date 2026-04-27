# Handoff — 2026-04-24 — Exp 6 Centripetal Force (PhysX integration)

## Summary

Replaced the exp6 stub with a full-stack PhysX-native centripetal-force
experiment.  The motion is **integrated by PhysX**, not calculated from
`F = m·ω²·r`.  The measured centripetal force is the real spring force
PhysX applies to keep the bob in circular motion.

Drop-in based on the classmate's `expt6_centripetal_force_physical_sim.py`
(RK4 spring-damper model), but reimplemented as a procedural USD scene
with a USD PrismaticJoint + linear DriveAPI so PhysX handles the
integration instead of Python RK4.  The classmate's gradio UI is
superseded by the existing React web frontend (`frontend/src/experiments.ts`).

## Physical model

Rotating apparatus:

* **Rotor** — kinematic Xform at origin.  Spun about +Z by an asyncio
  pose-driver task (`_run_exp6_rotor_loop`, 240 Hz) with a linear ω ramp
  over `EXP6_DEFAULT_RAMP_TIME = 1.2 s` to avoid impulsive drive jitter.
* **Bob** — dynamic rigid body (30 g by default) sitting on a
  frictionless horizontal table (gravity ON, normal force supports it).
  Z-translation and X/Y-rotation are locked so gravity cannot introduce
  tipping noise.
* **Prismatic joint** between rotor (body0) and bob (body1) along
  rotor-local X.  Linear DriveAPI (`type=force`, `stiffness=k`,
  `damping=c`, `target=r_target`) models the elastic tether.

Because the joint's frame is anchored to the rotor, the spring axis
rotates with the rotor.  PhysX integrates the bob as the constraint
frame changes — centrifugal tendency stretches the spring until

`k · (r_actual − r_target) = m · v_tan² / r_actual`

at steady state.  This is the real physics — the bob's radius and speed
come from PhysX's integrator, not from an analytic formula.

## Telemetry

Key UI outputs, all derived from PhysX-measured state:

| field | meaning |
|-------|---------|
| `centripetal_force` | `k · (r_actual − r_target)` — real spring force |
| `force_theory` | `m · ω_target² · r_target` — analytic reference |
| `force_kinematic` | `m · v_tan² / r_actual` — cross-check from PhysX v & r |
| `radius_actual` | `√(x² + y²)` of the bob |
| `speed` | `√(vx² + vy²)` from dynamic_control |
| `spring_extension` | `r_actual − r_target` |
| `omega_critical` | `√(k / m)` — above this, the drive cannot hold the bob |

A discrepancy between `centripetal_force` and `force_theory` indicates
transient motion, overshoot, or an under-stiff spring.  In steady state
they agree to <1 % for k ≥ 200 N/m, m ≤ 0.1 kg, ω ≤ 8 rad/s.

## Files changed

* `configs/server.py` — `EXP6_*` constants (paths, defaults, solver
  iter counts, ramp time, table geometry).
* `core/webrtc_server.py` — added:
  * `EXP6_*` imports.
  * Full state in `__init__`.
  * `set_exp6_mass | set_exp6_radius | set_exp6_omega |
    set_exp6_spring_k | set_exp6_damper` message handlers (with
    backward-compatible `set_mass | set_radius | set_angular_velocity`
    aliases).
  * Routing for `start_simulation`, `stop_simulation`, `reset`,
    `enter_experiment` when `experiment_id = "6"`.
  * `_setup_exp6_scene`, `_start_exp6_sim`, `_reset_exp6`,
    `_apply_exp6_spring_params`, `_run_exp6_rotor_loop`,
    `_read_exp6_state`, `_exp6_update_spring_visual`,
    `_force_exp6_camera`, `_deferred_exp6_camera`, plus `_exp6_make_*`
    helpers.
  * Exp 6 preset in `_switch_camera`.
  * Exp 6 branch in `_telemetry_loop`.
* `frontend/src/experiments.ts` — unlocked exp 6, new controls/chart
  configuration matching the server commands.
* `camera/usd6.py` — camera preset updated to match the procedural
  scene (eye ≈ (0.95, −0.95, 1.40), target ≈ (0, 0, 0.75)).
* `docs/PROJECT_STATE.md` — exp 6 row promoted to "full".
* `state/active_context.json` — status, focus, risks refreshed.

## Verification done

* `python3 -c "import ast; ast.parse(...)"` passes on both edited
  Python files.
* `npx vite build` succeeds (pre-existing tsc warnings in
  `ExperimentView.tsx` and third-party `.d.ts` files are unchanged by
  this work).
* Linter: `ReadLints` clean on all four edited files.

**Not yet verified** (requires a running Isaac Sim session on the RTX
5090 box): actual PhysX behaviour, visual layout, camera pose, live
telemetry values.  Re-run `./launch.sh` + load exp 6 via the web UI
and confirm the spring force matches `m · ω² · r` within a few % at
steady state.

## Follow-up fix (same day) — wrong viewport showing exp1 rig

Reported symptom: opening Experiment 6 displayed the angular-momentum
apparatus instead of the new centripetal-force rig.

Two root causes found and patched:

1. **`load_usd` handlers (HTTP and WebSocket) fell through to
   `DEFAULT_USD_PATH` for experiments 5, 6, and 8**, reloading
   `Experiment/exp.usd` (the unified scene dominated by the exp1
   angular-momentum rig).  If the frontend or any other caller sent
   `load_usd` for exp 6, the procedural PhysX scene would be overwritten.
   Fixed by centralising dispatch in a `procedural_builders` dict —
   experiments 2–8 all now route to their `_setup_expN_scene` coroutine
   regardless of which transport issued the request.

2. **The kinematic rotor rigid body had UsdGeom.Cube visual children**
   (arm, hub, shaft, counter-mass, spring).  On some Isaac Sim / PhysX
   builds, descendant Gprims of a RigidBodyAPI-bearing Xform are
   auto-interpreted as part of the body's collision geometry even
   without CollisionAPI, which can destabilise or silently reject the
   scene.  Restructured to follow exp 4's pattern:
   * `/World/exp6/rotor` — minimal kinematic rigid body, NO visible
     children, sole purpose is body0 of the prismatic joint.
   * `/World/exp6/visual_frame` — plain UsdGeom.Xform (no physics
     schema) that carries the decorative arm/hub/shaft/counter/spring
     cubes.
   * The rotor pose-driver loop now updates BOTH rotate ops with the
     same angle each tick, so the visual rig stays perfectly
     synchronised with the physics rotor.

New config symbol: `EXP6_VISUAL_FRAME_PATH = "/World/exp6/visual_frame"`.
All `EXP6_*_VISUAL_PATH` constants were retargeted to live under this
sibling Xform.

New server attribute: `self.exp6_visual_rotate_op` — cached RotateZOp
on the visual frame, set by `_exp6_make_visual_frame`.

## Follow-up — formal report export (2026-04-27)

Added one-click Experiment 6 lab-report export based on:

* `phy1002/Expt_6_Centripetal_Force.pdf`
* `evaluation.pdf`
* `guideline.pdf`
* the existing experiment-1 report UX and experiment-2 backend
  Python-plot workflow.

Implementation details:

* `core/webrtc_server.py`
  * Added `self.exp6_samples`, filled by the Exp 6 telemetry branch while
    the experiment is running.  Each sample stores PhysX-derived time,
    bob position, actual radius, speed, live omega, spring extension,
    measured spring force, theoretical reference, kinematic force from
    measured `v,r`, and error percent.
  * Added WebSocket command `export_exp6_report` (alias
    `run_exp6_report`).
  * Added `_generate_exp6_report(ws)`, which:
    * writes `exp6_raw_timeseries.csv`;
    * uses Python/Matplotlib to generate:
      `exp6_timeseries.png`, `exp6_force_compare.png`,
      `exp6_orbit.png`, `exp6_error.png`;
    * renders Markdown from
      `report_templates/expt6_centripetal_force.md.j2`;
    * builds `Lab_Report_Centripetal_Force.pdf` directly with
      Matplotlib `PdfPages`, so no pandoc/Word/browser screenshot is
      required;
    * packages all artifacts into a ZIP and sends PDF/CSV/Markdown/ZIP
      as base64 in `exp6_report_ready`.
* `frontend/src/experiments.ts`
  * Added Exp 6 button: `Export Lab Report (PDF)`, command
    `export_exp6_report`.
* `frontend/src/components/ExperimentView.tsx`
  * Added Exp 6 report progress state.
  * On `exp6_report_ready`, automatically downloads the generated PDF.
  * Shows a right-panel "Exp6 Report Generated" card with PDF, ZIP, CSV,
    and Markdown download buttons.
* `report_templates/expt6_centripetal_force.md.j2`
  * New English report template with Objective, Theory, Method, Raw
    Data, Figures, Data/Error Analysis, Conclusion, and Appendix.
  * Answers all five conclusion questions from the Exp 6 manual.

Report content and grading alignment:

* PDF only, English only.
* No screenshots for tables; raw data are exported as CSV and summary
  data are typeset in the PDF table.
* All Python plots include axis labels, units, titles, and captions in
  the PDF.
* Uses steady-state data after the initial ramp for analysis and keeps
  transient data in the raw CSV/plots.
* Error analysis includes simulated sensor uncertainties and propagated
  force uncertainty through `F = m v^2 / r`.

### Styling upgrade (2026-04-27)

The first exported PDF was functionally correct but visually plain because
it was assembled entirely with Matplotlib `PdfPages`.  It has now been
upgraded to match the Experiment 1 report style:

* Backend still performs the required Python work:
  * records PhysX telemetry,
  * writes CSV,
  * draws all figures with Matplotlib,
  * packages ZIP/Markdown/backend PDF.
* Backend additionally returns `plots.timeseries`,
  `plots.force_compare`, `plots.orbit`, and `plots.error` as base64 data
  URLs in `exp6_report_ready`.
* Frontend adds `frontend/src/components/Exp6ReportPDF.tsx`, a
  `@react-pdf/renderer` report component using the same visual language
  as Experiment 1/2:
  * CUHKSZ cover page,
  * Times-style typography,
  * fixed page headers,
  * formal numbered sections,
  * typeset equations,
  * table borders,
  * figure captions and page numbers.
* `ExperimentView.tsx` now automatically downloads the styled React PDF
  after `exp6_report_ready`.  The old backend `PdfPages` PDF remains
  available as a `Backend PDF` fallback button, while `Styled PDF` is the
  primary user-facing download.

## Follow-ups

* If the bob oscillates too much at start, increase `EXP6_DEFAULT_RAMP_TIME`.
* If ω approaches √(k/m) the bob flies to the outer joint limit — UI
  exposes `omega_critical` so users can see why.
* Optional batch mode: port the classmate's sweep (mass / ω / r) into
  `experiments/expt6_centripetal/sim.py` using the same PhysX scene,
  sampling telemetry to a DataFrame + Jinja2 report.
