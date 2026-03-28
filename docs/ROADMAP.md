# Roadmap

## Phase 1: Platform Foundation

- Standardize experiment lifecycle through `ExperimentBase`
- Centralize scene, recorder, reporter, and VR bridge utilities
- Normalize configs, outputs, and launcher behavior
- Establish durable agent continuity and versioned instructions

## Phase 2: Experiment Portfolio

- Harden `expt1_angular_momentum`
- Harden `expt7_momentum`
- Add more classical mechanics experiments using the same template
- Expand report templates and validation plots

## Phase 3: Runtime Reliability

- Add stronger smoke-test procedures for Isaac Sim launches
- Validate experiment outputs against theoretical expectations
- Improve logging and failure summaries
- Reduce regressions caused by authored USD physics conflicts

## Phase 4: VR Readiness

- Finalize `reset()` and rerun pathways across experiments
- Route runtime parameter overrides through `core/vr.py`
- Support headset-friendly render timing and controller inputs
- Define operator UX for in-sim experiment control

## Phase 5: AI-Orchestrated Experimentation

- Allow AI agents or NPC-like controllers to select parameters and run experiments
- Persist experiment intents, configs, outputs, and summaries as linked artifacts
- Build report pipelines that connect raw runs to conclusions
- Keep every run reproducible from committed code plus saved config

## Continuous Governance

- Update `docs/PROJECT_STATE.md` when project state changes
- Add ADRs when architecture or process decisions change
- Add handoff notes whenever session continuity would otherwise be lost
- Keep all rule and instruction changes under git version control
