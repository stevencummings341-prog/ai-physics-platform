# New Agent Startup Prompt

Use or adapt this when starting a fresh agent on the project.

```text
Read the project continuity files first and reconstruct the current state before editing anything.

Required order:
1. docs/START_HERE.md
2. docs/PROJECT_STATE.md
3. state/active_context.json
4. docs/ROADMAP.md
5. docs/handoff/LATEST.md
6. relevant docs/adr/*
7. docs/experiments/EXPERIMENT_INDEX.md
8. AGENTS.md
9. .cursor/rules/project.mdc
10. .cursor/rules/context-handoff.mdc
11. .cursor/rules/isaac-sim.mdc

Then report back with:
- Current project goal
- Active priorities
- Relevant experiments or subsystems
- Risks or open issues
- Exact next implementation step

Do not rely on prior chat as the primary source of truth. Repository files win.
```
