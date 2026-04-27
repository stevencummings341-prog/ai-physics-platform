# Handoff — 2026-04-27 — Experiment 4 Lab Report Export

## What changed

Experiment 4 (Driven Damped Harmonic Oscillations) gained a one-click
"Generate Lab Report" pipeline. The user clicks the button after running
the experiment in the browser; the backend renders 4 publication-quality
matplotlib figures, computes all six analysis-question answers from the
PASCO ME-8750 manual, packages everything into a ZIP, and ships it back
through the WebSocket. The frontend then offers downloads for the ZIP,
the Markdown report, both CSVs, and the JSON summary — and previews the
plots inline.

The pipeline is independent of live PhysX: it runs RK4 integration in
pure Python so the report is reproducible, fast (under 10 s end-to-end),
and immune to USD/PhysX restarts. The user's currently-set damping is
used as the "lightest" curve so the report's headline numbers reproduce
what they just observed; two heavier multiples (×2.5, ×6) are added so
the resonance figure shows the full broadening trend.

## New / changed files

| File | Purpose |
|------|---------|
| `core/exp4_report.py` (new, ~1100 LOC) | Physics, RK4, damped-sine LM fit, resonance sweep, half-power FWHM, half-amplitude asymmetry, linear-LS sinusoid phase fit, 4 matplotlib figures, formal Markdown report templating, **13-page A4 PDF report (Matplotlib PdfPages)**, ZIP packaging. |
| `core/webrtc_server.py` | Added WS handler `run_exp4_full_experiment` and `_run_exp4_full_experiment` async method. Runs the analysis in an executor, drains progress events, base64-encodes plots/CSVs/JSON/MD/**PDF**/ZIP, ships `exp4_progress` and `exp4_report_ready` messages. |
| `frontend/src/experiments.ts` | Added "Generate Lab Report" button to Exp 4 controls. |
| `frontend/src/components/ExperimentView.tsx` | Added `Exp4ReportData` type with `pdf_b64`, `exp4Progress` / `exp4ReportData` state, WS listeners, reset hooks, a green report-status panel with inline plot previews, and a prominent **Download PDF Report** button alongside ZIP / Markdown / CSVs / JSON. |
| `state/active_context.json` | Bumped `last_updated`, refreshed exp4 notes. |

## Pipeline at a glance

```
WS run_exp4_full_experiment
        │
        ▼
core.exp4_report.run_exp4_full_experiment(out_dir, …)
  1. RK4 ringdown (A=0, ω₀/2 kick, 20 s)        →  fig1_free_oscillation.png
     ↳ damped-sine LM fit  (A, γ, ω, φ, c, R²)
  2. RK4 resonance sweep × 3 damping levels      →  fig2_resonance_curves.png
     ↳ half-power FWHM extraction               →  fig3_phase_lag.png
  3. RK4 phase runs at 0.3 f_res / f_res / 2 f_res
     ↳ linear-LS sinusoid fit ⇒ φ within 0.1°   →  fig4_phase_comparison.png
  4. Markdown report (Intro / Method / Raw Data /
     Analysis / Conclusion / Appendix) with all
     numbers and figure refs                    →  Expt4_Driven_Damped_…_Report.md
  5. 13-page A4 PDF report (Matplotlib PdfPages):
       • Title page
       • 1. Introduction       • 2. Method
       • 3.1 Apparatus table   • 3.2 Free-osc fit table
       • 3.3 Resonance summary • 3.4 Phase runs table
       • Figures 1-4           • 4. Data and Error Analysis
       • 5. Conclusion (with all 6 manual-question answers)
                                                  →  Expt4_Driven_Damped_…_Report.pdf
  6. ZIP                                          →  outputs/expt4_web_<ts>.zip
        │
        ▼
WS exp4_report_ready (base64 plots, CSVs, MD, PDF, JSON, ZIP)
```

## Verification

- `python3 -c "import ast; ast.parse(open('core/exp4_report.py').read())"` ✅
- `npx tsc --noEmit` (frontend) ✅
- End-to-end smoke test (RK4 in pure Python, no Isaac Sim required):
  - `pct_diff_lightest`: **0.004 %** (resonance peak matches f₀)
  - `phase_max_residual_deg`: **0.09°** (LS fit beats cross-correlation)
  - `asymmetry_index_pct`: **+8.8 %** (positive — wider on low-f side, as theory predicts)
  - Phase runs (γ = 0.5 /s):
    - low f (0.318 Hz):   φ_meas = 1.42° / φ_th = 1.42°
    - resonance (1.06 Hz): φ_meas = 89.96° / φ_th = 90.05°
    - high f (2.12 Hz):    φ_meas = 177.18° / φ_th = 177.13°
- PDF generation smoke test:
  - File size: **465 KB**
  - Magic header: `%PDF-1.4` ✅
  - Page count: **13 pages**
  - Pipeline runtime end-to-end: **~10 s**

## Known caveats

- `pct_diff_gamma` from the FWHM extraction shows ~20 % discretisation
  error with the default 18-point sweep grid. This is intrinsic to the
  finite resolution of the resonance scan (a real student running this
  experiment would see similar numbers). Increase `sweep_points` or
  fit Eq. 9 directly with non-linear LS to tighten if needed.
- The PDF report fills `[Student Name]` / `[Student ID]` as placeholders.
  Users edit these before submission (using any PDF editor or by editing
  the Markdown source and regenerating).

## Pending / next steps

- (Optional) wire a `run.py` entry point to call
  `core.exp4_report.run_exp4_full_experiment` directly so batch mode is
  available outside the browser session.
- Replace the FWHM-based γ extraction with a non-linear Eq. 9 fit on
  the densely-sampled resonance curve to remove the ~20 % discretisation
  bias.
- Roll the same pipeline pattern to exp4-style reports for any other
  oscillator experiments that need formal analysis (e.g. exp8 once
  implemented).
