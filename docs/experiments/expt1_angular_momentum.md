# expt1_angular_momentum

## Goal

Simulate conservation of angular momentum using a teammate-provided apparatus model while preserving stable, controllable physics behavior in Isaac Sim.

## Current Implementation

- Loads the apparatus USD as a visual model
- Disables or avoids embedded authored physics that conflict with the simulation
- Uses hidden proxy rigid bodies for the rotating disk and falling ring
- Synchronizes the visible model to the proxy body poses during simulation

## Known Risks

- Needs more runtime validation for joint behavior and visible motion inside Isaac Sim
- Depends on robust prim discovery inside teammate-authored model hierarchies
- May need more diagnostics when new models or naming conventions are introduced

## Next Work

1. Verify motion and contact timing in live simulation
2. Confirm analysis outputs match expected theoretical trends
3. Improve validation logging around prim discovery and proxy synchronization
