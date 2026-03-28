# ADR-0002: Version Global Instructions In Repository

## Status

Accepted

## Date

2026-03-28

## Context

This project depends on persistent operational guidance for AI agents. Unversioned prompts or ad hoc notes make it easy for new agents to miss conventions, repeat mistakes, or regress architecture decisions.

## Decision

Project-wide AI instructions must live in versioned repository files:

- `AGENTS.md` for shared project instructions
- `.cursor/rules/*.mdc` for persistent Cursor rules
- `docs/PROJECT_STATE.md` for current project snapshot
- `docs/handoff/` for session continuity

Instruction updates are treated like normal engineering changes and should be committed with the related code or process update.

## Consequences

- Rule changes are auditable and reversible through git history.
- New agents inherit consistent behavior by reading repository truth instead of stale chat memory.
- Project process evolves as code evolves rather than drifting out of sync.
