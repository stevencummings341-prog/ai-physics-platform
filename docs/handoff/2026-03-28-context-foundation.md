# 2026-03-28 Context Foundation

## Summary

- Established a durable project continuity architecture so new agents can resume work without depending on prior chat context.
- Added `docs/`, `state/`, ADRs, experiment index files, and new persistent Cursor rules for startup and handoff discipline.
- Formalized versioned instruction management through repository files instead of transient prompts.

## Files Touched

- `docs/PROJECT_STATE.md`: current mission, priorities, and read order
- `docs/ROADMAP.md`: project phases and continuous governance
- `docs/adr/ADR-0001-context-truth.md`: four layers of truth
- `docs/adr/ADR-0002-versioned-instructions.md`: versioned instruction policy
- `docs/experiments/*`: experiment registry and per-experiment notes
- `state/active_context.json`: machine-readable project state for new agents
- `state/artifact_manifest.json`: mapping of continuity artifacts
- `AGENTS.md`: updated agent operating protocol
- `.cursor/rules/project.mdc`: project-level continuity references
- `.cursor/rules/context-handoff.mdc`: always-apply startup and shutdown rule
- `README.md`: documented the continuity architecture

## Decisions

- Repository files, not chat memory, are the durable source of project context.
- Every future architecture or process change should be recorded via ADR plus state update.
- Every substantial session should leave a handoff note when continuity would otherwise be lost.

## Open Risks

- The continuity system only works if future sessions keep it updated.
- Runtime verification for Isaac Sim experiments is still needed beyond architecture setup.
- Experiment outputs are still mostly manual artifacts; future work may need stronger run indexing.

## Next Actions

1. Use the new startup read order before any new experiment or major refactor.
2. Update `state/active_context.json` and add a handoff note at the end of substantial future sessions.
3. Commit related instruction and state changes together with the code changes they govern.
