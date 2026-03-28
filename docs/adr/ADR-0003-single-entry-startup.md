# ADR-0003: Single Entry Point For New Agent Sessions

## Status

Accepted

## Date

2026-03-28

## Context

Even with continuity files in place, new agents can still miss context if the read order is ambiguous or scattered across multiple documents.

## Decision

The canonical startup entry point for fresh sessions is `docs/START_HERE.md`.

It defines:

- the mandatory read order
- the startup procedure
- the continuity rules
- the template files for startup and closeout

`docs/handoff/LATEST.md` becomes the stable pointer to the most relevant recent handoff.

## Consequences

- New agents have a single predictable place to begin.
- Startup behavior becomes easier to standardize across Cursor and Claude-style agents.
- Handoff discovery becomes faster because agents no longer need to guess which dated note is current.
