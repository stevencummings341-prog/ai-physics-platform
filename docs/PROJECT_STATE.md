# Project State

## Mission

Build a reproducible AI physics experiment platform on a Linux GPU server using Isaac Sim / PhysX, with standardized experiment execution, artifact generation, report output, and future VR interaction.

## Current Status

- Core framework exists under `core/` with experiment lifecycle, scene helpers, recording, reporting, and a VR bridge scaffold.
- `expt1_angular_momentum` is implemented with a visual-model-plus-physics-proxy approach for stability with authored USD assets.
- `expt7_momentum` is implemented with standardized configuration and interactive launch support.
- Persistent agent continuity is now a first-class project requirement through `docs/`, `state/`, `AGENTS.md`, and `.cursor/rules/`.

## Source Of Truth

Read these in order before any substantial task:

1. `docs/PROJECT_STATE.md`
2. `state/active_context.json`
3. `docs/ROADMAP.md`
4. Latest relevant file in `docs/handoff/`
5. Relevant ADRs in `docs/adr/`
6. `AGENTS.md`
7. `.cursor/rules/*.mdc`

## Active Priorities

1. Keep experiment code reproducible and physically defensible.
2. Prevent context loss across new agent sessions.
3. Version all instruction changes, architecture decisions, and handoff updates.
4. Maintain clean separation between framework code, experiment code, generated outputs, and teammate-provided assets.
5. Keep the codebase ready for later VR control and observation workflows.

## Non-Negotiable Operating Rules

- Never rely on chat memory as the only project memory.
- Every substantial architecture or workflow decision must be recorded in `docs/adr/`.
- Every session that changes project direction, workflow, or task ownership must leave a handoff note in `docs/handoff/`.
- Every meaningful project-state update must refresh `state/active_context.json`.
- Rule files and `AGENTS.md` are versioned project assets, not disposable prompts.
- Generated experiment outputs belong under `outputs/` and are not the source of truth for architecture decisions.

## Current Experiment Snapshot

- `expt1_angular_momentum`: implemented, integrated with teammate model loading, still needs more runtime verification inside Isaac Sim.
- `expt7_momentum`: standardized launcher and config flow exist, suitable as the baseline for future experiment templates.

## Immediate Next Steps

1. Use this architecture for all future experiment work and handoffs.
2. When a new experiment starts, add an entry to `docs/experiments/EXPERIMENT_INDEX.md`.
3. When a new decision changes process or structure, add an ADR before broad implementation.
