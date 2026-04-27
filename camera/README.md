# Camera helpers (dev-time only)

These scripts are **NOT** invoked at runtime. The actual camera presets used
by the running server live as constants in `core/webrtc_server.py`
(`_EXP{N}_CAM_EYE / TGT / FL`) and are switched by the `_switch_camera()`
method when the user enters an experiment from the React frontend.

## What they're for

- `usd1.py` … `usd8.py` — drop-in snippets you can paste into the Isaac Sim
  **Script Editor** to manually preview / tweak the per-experiment camera
  pose against the live USD stage. They use `omni.usd.get_context()` so they
  only run inside Isaac Sim.
- `get_camera_params.py` — utility that reads the current viewport camera's
  translate, orient quaternion, focal length, and clipping range and prints
  them in the exact format consumed by the runtime presets in
  `core/webrtc_server.py`. Use this to capture a freshly designed camera
  pose, then transcribe the values into the matching `_EXP{N}_CAM_*`
  constants.

## When to use

- Designing a new experiment and need to pick a flattering default camera
  view: position the viewport in the Isaac Sim GUI, run
  `get_camera_params.py`, then copy the output into `core/webrtc_server.py`.
- Re-tuning an existing experiment's camera after the USD scene has been
  redesigned.

## When NOT to use

- Never rely on these scripts in any production code path. If you find
  yourself importing them, you are doing something wrong — every camera
  switch must go through the WebSocket `set_camera` / `enter_experiment`
  command pipeline so the change is visible to all connected browsers.
