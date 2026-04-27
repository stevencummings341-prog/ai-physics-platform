# Handoff: Experiment 5 Report Redesign (matches Exp1 PDF look)

## Why

The earlier Experiment 5 export shipped a Python-side `PdfPages` PDF
(matplotlib `text_page` / `table_page` / `image_page`).  The user's
verdict: it was ugly and did not match the formal PHY1002 layout produced
for Experiment 1 (`LabReportPDF.tsx`, `@react-pdf/renderer`, Times Roman,
LaTeX equations, horizontal-line tables, cover page, headers and page
numbers).

This handoff documents the redesign so future agents do not regress to
the matplotlib PDF approach.

## Decision

Mirror Experiment 1's pipeline exactly:

- Backend (Isaac Sim) only produces **data** + Python/Matplotlib PNG
  figures + CSV / Markdown / ZIP attachments.
- Frontend (`@react-pdf/renderer`) composes the **PDF** in the browser,
  re-using the same styles, table component, header, page numbers, cover
  page and `MathEquation` helper as `LabReportPDF.tsx` (Exp1) and
  `Exp7ReportPDF.tsx`.

This guarantees the Exp5 report has the same look-and-feel as Exp1.

## Files

### Backend
- `core/exp5_report.py`
  - Now writes **only** four PNG figures + raw CSV + cycle-period CSV +
    Markdown sidecar + ZIP archive.
  - The Python `PdfPages` block has been removed; do not re-add it.
- `core/webrtc_server.py::_generate_exp5_report`
  - Sends a `pdf_b64`-free payload over `exp5_report_ready`:
    - `summary` (typed by `Exp5Summary` on the frontend)
    - `period_rows`
    - `plots`: `timeseries`, `period_curve`, `inertia`, `cycle_periods`
      as `data:image/png;base64,...`
    - `csv_b64`, `period_csv_b64`, `report_md`, `zip_b64`
  - Sends an immediate `Export request received` progress message so the
    UI never appears stuck.

### Frontend
- `frontend/src/components/Exp5ReportPDF.tsx` (new)
  - Mirrors the Exp1 style block (`paddingTop: 45`, Times-Roman, headers,
    `MathEquation`, horizontal-line `T` table component, page numbers).
  - Sections: Cover -> 1 Introduction -> 2 Objective (theory + purposes)
    -> 3 Methods (setup + procedure) -> 4 Raw Data (parameter table +
    cycle-period table) -> 5 Data and Error Analysis (period analysis +
    inertia analysis + propagated uncertainties + presentation table)
    -> 6 Conclusion (4 questions + summary) -> 7 Appendix (4 figures).
  - Equations rendered as PNGs via `latex.codecogs.com`, exactly like
    Exp1.
- `frontend/src/components/ExperimentView.tsx`
  - On `exp5_report_ready` it now calls
    `pdf(<Exp5ReportPDF data={...}/>).toBlob()` and downloads the result.
  - The Exp5 report panel's "PDF Report" button re-renders the same
    component on demand instead of trying to download `pdf_b64` from the
    backend (which no longer exists).

## Verification

- Python AST parse OK for `core/exp5_report.py` and
  `core/webrtc_server.py`.
- Frontend `tsc --noEmit && vite build` passes.
- End-to-end smoke test with the live WebSocket:
  - Enter Experiment 5
  - Run for ~8 s -> 455 telemetry samples recorded
  - Send `export_exp5_report`
  - Server returns `summary` + `period_rows` + 4 base64 PNG plots, no
    `pdf_b64`.
- Direct `Exp5ReportPDF` render via `@react-pdf/renderer` `renderToFile`
  succeeds with realistic mock data, producing a 77 KB multi-page PDF.

## Future maintenance

- Do not generate a Python `PdfPages` PDF for any experiment that already
  has a frontend `@react-pdf/renderer` template; it never matches the
  formal lab-report look.
- For new experiments, copy `Exp5ReportPDF.tsx`'s skeleton (cover,
  sections, `MathEquation`, `T` table, header, page numbers) and only
  swap in the experiment-specific equations, tables, and figures.
- Keep the backend response shape (`summary`, `period_rows`, `plots`,
  `csv_b64`, `period_csv_b64`, `report_md`, `zip_b64`) so the frontend
  PDF component stays decoupled from backend changes.
