# Session Closeout Checklist

Run this before ending any substantial session.

## Update Context

- Refresh `state/active_context.json` if priorities, status, or risks changed
- Update `docs/PROJECT_STATE.md` if the project snapshot changed materially
- Add an ADR in `docs/adr/` if architecture or workflow changed

## Leave Handoff

- Add a dated note in `docs/handoff/` if a future agent would need continuity
- Update `docs/handoff/LATEST.md` to point at the most recent relevant handoff
- List open risks, blockers, and exact next steps

## Version Management

- Keep continuity files in the same commit stream as the related work
- Do not leave important process changes only in chat
- Verify the working tree so unrelated changes are not accidentally bundled
