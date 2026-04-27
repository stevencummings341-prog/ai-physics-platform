# 2026-04-27 — Architecture Cleanup

## Summary

Project-wide cleanup pass: collapsed the historical "everything in the
repo root" layout into a single canonical structure, removed dead code,
deduplicated reference PDFs, fixed a broken CLI registry, and synced the
continuity docs with reality.

The runtime behaviour is unchanged. Frontend, Isaac Sim backend, share
tunnel, and VR pipeline all keep working; only stale or duplicate files
were removed. Verified with `python -c "import ast; ast.parse(...)"` for
every Python file, `npx tsc --noEmit` (zero errors), and `npx vite build`
(`✓ built in 9.60s`).

## What changed

### Deleted (dead code / duplicates / caches)

Root-level legacy scripts (all superseded by `core/webrtc_server.py` +
`experiments/exptN_*/sim.py` + the React frontend):

- `expt1_angular_momentum_sim.py` — interactive Python launcher
- `expt2_large_amplitude_pendulum_sim_fixed.py` — old standalone sim
- `expt2_ui.py` — Gradio UI
- `expt6_centripetal_force_physical_sim_2026-04-24_09_45_16.py` — timestamped draft
- `expt6_ui_physical_2026-04-24_09_46_03.py` — Gradio UI for the draft
- `expt7_momentum_sim.py` — old standalone sim
- `expt7_ui.py` — Gradio UI
- `generate_ppt.py` + `AI物理实验平台_项目汇报.pptx` — one-shot PPT generator

Empty / unused packages:

- `server/` — only had a stub `__init__.py`, no imports anywhere
- `utils/` — 4 helper modules, never imported

Duplicate / cached / generated:

- `__pycache__/`, `experiments/__pycache__/`, `experiments/hh.zip`
- `frontend/dist/`, `frontend/vite.config.js` (compiled duplicate of `.ts`),
  `frontend/tsconfig.tsbuildinfo`
- `outputs/` (115 MB of old run artifacts — gitignored, regenerates on demand)
- `launchers/bin/cloudflared` (40 MB — Cloudflare is blocked from this
  cluster's egress; `share.sh` uses bore.pub / localhost.run instead)
- `Expt_3.pdf`, `Expt_4.pdf`, `Expt_8.pdf` (duplicates of `phy1002/`)
- `evaluation.pdf`, `guideline.pdf`, `high.pdf` (duplicates of `standard/`)
- `standard/` (cryptic-hash duplicates of the loose root PDFs)

### Reorganised

- `phy1002/` → `docs/reference/phy1002/`  (lab manuals)
- `实验5/` → `docs/legacy/exp5_classmate_code/`  (preserved teammate work
  after integration into `core/webrtc_server.py`)

### Bugs fixed

1. **`run.py` registry** — `expt7_momentum` was registered to
   `experiments.expt7_momentum.sim`, a module that doesn't exist (the
   folder was deleted at some point). `python run.py expt7_momentum`
   would have ImportError'd. Removed the entry; updated docstring to
   explain that web-only experiments live exclusively in
   `core/webrtc_server.py`.
2. **Dead `CAMERA_SCRIPT_DIR` import** — `core/webrtc_server.py` imported
   it but never used it; the camera presets actually live as
   `_EXP{N}_CAM_*` constants in `webrtc_server.py` itself. Removed both
   the import and the `CAMERA_SCRIPT_DIR` definition in
   `configs/server.py`.
3. **`state/artifact_manifest.json`** still listed
   `expt7_momentum_sim.py` and `expt1_angular_momentum_sim.py` as
   "interactive_launchers"; rewrote the manifest with the real entry
   points (launch.sh, start_isaac.sh, start_server.py, share.sh,
   setup.sh, bootstrap.sh, run.py).
4. **`README.md`** still claimed `python expt7_momentum_sim.py` was a
   supported entry point. Rewrote the whole README to match the actual
   layout and quick-start commands.
5. **`AGENTS.md`** experiment status table marked exp 3/5/6/8 as 🔒
   stub; in reality every experiment is fully implemented. Updated the
   table to reflect web/batch/PDF-report status per experiment.

### Naming consistency

- `frontend/src/components/LabReportPDF.tsx` → `Exp1ReportPDF.tsx` to
  match the `Exp{N}ReportPDF.tsx` pattern of the other six lab-report
  components. Updated the import in `ExperimentView.tsx` and the inline
  comment in `Exp5ReportPDF.tsx`. Component / default-export are
  renamed inside the file too.

### New documentation

- `camera/README.md` — explains that the per-experiment USD camera
  scripts (`usd1.py`–`usd8.py`, `get_camera_params.py`) are dev-time
  Script-Editor helpers only; runtime camera presets live as constants
  in `core/webrtc_server.py`.

### `.gitignore`

Extended to cover the new build/cache files we just removed so they
won't drift back into git: `frontend/tsconfig.tsbuildinfo`,
`frontend/vite.config.js`, `.share/`.

## Final root layout

```
README.md  AGENTS.md  requirements.txt  .gitignore  .cursor/
launch.sh  start_isaac.sh  start_server.py  share.sh  setup.sh  bootstrap.sh  run.py
core/  configs/  frontend/  Experiment/  experiments/  report_templates/
camera/  vr/  launchers/bin/  docs/  state/
outputs/  (gitignored, auto-created)
```

22 entries, every one with a clear single purpose. Down from ~50
including all the loose `expt*.py` scripts, duplicate PDFs, the PPTX,
and the dead `server/` / `utils/` packages.

## Verification

| Check | Result |
|-------|--------|
| `python -c "ast.parse(...)"` on every kept .py | ✅ all OK |
| `python run.py --help` | ✅ shows the 3 batch experiments |
| Grep for removed symbols (CAMERA_SCRIPT_DIR, expt*_ui, expt2_large_amplitude...) | ✅ only in historical handoffs (preserved) |
| `npx tsc --noEmit` in `frontend/` | ✅ zero errors |
| `npx vite build` | ✅ built in 9.60 s, no warnings beyond chunk size |
| `./launch.sh --status` | ✅ Frontend + Isaac Sim + WebRTC + WebSocket all RUNNING |
| Frontend lints (`Exp1ReportPDF.tsx`, `ExperimentView.tsx`) | ✅ no errors |

## Migration notes for future agents

- `phy1002/` is now `docs/reference/phy1002/`. Update any internal links.
- `实验5/` is now `docs/legacy/exp5_classmate_code/`. Reference only;
  the active code is in `core/webrtc_server.py` (procedural PhysX
  physical pendulum scene) and `frontend/src/components/Exp5ReportPDF.tsx`.
- The "interactive Python launcher" pattern (root-level `expt*_sim.py`)
  is dead. All interaction goes through the React frontend → WebSocket →
  `core/webrtc_server.py`. Batch reproducible runs go through
  `python run.py expt{1,2,3}_*`.
- The Gradio UIs (`expt*_ui.py`) are gone. The React frontend in
  `frontend/` is the canonical UI surface.
