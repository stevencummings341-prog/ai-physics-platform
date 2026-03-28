# ADR-0001: Four Layers Of Project Truth

## Status

Accepted

## Date

2026-03-28

## Context

Chat-only context does not survive reliably across long sessions, agent restarts, or new agents. This project needs continuity across physics work, infrastructure work, VR preparation, and teammate asset integration.

## Decision

The project will persist truth in four layers:

1. Code Truth: committed source code, configs, and templates in the repository.
2. Decision Truth: architecture decision records in `docs/adr/`.
3. Run Truth: machine-readable current state in `state/active_context.json` and artifact mapping in `state/artifact_manifest.json`.
4. Handoff Truth: human-readable session summaries in `docs/handoff/`.

## Consequences

- No important workflow or architecture decision should exist only in chat.
- New agents can reconstruct context by reading a small, ordered set of files.
- State updates become explicit and reviewable in git history.
- The team gains continuity even when working over SSH or across different tools.
