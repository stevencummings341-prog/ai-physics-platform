# 2026-03-28 Startup Workflow Upgrade

## Summary

- Added a single startup entry point for fresh agent sessions with `docs/START_HERE.md`.
- Added reusable templates for new-agent startup and session closeout.
- Introduced `docs/handoff/LATEST.md` as the stable pointer for the most relevant handoff.
- Updated rules, state files, and project instructions so the new workflow is part of repository truth.

## Files Touched

- `docs/START_HERE.md`: canonical startup entry point
- `docs/templates/NEW_AGENT_STARTUP_PROMPT.md`: reusable startup prompt
- `docs/templates/SESSION_CLOSEOUT_CHECKLIST.md`: reusable closeout checklist
- `docs/handoff/LATEST.md`: stable handoff pointer
- `docs/adr/ADR-0003-single-entry-startup.md`: rationale for the single-entry model
- `AGENTS.md`, `README.md`, `.cursor/rules/*.mdc`: wired new workflow into instructions
- `state/*.json`: updated machine-readable continuity metadata

## Decisions

- Fresh sessions should begin from one canonical file instead of a loosely described read list.
- The latest relevant handoff should be discoverable through a stable pointer rather than guessed from filenames.
- Startup and closeout should use reusable templates so continuity is not dependent on memory.

## Open Risks

- The system still relies on future sessions updating `LATEST.md` and the continuity files consistently.
- Experiment-specific live validation remains separate from this workflow upgrade.

## Next Actions

1. Use `docs/templates/NEW_AGENT_STARTUP_PROMPT.md` when launching fresh agents.
2. Use `docs/templates/SESSION_CLOSEOUT_CHECKLIST.md` before ending substantial sessions.
3. Keep `docs/handoff/LATEST.md` synchronized with the newest relevant handoff.
