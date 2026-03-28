# expt7_momentum

## Goal

Provide a stable, user-friendly linear momentum conservation experiment with standardized configuration, data recording, and report generation.

## Current Implementation

- Unified experiment class under `experiments/expt7_momentum/`
- Interactive launcher with clearer input prompts and direction-aware velocity entry
- Standardized output generation through the shared framework

## Known Risks

- Still needs more full-run validation against expected elastic and inelastic cases
- Future UI or VR control paths may require better real-time parameter override handling

## Next Work

1. Use this experiment as the template for future simpler experiments
2. Add focused validation scenarios for collision direction and conservation metrics
3. Keep launcher ergonomics aligned with the non-interactive `run.py` pathway
