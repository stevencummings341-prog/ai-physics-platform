# Handoff: Experiment 5 Report Export

## Scope

Experiment 5 (Rotational Inertia / Physical Pendulum) now supports
server-side report export from the web UI.

## User Requirement

Use `phy1002/Expt_5_Rotational_Inertia_(Physical_Pendulum).pdf`,
`evaluation.pdf`, and `guideline.pdf` as references.  After a web run,
clicking an export button should generate a PHY1002-style PDF report using
Experiment 5 data, Python-generated plots, and a reusable template.

## Implementation

- `core/exp5_report.py`
  - Pure Python report generator, independent of Isaac Sim imports.
  - Cleans the recorded time-series data.
  - Estimates the period from positive-going zero crossings of `theta(t)`.
  - Computes:
    - `T_theory = 2*pi*sqrt((L^2/12 + x^2)/(g*x))`
    - `x_min = L/sqrt(12)`
    - `I_cm = m*L^2/12`
    - `I_pivot = I_cm + m*x^2`
    - `I_pivot_from_period = T^2*m*g*x/(4*pi^2)`
    - percent differences and uncertainty-style summary values.
  - Generates:
    - `exp5_raw_timeseries.csv`
    - `exp5_cycle_periods.csv`
    - four PNG plots
    - `Lab_Report_Rotational_Inertia_Physical_Pendulum.pdf`
    - ZIP package.

- `report_templates/expt5_rotational_inertia.md.j2`
  - Markdown template matching the PHY1002 report guideline sections:
    Objective, Theory, Method, Raw Data, Figures, Data/Error Analysis,
    Conclusion, Appendix.

- `core/webrtc_server.py`
  - Adds `self.exp5_samples` and `self.exp5_report_task`.
  - Clears samples when Experiment 5 starts or resets.
  - Records live telemetry samples while Experiment 5 is running.
  - Handles `export_exp5_report` / `run_exp5_report`.
  - Sends progress via `exp5_report_progress`.
  - Sends artifacts via `exp5_report_ready` as base64.

- `frontend/src/experiments.ts`
  - Adds Experiment 5 control button: `Export Lab Report`.

- `frontend/src/components/ExperimentView.tsx`
  - Adds Exp5 report progress/download panel.
  - Automatically downloads the generated PDF when ready.
  - Provides ZIP, raw CSV, cycle-period CSV, and Markdown downloads.

- `frontend/src/services/isaacService.ts`
  - Generalizes custom report message dispatch to `expN_report_progress`
    and `expN_report_ready`.

## Validation

- Python AST parse passed for:
  - `core/webrtc_server.py`
  - `core/exp5_report.py`
- Offline mock-data report generation passed:
  - created PDF/CSV/period CSV/ZIP
  - measured period matched theoretical period for generated sinusoidal data.
- Frontend build passed:
  - `cd frontend && npm run build`

## Usage

1. Enter Experiment 5.
2. Set mass, length, pivot distance, and initial angle.
3. Click `Run Pendulum`.
4. Let the pendulum run for several seconds so at least a few zero crossings
   are recorded.
5. Click `Export Lab Report`.
6. The PDF downloads automatically; additional artifacts are available in the
   report panel.

## Notes

- The report uses the last web run's live telemetry.  It is not a synthetic
  batch-mode experiment.
- The theoretical period curve plot includes a full `T(x)` reference curve
  and highlights the selected run's pivot distance and measured period.
- If the user exports too early, the backend returns a progress message asking
  them to run the pendulum longer.
