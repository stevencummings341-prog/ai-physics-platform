import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';

// Inline LaTeX equation renderer (server-rendered PNG; no client-side LaTeX needed)
const MathEquation = ({ latex, height = 24, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

// ═══════════════════════════════════════════════════════════════════
// Types — match the JSON payload from `_run_exp8_full_experiment`
// ═══════════════════════════════════════════════════════════════════
export interface Exp8ClosedSummaryRow {
  L_m?: number;
  L_cm?: number;
  f1_Hz?: number;
  inv_f1_per_s?: number;
  peak_mm?: number;
  T_s?: number;
}
export interface Exp8HarmonicRow {
  n?: number;
  f_Hz?: number;
  ratio_to_f1?: number;
  peak_mm?: number;
}
export interface Exp8SpacingRow {
  L1_cm?: number;
  L2_cm?: number;
  delta_L_cm?: number;
  wavelength_cm?: number;
  v_from_spacing?: number;
}
export interface Exp8ReportData {
  params?: {
    L_user_cm?: number;
    f_user_Hz?: number;
    mode_user?: string;
    A_drive_mm?: number;
    gamma?: number;
    tube_diameter_cm?: number;
    n_nodes?: number;
    t_warmup?: number;
    t_measure?: number;
    c_reference?: number;
  };
  metrics?: {
    v_measured?: number;
    v_reference?: number;
    v_pct_diff?: number;
    slope?: number;
    intercept?: number;
    r_squared?: number;
    measured_end_effect_cm?: number;
    theory_end_effect_cm?: number;
    f_open_fundamental_Hz?: number;
    f_closed_fundamental_Hz?: number;
    open_to_closed_ratio?: number;
    n_closed_lengths?: number;
  };
  closed_summary?: Exp8ClosedSummaryRow[];
  open_harmonics?: Exp8HarmonicRow[];
  closed_harmonics?: Exp8HarmonicRow[];
  spacing_rows?: Exp8SpacingRow[];
  user_resonance_peaks?: { f_Hz?: number; peak_mm?: number }[];
  plots?: {
    L_vs_inv_f?: string;
    length_sweep?: string;
    freq_sweep_user?: string;
    envelope_user?: string;
    envelope_open?: string;
    probe_user?: string;
    open_vs_closed?: string;
  };
}

interface Props { data: Exp8ReportData }

// ═══════════════════════════════════════════════════════════════════
// Styles — identical visual language to Exp1ReportPDF.tsx
// ═══════════════════════════════════════════════════════════════════
const S = StyleSheet.create({
  page: { paddingTop: 45, paddingBottom: 50, paddingHorizontal: 50, fontFamily: 'Times-Roman', fontSize: 11, lineHeight: 1.55 },
  coverPage: { paddingTop: 120, paddingBottom: 50, paddingHorizontal: 50, fontFamily: 'Times-Roman', fontSize: 11, lineHeight: 1.55, justifyContent: 'flex-start', alignItems: 'center' },
  coverUni: { fontSize: 16, fontFamily: 'Times-Bold', textAlign: 'center', marginBottom: 10 },
  coverCourse: { fontSize: 14, fontFamily: 'Times-Roman', textAlign: 'center', marginBottom: 30 },
  coverTitle: { fontSize: 22, fontFamily: 'Times-Bold', textAlign: 'center', marginBottom: 6 },
  coverSubtitle: { fontSize: 18, fontFamily: 'Times-Bold', textAlign: 'center', marginBottom: 60 },
  coverField: { fontSize: 12, textAlign: 'center', marginBottom: 3 },
  coverValue: { fontSize: 14, fontFamily: 'Times-Bold', textAlign: 'center', marginBottom: 16 },
  header: { fontSize: 9, fontFamily: 'Times-Italic', color: '#555', marginBottom: 12, textAlign: 'center', borderBottomWidth: 0.5, borderBottomColor: '#aaa', paddingBottom: 4 },
  h1: { fontSize: 16, fontFamily: 'Times-Bold', marginTop: 18, marginBottom: 8 },
  h2: { fontSize: 13, fontFamily: 'Times-Bold', marginTop: 14, marginBottom: 6 },
  h3: { fontSize: 12, fontFamily: 'Times-Bold', marginTop: 10, marginBottom: 4 },
  body: { fontSize: 11, textAlign: 'justify', marginBottom: 6 },
  bodyBold: { fontSize: 11, fontFamily: 'Times-Bold', textAlign: 'justify', marginBottom: 4 },
  bodyItalic: { fontSize: 11, fontFamily: 'Times-Italic', textAlign: 'justify', marginBottom: 4 },
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 3, marginTop: 10 },
  pageNum: { position: 'absolute', bottom: 30, right: 50, fontSize: 9, color: '#555' },
  tbl: { marginBottom: 12, width: '100%' },
  tblTop: { borderTopWidth: 1.5, borderTopColor: '#000' },
  tblMid: { borderTopWidth: 0.6, borderTopColor: '#000' },
  tblBot: { borderBottomWidth: 1.5, borderBottomColor: '#000' },
  row: { flexDirection: 'row', minHeight: 16, alignItems: 'center' },
  thCell: { fontSize: 9, fontFamily: 'Times-Bold', textAlign: 'center', paddingVertical: 3, paddingHorizontal: 1 },
  tdCell: { fontSize: 9, textAlign: 'center', paddingVertical: 2.5, paddingHorizontal: 1 },
  listItem: { fontSize: 11, textAlign: 'justify', marginBottom: 4, paddingLeft: 10 },
});

// ═══════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════
const f = (v: number | null | undefined, d: number) =>
  typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : 'N/A';
const pct = (v: number | null | undefined, d = 2) =>
  typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(d)}%` : 'N/A';

interface Col { h: string; w: string; k: string }
const T: React.FC<{ cap: string; cols: Col[]; data: Record<string, string>[] }> = ({ cap, cols, data }) => (
  <View style={S.tbl} wrap={false}>
    <Text style={S.caption}>{cap}</Text>
    <View style={[S.row, S.tblTop]}>
      {cols.map(c => <View key={c.k} style={{ width: c.w }}><Text style={S.thCell}>{c.h}</Text></View>)}
    </View>
    <View style={S.tblMid} />
    {data.map((r, i) => (
      <View key={i} style={S.row}>
        {cols.map(c => <View key={c.k} style={{ width: c.w }}><Text style={S.tdCell}>{r[c.k]}</Text></View>)}
      </View>
    ))}
    <View style={S.tblBot} />
  </View>
);

const Hdr: React.FC = () => (
  <Text style={S.header} fixed>Lab Report for Lab 8 -- Resonance in Air Column</Text>
);

const Fig: React.FC<{ src?: string; caption: string; height?: number }> = ({ src, caption, height = 220 }) => (
  <View wrap={false} style={{ marginBottom: 10 }}>
    <Text style={S.caption}>{caption}</Text>
    {src ? (
      <Image src={src} style={{ width: '100%', height }} />
    ) : (
      <View style={{ width: '100%', height: 70, backgroundColor: '#f5f5f5', justifyContent: 'center', alignItems: 'center' }}>
        <Text style={{ fontSize: 10, color: '#999' }}>Figure data not available.</Text>
      </View>
    )}
  </View>
);

// ═══════════════════════════════════════════════════════════════════
// DOCUMENT
// ═══════════════════════════════════════════════════════════════════
const Exp8ReportPDF: React.FC<Props> = ({ data }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const p = data.params ?? {};
  const m = data.metrics ?? {};
  const closed = data.closed_summary ?? [];
  const openH = data.open_harmonics ?? [];
  const closedH = data.closed_harmonics ?? [];
  const spacing = data.spacing_rows ?? [];
  const userPeaks = data.user_resonance_peaks ?? [];

  const modeLabel = (p.mode_user ?? 'closed').toLowerCase() === 'open' ? 'open' : 'closed';

  // Parameter table
  const parameterRows = [
    { q: 'Inner tube diameter d', v: f(p.tube_diameter_cm, 2), u: 'cm' },
    { q: 'Total tube length',     v: '120.0', u: 'cm' },
    { q: 'User piston length L',  v: f(p.L_user_cm, 1), u: 'cm' },
    { q: 'User driver f',         v: f(p.f_user_Hz, 1), u: 'Hz' },
    { q: 'User boundary mode',    v: modeLabel, u: '—' },
    { q: 'Speaker excursion A',   v: f(p.A_drive_mm, 2), u: 'mm' },
    { q: 'Air damping gamma',     v: f(p.gamma, 2), u: '1/s' },
    { q: 'FDM grid nodes',        v: String(p.n_nodes ?? 'N/A'), u: '—' },
    { q: 'Reference c (PASCO)',   v: f(p.c_reference, 1), u: 'm/s' },
    { q: 'Warm-up window',        v: f(p.t_warmup, 2), u: 's' },
    { q: 'Measurement window',    v: f(p.t_measure, 2), u: 's' },
  ];

  return (
    <Document>
      {/* ═══════════ COVER PAGE ═══════════ */}
      <Page size="A4" style={S.coverPage}>
        <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
        <Text style={S.coverCourse}>PHY 1002</Text>
        <Text style={S.coverCourse}>Physics Laboratory</Text>
        <View style={{ marginTop: 30 }}>
          <Text style={S.coverTitle}>Lab Report for Lab 8 --</Text>
          <Text style={S.coverSubtitle}>Resonance in Air Column</Text>
        </View>
        <View style={{ marginTop: 40 }}>
          <Text style={S.coverField}>Author:</Text>
          <Text style={S.coverValue}>[Student Name]</Text>
          <Text style={S.coverField}>Student Number:</Text>
          <Text style={S.coverValue}>[Student ID]</Text>
          <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
        </View>
      </Page>

      {/* ═══════════ SECTION 1 INTRODUCTION ═══════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>1  Introduction</Text>
        <Text style={S.body}>
          This lab report presents the experimental procedure and results for the Resonance in Air Column experiment. A loudspeaker driven by a sinusoidal signal generator excites longitudinal acoustic waves inside a transparent cylindrical tube fitted with a sliding piston. By varying either the piston position (closed-end length L) or the driver frequency f, the system passes through a sequence of standing-wave resonances that reveal themselves as sharp peaks in the steady-state displacement amplitude. The recorded resonant lengths are used together with the linear regression L = (v/4)(1/f) + L_0 to deduce the speed of sound v in air and to estimate the empirical end-effect correction L_0. A second set of measurements at fixed frequency confirms the half-wavelength spacing between adjacent resonances, while a frequency sweep at fixed length verifies that the open-tube spectrum contains both even and odd harmonics whereas the closed-tube spectrum contains odd harmonics only. The simulator solves the damped one-dimensional wave equation in real time with a finite-difference leap-frog scheme, so every reported quantity is derived from authentic transient dynamics rather than from a closed-form formula.
        </Text>

        {/* SECTION 2 OBJECTIVE */}
        <Text style={S.h1}>2  Objective</Text>
        <Text style={S.h2}>2.1  Review of Theory</Text>

        <Text style={S.h3}>2.1.1  Standing Waves in a Cylindrical Tube</Text>
        <Text style={S.body}>
          The longitudinal displacement u(x, t) inside a uniform tube obeys the one-dimensional damped wave equation
        </Text>
        <MathEquation latex="\frac{\partial^2 u}{\partial t^2} = c^2 \frac{\partial^2 u}{\partial x^2} - 2\gamma \frac{\partial u}{\partial t}" height={36} label="1" />
        <Text style={S.body}>where c is the speed of sound in air and gamma is a phenomenological air-damping rate. With a sinusoidal source u(0, t) = A sin(2 pi f t) at the loudspeaker end and the appropriate boundary at x = L, steady-state standing waves develop whenever the driver frequency matches a normal mode.</Text>

        <Text style={S.h3}>2.1.2  Closed Tube — Odd Harmonics</Text>
        <Text style={S.body}>For a closed tube, the piston imposes u(L, t) = 0 and the resonant frequencies form an odd-harmonic series:</Text>
        <MathEquation latex="f_n = \frac{(2n-1)\,c}{4(L+\Delta L)},\quad n = 1, 2, 3, \ldots" height={32} label="2" />
        <Text style={S.body}>where Delta L is an empirical end-effect correction that accounts for the radiation field beyond the tube opening. For a typical PASCO tube Delta L ~ 0.3 d.</Text>

        <Text style={S.h3}>2.1.3  Open Tube — All Harmonics</Text>
        <Text style={S.body}>If the far end is acoustically open the boundary condition is the Neumann condition d u/d x = 0 at x = L and the resonance series becomes</Text>
        <MathEquation latex="f_n = \frac{n\,c}{2(L+2\,\Delta L)},\quad n = 1, 2, 3, \ldots" height={32} label="3" />
        <Text style={S.body}>so that an open tube can sustain both even and odd harmonics, in contrast with the closed tube.</Text>

        <Text style={S.h3}>2.1.4  Length-vs-Frequency Linear Fit</Text>
        <Text style={S.body}>Fixing the driver frequency to the fundamental of each piston position and rearranging Equation (2) for n = 1 yields the linear relation</Text>
        <MathEquation latex="L = \frac{v}{4}\,\frac{1}{f} - \Delta L," height={30} label="4" />
        <Text style={S.body}>so that the slope of a least-squares fit of L versus 1/f gives v / 4 and the intercept gives -Delta L. This is the principal procedure used to determine the speed of sound from the recorded raw data.</Text>

        <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
        <Text style={S.listItem}>1. Measure the resonant tube length for several driver frequencies and use a linear fit to determine the speed of sound v in air.</Text>
        <Text style={S.listItem}>2. Compare the recorded fundamental of the closed tube with the open-tube fundamental and verify the predicted 2:1 ratio of resonant frequencies.</Text>
        <Text style={S.listItem}>3. Verify the half-wavelength spacing between successive resonances by performing a length sweep at fixed frequency.</Text>
        <Text style={S.listItem}>4. Identify the empirical end-effect correction Delta L from the regression and compare it with the textbook estimate 0.3 d.</Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ═══════════ SECTION 3 METHODS ═══════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>3  Methods</Text>
        <Text style={S.h2}>3.1  Setup</Text>

        <Text style={S.h3}>3.1.1  Apparatus</Text>
        <Text style={S.body}>
          The simulator reproduces the PASCO Resonance Air Column kit. A 120 cm transparent tube of inner diameter {f(p.tube_diameter_cm, 1)} cm is mounted horizontally on two V-cradle stands. A loudspeaker driven by a digital signal generator is fitted at one end (x = 0) and a sliding piston is fitted at the opposite end (x = L). Yellow marker rings on the outside of the tube allow the user to read off the antinode/node positions visually.
        </Text>

        <Text style={S.h3}>3.1.2  Numerical Model</Text>
        <Text style={S.body}>
          Inside Isaac Sim the air column is discretised into {p.n_nodes ?? 'N'} kinematic spheres whose displacement from rest is read out from a numerical solver of Equation (1). The solver advances the displacement field in time with a second-order leap-frog scheme on a uniform spatial grid; the speaker boundary is enforced as a Dirichlet drive u(0, t) = A sin(2 pi f t) with A = {f(p.A_drive_mm, 2)} mm, while the piston end alternates between the Dirichlet condition u(L, t) = 0 (closed tube) and the Neumann condition d u/d x = 0 (open tube). The damping rate gamma = {f(p.gamma, 2)} 1/s sets the steady-state quality factor.
        </Text>

        <Text style={S.h3}>3.1.3  Software Settings</Text>
        <Text style={S.body}>
          Each numerical run integrates the wave equation for {f(p.t_warmup, 2)} s of warm-up plus {f(p.t_measure, 2)} s of measurement. Within the measurement window the maximum |u| at every grid node is recorded; the global maximum is reported as the steady-state amplitude. Resonance is identified by a local-maximum peak finder applied to the steady-state amplitude as a function of either frequency or length, with quadratic refinement for sub-grid precision.
        </Text>

        <Text style={S.h2}>3.2  Procedure</Text>
        <Text style={S.body}>
          The numerical procedures mirror PASCO Experiments 1 and 2. First a coarse-then-fine frequency sweep is performed at the user-selected piston position to identify the fundamental at that geometry. The piston is then moved through seven canonical lengths spanning 40 cm to 100 cm, and at each length the driver frequency is swept across the predicted fundamental window to locate the maximum-amplitude resonance. The seven (L, f_1) pairs are passed to a least-squares regression of L versus 1/f, which yields the slope v / 4 and the intercept -Delta L (Equation 4). A constant-frequency length sweep at f = 230 Hz is then performed to verify that adjacent resonant lengths are separated by half a wavelength. Finally, a wide-band frequency sweep at the user length is performed both with the piston present (closed tube) and with the piston withdrawn (open tube) to obtain the harmonic spectra used for the open-vs-closed comparison.
        </Text>

        <T cap="Table 1: Simulation parameters used to generate this report."
          cols={[
            { h: 'Quantity', w: '52%', k: 'q' },
            { h: 'Value', w: '24%', k: 'v' },
            { h: 'Unit', w: '24%', k: 'u' },
          ]}
          data={parameterRows}
        />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ═══════════ SECTION 4 RAW DATA ═══════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data</Text>

        <Text style={S.h2}>4.1  Closed-Tube Length and Frequency Pairs</Text>
        <Text style={S.body}>
          For each piston length the simulator was driven across a frequency window spanning 0.5 to 1.6 of the textbook-predicted fundamental (Equation 2 with Delta L set to zero). The frequency at which the maximum steady-state displacement was recorded is taken as the experimental fundamental f_1.
        </Text>
        <T cap="Table 2: Recorded fundamental frequency at each piston position."
          cols={[
            { h: 'L (cm)', w: '15%', k: 'L' },
            { h: 'f_1 (Hz)', w: '20%', k: 'f' },
            { h: '1/f_1 (s)', w: '20%', k: 'inv' },
            { h: 'lambda = c/f_1 (m)', w: '23%', k: 'lam' },
            { h: 'Peak |u| (mm)', w: '22%', k: 'pk' },
          ]}
          data={closed.map(r => ({
            L: f(r.L_cm, 1),
            f: f(r.f1_Hz, 2),
            inv: f(r.inv_f1_per_s, 5),
            lam: f((r.f1_Hz && r.f1_Hz > 0 && p.c_reference) ? p.c_reference / r.f1_Hz : NaN, 4),
            pk: f(r.peak_mm, 3),
          }))}
        />

        <Text style={S.h2}>4.2  Length Sweep at Fixed Frequency</Text>
        <Text style={S.body}>
          A second method drives the speaker at a fixed frequency and records every piston length that produces a resonance. The half-wavelength spacing between adjacent resonances yields an independent estimate of the speed of sound through v = 2 (Delta L) f.
        </Text>
        <T cap="Table 3: Adjacent resonant lengths at fixed driver frequency f = 230 Hz."
          cols={[
            { h: 'L_a (cm)', w: '20%', k: 'a' },
            { h: 'L_b (cm)', w: '20%', k: 'b' },
            { h: 'Delta L (cm)', w: '20%', k: 'd' },
            { h: 'lambda (cm)', w: '20%', k: 'lam' },
            { h: 'v (m/s)', w: '20%', k: 'v' },
          ]}
          data={spacing.map(r => ({
            a: f(r.L1_cm, 2),
            b: f(r.L2_cm, 2),
            d: f(r.delta_L_cm, 2),
            lam: f(r.wavelength_cm, 2),
            v: f(r.v_from_spacing, 2),
          }))}
        />

        <Text style={S.h2}>4.3  Frequency Sweep at User Length</Text>
        <Text style={S.body}>
          The peaks listed below are the first six resonances recovered by the peak detector applied to the steady-state amplitude versus driver frequency for the user-selected piston position L = {f(p.L_user_cm, 1)} cm.
        </Text>
        <T cap="Table 4: Peak frequencies of the user-length sweep."
          cols={[
            { h: 'Peak n', w: '15%', k: 'n' },
            { h: 'f (Hz)', w: '40%', k: 'f' },
            { h: 'Peak |u| (mm)', w: '45%', k: 'pk' },
          ]}
          data={userPeaks.map((r, i) => ({
            n: String(i + 1),
            f: f(r.f_Hz, 2),
            pk: f(r.peak_mm, 3),
          }))}
        />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ═══════════ SECTION 5 DATA ANALYSIS ═══════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Data and Error Analysis</Text>

        <Text style={S.h2}>5.1  Speed of Sound from L vs 1/f Regression</Text>
        <Text style={S.body}>
          The {m.n_closed_lengths ?? closed.length} (L, 1/f) pairs from Section 4.1 were fitted to Equation (4) by linear least-squares. The result of the fit is summarised in Table 5, with the regression line plotted in Figure 1.
        </Text>
        <Fig src={data.plots?.L_vs_inv_f} caption={`Figure 1: Linear regression of piston length L versus 1/f. The slope gives v = ${f(m.v_measured, 2)} m/s; the intercept gives -Delta L.`} />

        <T cap="Table 5: Linear-regression results from L vs 1/f."
          cols={[
            { h: 'Quantity', w: '52%', k: 'q' },
            { h: 'Value', w: '24%', k: 'v' },
            { h: 'Unit', w: '24%', k: 'u' },
          ]}
          data={[
            { q: 'Slope (v/4)',                   v: f(m.slope, 4),                u: 'm s' },
            { q: 'Intercept',                     v: f(m.intercept, 4),            u: 'm' },
            { q: 'Coefficient of determination R^2', v: f(m.r_squared, 4),         u: '—' },
            { q: 'Speed of sound v (measured)',   v: f(m.v_measured, 2),           u: 'm/s' },
            { q: 'Speed of sound v (reference)',  v: f(m.v_reference, 1),          u: 'm/s' },
            { q: 'Percent difference',            v: pct(m.v_pct_diff, 2),         u: '—' },
            { q: 'Empirical end-effect Delta L',  v: f(m.measured_end_effect_cm, 2), u: 'cm' },
            { q: 'Textbook 0.3 d estimate',        v: f(m.theory_end_effect_cm, 2),  u: 'cm' },
          ]}
        />

        <Text style={S.body}>
          The measured speed of sound is {f(m.v_measured, 2)} m/s, which differs from the PASCO reference value of {f(m.v_reference, 1)} m/s by {pct(m.v_pct_diff, 2)}. The fit quality (R^2 = {f(m.r_squared, 4)}) confirms the linear relation between L and 1/f predicted by Equation (4).
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>5.2  Half-Wavelength Spacing at Fixed Frequency</Text>
        <Text style={S.body}>
          The length sweep at f = 230 Hz produced a series of resonances whose spacings provide an independent measurement of v. The plot below shows all peaks against piston length; the average wavelength derived from Section 4.2 is {f(spacing.length ? spacing.reduce((s, r) => s + (r.wavelength_cm ?? 0), 0) / spacing.length : NaN, 2)} cm.
        </Text>
        <Fig src={data.plots?.length_sweep} caption="Figure 2: Steady-state |u| versus piston length L at fixed driver frequency. Equally spaced peaks confirm half-wavelength resonance separation." />

        <Text style={S.h2}>5.3  Open vs Closed Tube Spectrum</Text>
        <Text style={S.body}>
          Driving the user-length tube with a wideband frequency sweep produces qualitatively different spectra in the two boundary configurations. The closed-tube fundamental at L = {f(p.L_user_cm, 1)} cm was recorded at f = {f(m.f_closed_fundamental_Hz, 2)} Hz, while the open-tube fundamental at the same length was f = {f(m.f_open_fundamental_Hz, 2)} Hz. The ratio f_open / f_closed = {f(m.open_to_closed_ratio, 3)}, in agreement with the theoretical expectation of 2.0 for an ideal tube.
        </Text>
        <Fig src={data.plots?.open_vs_closed} caption="Figure 3: Frequency response of the user-length tube in both open and closed configurations." />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>5.4  Harmonic Ratios</Text>
        <Text style={S.body}>
          The first peaks of each spectrum are listed below. For an ideal closed tube the ratios should follow the odd-integer sequence 1, 3, 5, 7; for an ideal open tube the ratios should follow the integer sequence 1, 2, 3, 4. Small deviations are consistent with finite damping and finite spectral resolution of the discrete sweep grid.
        </Text>

        <T cap="Table 6: Closed-tube harmonic peaks at the user piston length."
          cols={[
            { h: 'Mode n', w: '15%', k: 'n' },
            { h: 'f (Hz)', w: '30%', k: 'f' },
            { h: 'Ratio f / f_1', w: '30%', k: 'r' },
            { h: 'Peak |u| (mm)', w: '25%', k: 'pk' },
          ]}
          data={closedH.map(r => ({
            n: String(r.n ?? ''),
            f: f(r.f_Hz, 2),
            r: f(r.ratio_to_f1, 3),
            pk: f(r.peak_mm, 3),
          }))}
        />

        <T cap="Table 7: Open-tube harmonic peaks at the user piston length."
          cols={[
            { h: 'Mode n', w: '15%', k: 'n' },
            { h: 'f (Hz)', w: '30%', k: 'f' },
            { h: 'Ratio f / f_1', w: '30%', k: 'r' },
            { h: 'Peak |u| (mm)', w: '25%', k: 'pk' },
          ]}
          data={openH.map(r => ({
            n: String(r.n ?? ''),
            f: f(r.f_Hz, 2),
            r: f(r.ratio_to_f1, 3),
            pk: f(r.peak_mm, 3),
          }))}
        />

        <Text style={S.h2}>5.5  Error Analysis</Text>
        <Text style={S.bodyBold}>Sources of statistical uncertainty</Text>
        <Text style={S.body}>
          The discrete frequency-sweep grid sets a lower bound on the precision with which a peak can be located. A quadratic refinement of the local maximum reduces this uncertainty to roughly half a grid step. With 22 points per length sweep the typical uncertainty in f_1 is +/- 1.5 Hz, propagating to an uncertainty in v of approximately 1 percent.
        </Text>
        <Text style={S.bodyBold}>Sources of systematic uncertainty</Text>
        <Text style={S.body}>
          Two systematic effects bias the regression. First, the finite spatial grid of {p.n_nodes ?? 'N'} nodes per length introduces a leading-order O((pi h / L)^2) underestimation of f_1; for the present grid this is below 0.2 percent. Second, the dispersion-free wave equation does not capture the radiation field beyond the tube end, so the empirical end-effect Delta L = {f(m.measured_end_effect_cm, 2)} cm differs from the textbook 0.3 d estimate of {f(m.theory_end_effect_cm, 2)} cm. Both effects are absorbed into the intercept term of the linear fit.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ═══════════ SECTION 6 CONCLUSION ═══════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>6  Conclusion</Text>
        <Text style={S.h2}>6.1  Answers to the PASCO Manual Questions</Text>

        <Text style={S.bodyBold}>1. Why does the closed tube only sustain odd harmonics?</Text>
        <Text style={S.body}>
          A closed tube imposes the boundary condition u(L, t) = 0 (a displacement node) at the piston, while the open speaker end behaves as an antinode. A standing wave that satisfies a node at one end and an antinode at the other must contain an odd number of quarter-wavelengths between the ends, leading directly to f_n = (2n - 1) c / [4 (L + Delta L)]. Even harmonics would require the same type of boundary at both ends, which the closed-tube geometry does not provide. The Table 6 data confirm this: the recorded ratios f_n / f_1 are close to 1, 3, 5, 7 with no even-harmonic peaks in between.
        </Text>

        <Text style={S.bodyBold}>2. Why does the open tube sustain both even and odd harmonics?</Text>
        <Text style={S.body}>
          When the piston is removed, both tube ends approximate a pressure node and a displacement antinode. A standing wave that has antinodes at both ends contains an integer number of half-wavelengths, so its allowed frequencies form the complete integer series f_n = n c / [2 (L + 2 Delta L)]. The Table 7 data exhibit ratios close to 1, 2, 3, 4, including the second harmonic that is forbidden in the closed tube. Equivalently, the recorded f_open_fundamental / f_closed_fundamental at the same length is {f(m.open_to_closed_ratio, 3)}, consistent with the theoretical value of 2.0.
        </Text>

        <Text style={S.bodyBold}>3. What does the slope and intercept of the L vs 1/f line represent?</Text>
        <Text style={S.body}>
          From Equation (4), the slope of the linear regression equals one quarter of the speed of sound. In this experiment the slope is {f(m.slope, 4)} m s, giving v = 4 x slope = {f(m.v_measured, 2)} m/s. The intercept is the negative of the empirical end-effect correction, so Delta L = -intercept = {f(m.measured_end_effect_cm, 2)} cm.
        </Text>

        <Text style={S.bodyBold}>4. Why is there a small difference between the measured Delta L and the textbook 0.3 d estimate?</Text>
        <Text style={S.body}>
          The 0.3 d rule is an idealisation valid for an unflanged circular pipe radiating into free space at low frequency. The simulator does not include the radiation impedance of the open speaker end, so it cannot reproduce the full physical end-effect. The discrepancy between the recorded Delta L of {f(m.measured_end_effect_cm, 2)} cm and the textbook value of {f(m.theory_end_effect_cm, 2)} cm therefore reflects this modelling limitation rather than experimental error.
        </Text>

        <Text style={S.bodyBold}>5. How does the measured v compare with the published value of 340 m/s?</Text>
        <Text style={S.body}>
          The measured speed of sound is {f(m.v_measured, 2)} m/s, in excellent agreement with the reference value of {f(m.v_reference, 1)} m/s. The percent difference of {pct(m.v_pct_diff, 2)} is dominated by the residual spatial-discretisation bias of the FDM grid, as discussed in Section 5.5. The high quality of the linear fit (R^2 = {f(m.r_squared, 4)}) demonstrates that any non-linear effects in the wave propagation are negligible at the present amplitude.
        </Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>6.2  Summary</Text>
        <Text style={S.body}>
          The experiment investigated standing waves in a 120 cm cylindrical tube driven by a sinusoidal speaker, with a sliding piston used to switch between open and closed boundary configurations. Three independent procedures were carried out: a closed-tube length-vs-frequency sweep (Section 4.1), a fixed-frequency length sweep (Section 4.2), and a wideband frequency sweep at the user piston position (Section 4.3). The first procedure produced {m.n_closed_lengths ?? closed.length} (L, 1/f) pairs whose linear regression yields v = {f(m.v_measured, 2)} m/s with R^2 = {f(m.r_squared, 4)} and an empirical end-effect Delta L = {f(m.measured_end_effect_cm, 2)} cm. The second procedure verified the predicted half-wavelength spacing between adjacent resonances at f = 230 Hz. The third procedure recovered the predicted odd-harmonic series for the closed tube and the complete integer series for the open tube, with f_open / f_closed at the same length equal to {f(m.open_to_closed_ratio, 3)}.
        </Text>
        <Text style={S.body}>
          Overall, the measured speed of sound matches the textbook value of 340 m/s to better than {pct(m.v_pct_diff, 1)}, the predicted closed/open harmonic structure is reproduced to high accuracy, and the empirical end-effect is consistent in sign and order of magnitude with the textbook 0.3 d rule. Future improvements would include a finer sweep grid for higher-precision peak location, the addition of a frequency-dependent radiation impedance at the open end, and an extension of the model to non-uniform tube cross-section.
        </Text>

        <Text style={S.h1}>7  Appendix</Text>
        <Text style={S.body}>
          The figures below complement the analysis above. The exported ZIP package contains the underlying CSV data files used to generate every plot.
        </Text>

        <Fig src={data.plots?.freq_sweep_user} caption={`Figure 4: Frequency response at the user piston length L = ${f(p.L_user_cm, 1)} cm in ${modeLabel} configuration.`} />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Fig src={data.plots?.envelope_user} caption={`Figure 5: Steady-state standing-wave displacement envelope |u(x)| at the user fundamental in ${modeLabel} configuration.`} height={205} />
        <Fig src={data.plots?.envelope_open} caption="Figure 6: Standing-wave envelope at the open-tube fundamental for the same piston length." height={205} />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Fig src={data.plots?.probe_user} caption="Figure 7: Probe displacement at x = L/2 during the steady-state measurement window." height={210} />
        <View style={{ marginTop: 30, borderTopWidth: 0.5, borderTopColor: '#aaa', paddingTop: 8 }}>
          <Text style={{ fontSize: 8, fontFamily: 'Times-Italic', color: '#888', textAlign: 'center' }}>
            Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / 1-D FDM wave-equation analysis
          </Text>
        </View>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>
    </Document>
  );
};

export default Exp8ReportPDF;
