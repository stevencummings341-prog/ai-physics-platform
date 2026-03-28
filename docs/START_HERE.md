# Start Here

This is the single entry point for any new agent session.

## Goal

Reconstruct the current project state from repository truth before making changes.

## Required Read Order

1. `docs/PROJECT_STATE.md`
2. `state/active_context.json`
3. `docs/ROADMAP.md`
4. `docs/handoff/LATEST.md`
5. Relevant ADRs in `docs/adr/`
6. `docs/experiments/EXPERIMENT_INDEX.md`
7. `AGENTS.md`
8. `.cursor/rules/project.mdc`
9. `.cursor/rules/context-handoff.mdc`
10. `.cursor/rules/isaac-sim.mdc`

## Startup Procedure

1. Read the files above in order.
2. Summarize current project state before touching code.
3. Identify the active experiment or subsystem you are changing.
4. Check whether the task implies a new ADR, handoff update, or state update.
5. Only then start code exploration or edits.

## Mandatory Rules

- Repository truth overrides memory from prior chat.
- If the task changes architecture, workflow, or active priorities, update `docs/` and `state/`.
- If the session would be hard to continue later, update `docs/handoff/LATEST.md` and add a dated handoff note.
- Keep these updates in git with the related work.

## Templates

- Startup template: `docs/templates/NEW_AGENT_STARTUP_PROMPT.md`
- Closeout checklist: `docs/templates/SESSION_CLOSEOUT_CHECKLIST.md`
