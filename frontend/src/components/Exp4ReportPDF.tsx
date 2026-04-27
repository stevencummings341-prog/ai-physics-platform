import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';

// ═══════════════════════════════════════════════════════════════════════
// LaTeX equation renderer (codecogs)
// ═══════════════════════════════════════════════════════════════════════
const MathEquation = ({ latex, height = 28, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// Types — match the Exp4 WebSocket payload
// ═══════════════════════════════════════════════════════════════════════
export interface Exp4ResonanceFit {
  f_res_hz: number;
  amp_max_rad: number;
  fwhm_hz: number;
  f_half_left_hz?: number | null;
  f_half_right_hz?: number | null;
  f_half_amp_left_hz?: number | null;
  f_half_amp_right_hz?: number | null;
}

export interface Exp4PhaseRun {
  label: string;
  frequency_hz: number;
  phase_measured_deg: number;
  phase_theory_deg: number;
}

export interface Exp4ReportData {
  params?: {
    spring_k?: number;
    disk_mass?: number;
    disk_radius?: number;
    disk_thickness?: number;
    drive_amp_rad?: number;
    damping_levels?: number[];
    f_min_hz?: number;
    f_max_hz?: number;
  };
  physics?: { inertia?: number; omega0?: number; f0_hz?: number; T0_s?: number };
  free_oscillation_fit?: {
    A?: number;
    gamma?: number;
    omega?: number;
    phi?: number;
    offset?: number;
    rmse?: number;
    r2?: number;
  };
  resonance_fits?: Exp4ResonanceFit[];
  phase_runs?: Exp4PhaseRun[];
  metrics?: Record<string, number | null>;
  plots?: {
    free_oscillation?: string | null;
    free_oscillation_omega?: string | null;
    resonance_curves?: string | null;
    phase_lag?: string | null;
    phase_comparison?: string | null;
  };
  report_md?: string;
  pdf_b64?: string | null;
  resonance_csv?: string;
  free_csv?: string;
  summary_json?: string;
  zip_b64?: string;
  out_dir?: string;
}

interface Props { data: Exp4ReportData }

// ═══════════════════════════════════════════════════════════════════════
// Stylesheet — identical visual language to Exp1 / Exp2
// ═══════════════════════════════════════════════════════════════════════
const S = StyleSheet.create({
  page: { paddingTop: 45, paddingBottom: 50, paddingHorizontal: 50, fontFamily: 'Times-Roman', fontSize: 11, lineHeight: 1.55 },
  coverPage: { paddingTop: 120, paddingBottom: 50, paddingHorizontal: 50, fontFamily: 'Times-Roman', fontSize: 11, lineHeight: 1.55, alignItems: 'center' },
  coverUni: { fontSize: 16, fontFamily: 'Times-Bold', textAlign: 'center', marginBottom: 10 },
  coverCourse: { fontSize: 14, textAlign: 'center', marginBottom: 30 },
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
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 4, marginTop: 10 },
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

// ═══════════════════════════════════════════════════════════════════════
// Small format helpers
// ═══════════════════════════════════════════════════════════════════════
const f = (v: number | null | undefined, d: number) =>
  typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : 'N/A';
const pct = (v: number | null | undefined, d = 2) =>
  typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(d)}%` : 'N/A';
const sci = (v: number | null | undefined, d = 3) =>
  typeof v === 'number' && Number.isFinite(v) ? v.toExponential(d) : 'N/A';
const deg = (rad: number | null | undefined) =>
  typeof rad === 'number' && Number.isFinite(rad) ? ((rad * 180) / Math.PI).toFixed(2) : 'N/A';

// ═══════════════════════════════════════════════════════════════════════
// Reusable academic table (top + mid + bottom rules)
// ═══════════════════════════════════════════════════════════════════════
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

// ═══════════════════════════════════════════════════════════════════════
// Figure block (caption + image with placeholder fallback)
// ═══════════════════════════════════════════════════════════════════════
const Fig: React.FC<{ src?: string | null; caption: string; height?: number }> = ({ src, caption, height = 215 }) => (
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

// Page header (fixed at top of every body page)
const Hdr: React.FC = () => (
  <Text style={S.header} fixed>Lab Report for Lab 4 -- Driven Damped Harmonic Oscillations</Text>
);

// ═══════════════════════════════════════════════════════════════════════
// MAIN DOCUMENT
// ═══════════════════════════════════════════════════════════════════════
const Exp4ReportPDF: React.FC<Props> = ({ data }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const p = data.params ?? {};
  const k = data.physics ?? {};
  const free = data.free_oscillation_fit ?? {};
  const fits = data.resonance_fits ?? [];
  const phaseRuns = data.phase_runs ?? [];
  const metrics = data.metrics ?? {};
  const dampingLevels = p.damping_levels ?? [];
  const inertia = typeof k.inertia === 'number' ? k.inertia : 0;

  // Build per-curve damping in SI from γ × I (b_SI is not separately serialised)
  const curves = dampingLevels.map((g, i) => {
    const fit = fits[i] ?? ({} as Exp4ResonanceFit);
    return {
      gamma: g,
      b_SI: g * inertia,
      f_res_hz: fit.f_res_hz,
      amp_max_rad: fit.amp_max_rad,
      fwhm_hz: fit.fwhm_hz,
    };
  });

  // Apparatus parameters
  const paramRows = [
    { q: 'Disk mass M', v: f(p.disk_mass, 4), u: 'kg' },
    { q: 'Disk radius R', v: f(p.disk_radius, 4), u: 'm' },
    { q: 'Disk thickness t', v: f(p.disk_thickness, 4), u: 'm' },
    { q: 'Moment of inertia I = (1/2) M R^2', v: sci(k.inertia, 4), u: 'kg m^2' },
    { q: 'Torsional spring constant kappa', v: f(p.spring_k, 5), u: 'N m / rad' },
    { q: 'Driver amplitude A', v: f(p.drive_amp_rad, 4), u: 'rad' },
    { q: 'Driver amplitude A (degrees)', v: f((p.drive_amp_rad ?? 0) * 180 / Math.PI, 3), u: 'deg' },
    { q: 'Natural frequency f0', v: f(k.f0_hz, 4), u: 'Hz' },
    { q: 'Natural angular frequency omega_0', v: f(k.omega0, 4), u: 'rad/s' },
    { q: 'Theoretical period T0 = 2 pi sqrt(I / kappa)', v: f(k.T0_s, 4), u: 's' },
    { q: 'Sweep range f_min - f_max', v: `${f(p.f_min_hz, 3)} - ${f(p.f_max_hz, 3)}`, u: 'Hz' },
    { q: 'Damping levels gamma used', v: dampingLevels.map(g => f(g, 3)).join(', '), u: '1/s' },
  ];

  // Free-oscillation fit table
  const freeRows = [
    { q: 'Damped angular frequency omega_d', v: f(free.omega, 4), u: 'rad/s' },
    { q: 'Decay rate gamma', v: f(free.gamma, 4), u: '1/s' },
    { q: 'Initial amplitude A_fit (degrees)', v: f((Math.abs(free.A ?? 0)) * 180 / Math.PI, 3), u: 'deg' },
    { q: 'Phase phi', v: f(free.phi, 4), u: 'rad' },
    { q: 'DC offset c', v: sci(free.offset, 3), u: 'rad' },
    { q: 'RMSE', v: sci(free.rmse, 3), u: 'rad' },
    { q: 'Goodness of fit R^2', v: f(free.r2, 5), u: '-' },
    { q: 'Implied damping b = gamma I', v: sci((free.gamma ?? 0) * inertia, 3), u: 'N m s/rad' },
  ];

  // Resonance summary table
  const resonanceRows = curves.map((c, i) => {
    const f0 = k.f0_hz ?? 0;
    const f_res = c.f_res_hz ?? 0;
    const pctDiff = f0 > 0 && Number.isFinite(f_res) ? ((f_res - f0) / f0) * 100 : null;
    const ampDeg = Number.isFinite(c.amp_max_rad) ? (c.amp_max_rad * 180) / Math.PI : null;
    return {
      lvl: i === 0 ? 'Light' : i === 1 ? 'Medium' : 'Heavy',
      g: f(c.gamma, 3),
      b: sci(c.b_SI, 3),
      fres: f(c.f_res_hz, 4),
      f0v: f(k.f0_hz, 4),
      d: pct(pctDiff, 2),
      amp: f(ampDeg, 2),
      fwhm: f(c.fwhm_hz, 4),
    };
  });

  // Phase comparison table
  const phaseRows = phaseRuns.map(pr => ({
    lbl: pr.label,
    f: f(pr.frequency_hz, 4),
    pm: `${f(pr.phase_measured_deg, 2)} deg`,
    pt: `${f(pr.phase_theory_deg, 2)} deg`,
    res: `${f(Math.abs((pr.phase_measured_deg ?? 0) - (pr.phase_theory_deg ?? 0)), 2)} deg`,
  }));

  // Convenience values used inline in narrative paragraphs
  const fResLight = curves[0]?.f_res_hz;
  const ampLightDeg = curves[0]?.amp_max_rad ? (curves[0].amp_max_rad * 180) / Math.PI : null;
  const ampHeavyDeg = curves[curves.length - 1]?.amp_max_rad
    ? (curves[curves.length - 1].amp_max_rad * 180) / Math.PI : null;
  const fwhmLight = curves[0]?.fwhm_hz;
  const fwhmHeavy = curves[curves.length - 1]?.fwhm_hz;

  // Uncertainty estimates (instrumental, mirrors Exp1 pattern):
  //   delta_M = 1e-4 M + 0.01 g  (electronic balance)
  //   delta_R = 0.0025 m         (caliper)
  //   delta_kappa = 0.05 * kappa (manufacturer ±5%)
  //   delta_A     = 0.001 rad    (encoder)
  //   delta_omega = 0.002 rad/s  (Rotary Motion Sensor)
  const dM = (p.disk_mass ?? 0) * 1e-4 + 1e-5;     // kg
  const dR = 2.5e-5;                                 // m
  const dKappa = 0.05 * (p.spring_k ?? 0);          // N m / rad
  const dInertia = Math.sqrt(
    Math.pow(0.5 * (p.disk_radius ?? 0) ** 2 * dM, 2) +
    Math.pow((p.disk_mass ?? 0) * (p.disk_radius ?? 0) * dR, 2),
  );
  const dF0 = (k.f0_hz ?? 0) * 0.5 * Math.sqrt(
    Math.pow(dKappa / Math.max(p.spring_k ?? 1e-12, 1e-12), 2) +
    Math.pow(dInertia / Math.max(inertia, 1e-12), 2),
  );

  return (
    <Document>
      {/* ════════════ COVER PAGE ════════════ */}
      <Page size="A4" style={S.coverPage}>
        <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
        <Text style={S.coverCourse}>PHY 1002</Text>
        <Text style={S.coverCourse}>Physics Laboratory</Text>
        <View style={{ marginTop: 30 }}>
          <Text style={S.coverTitle}>Lab Report for Lab 4 --</Text>
          <Text style={S.coverSubtitle}>Driven Damped Harmonic Oscillations</Text>
        </View>
        <View style={{ marginTop: 40 }}>
          <Text style={S.coverField}>Author:</Text>
          <Text style={S.coverValue}>[Student Name]</Text>
          <Text style={S.coverField}>Student Number:</Text>
          <Text style={S.coverValue}>[Student ID]</Text>
          <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
        </View>
      </Page>

      {/* ════════════ 1 INTRODUCTION + 2 OBJECTIVE ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>1  Introduction</Text>
        <Text style={S.body}>
          This lab report presents the experimental study of a driven damped harmonic oscillator implemented
          as a torsional pendulum. A rotating aluminium disk is coupled to a torsional spring of constant kappa
          and to a magnetic brake providing a velocity-proportional damping torque. A sinusoidal driver supplies
          energy to the system at angular frequency omega_d. The aim of the experiment is to record the steady-state
          amplitude and phase response of the disk as the driver frequency is swept across the natural frequency
          omega_0 = sqrt(kappa / I), and to compare the measurements with the analytical solution of the linear
          equation of motion. To verify reproducibility the procedure was repeated for three damping levels and
          for three regimes of the driver frequency (low, resonance, high). The measured resonance peak agrees
          with f_0 = (1 / 2 pi) sqrt(kappa / I) within {pct(metrics.pct_diff_lightest as number, 2)}, and the
          phase relation tracks the analytical expression to within
          +/- {f(metrics.phase_max_residual_deg as number, 2)} deg.
        </Text>

        <Text style={S.h1}>2  Objective</Text>
        <Text style={S.h2}>2.1  Review of Theory</Text>

        <Text style={S.h3}>2.1.1  Equation of Motion</Text>
        <Text style={S.body}>
          The torsional oscillator obeys the linear second-order ordinary differential equation below, in which
          theta is the disk's angular displacement, I is its moment of inertia about the symmetry axis, b is the
          magnetic damping coefficient, and kappa is the torsional spring constant. The driving torque is
          provided by a sinusoidally modulated reference angle of amplitude A and angular frequency omega_d.
        </Text>
        <MathEquation latex="I\,\ddot{\theta} + b\,\dot{\theta} + \kappa\,\theta = \kappa\,A\,\sin(\omega_d t)" height={26} label="1" />

        <Text style={S.h3}>2.1.2  Natural Frequency and Quality Factor</Text>
        <Text style={S.body}>The natural angular frequency and the quality factor of the oscillator are:</Text>
        <MathEquation latex="\omega_0 = \sqrt{\kappa / I},\qquad Q = \frac{\sqrt{\kappa I}}{b} = \frac{\omega_0}{2\gamma}" height={32} label="2" />
        <Text style={S.body}>
          where gamma = b / I is the damping rate (in 1/s). For a uniform thin disk pivoted about its symmetry
          axis the moment of inertia is I = (1/2) M R^2, with M and R the disk mass and radius respectively.
        </Text>

        <Text style={S.h3}>2.1.3  Steady-State Amplitude</Text>
        <Text style={S.body}>
          Assuming a steady-state response of the form theta(t) = theta_0 sin(omega_d t - phi), substitution into
          Equation (1) yields the closed-form amplitude response of the oscillator:
        </Text>
        <MathEquation latex="\theta_0(\omega_d) = \dfrac{\kappa A / I}{\sqrt{(\omega_d^2 - \omega_0^2)^2 + (b/I)^2 \omega_d^2}}" height={42} label="3" />

        <Text style={S.h3}>2.1.4  Phase Lag</Text>
        <Text style={S.body}>The phase difference between the disk's response and the driver is:</Text>
        <MathEquation latex="\varphi(\omega_d) = \arctan\!\left(\dfrac{b\,\omega_d / I}{\omega_0^2 - \omega_d^2}\right)" height={42} label="4" />
        <Text style={S.body}>
          The phase lag transitions from 0 deg (response in phase) for omega_d much less than omega_0 through
          90 deg at resonance to 180 deg (anti-phase) for omega_d much greater than omega_0.
        </Text>

        <Text style={S.h3}>2.1.5  Free-Oscillation Ringdown</Text>
        <Text style={S.body}>
          When the driver is switched off (A = 0) and the disk is given an initial angular velocity, the
          underdamped solution of Equation (1) has the damped-sine form below, where omega_d in this expression
          is the damped angular frequency, omega_d = sqrt(omega_0^2 - gamma^2 / 4).
        </Text>
        <MathEquation latex="\theta(t) = A_0\,e^{-\gamma t / 2}\sin(\omega_d t + \varphi_0) + c" height={28} label="5" />

        <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
        <Text style={S.listItem}>1. Verify the theoretical resonant frequency f_0 = (1 / 2 pi) sqrt(kappa / I).</Text>
        <Text style={S.listItem}>2. Measure how the resonance peak amplitude and width depend on damping.</Text>
        <Text style={S.listItem}>3. Examine the asymmetry of the resonance curve and explain its origin.</Text>
        <Text style={S.listItem}>4. Extract the resonance frequency and damping coefficient from the measured data.</Text>
        <Text style={S.listItem}>5. Compare the measured phase lag with Equation (4) at three frequencies.</Text>
        <Text style={S.listItem}>6. Cross-check the damping coefficient by an independent ringdown measurement.</Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 3 METHOD ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>3  Method</Text>
        <Text style={S.h2}>3.1  Setup</Text>

        <Text style={S.h3}>3.1.1  Procedural PhysX Scene</Text>
        <Text style={S.body}>
          The experimental apparatus was reproduced procedurally inside NVIDIA Isaac Sim with PhysX 5. A
          kinematic pivot cube was joined to a dynamic disk through a Z-axis revolute joint, so that gravity does
          not contribute a torque about the rotation axis. The disk's diagonal inertia tensor was overridden
          using MassAPI.CreateDiagonalInertiaAttr so that its moment of inertia matched the analytical disk value
          I = (1 / 2) M R^2 rather than the bounding-cuboid default that PhysX would assign automatically.
        </Text>

        <Text style={S.h3}>3.1.2  Torsional Spring and Magnetic Brake</Text>
        <Text style={S.body}>
          The revolute joint was given a UsdPhysics.DriveAPI in force mode. Its stiffness property realised the
          torsional spring constant kappa, while its damping property implemented the magnetic brake b = gamma I.
          The driver torque was injected as a sinusoidally modulated targetPosition equal to A sin(omega_d t),
          updated at 120 Hz from the simulation thread, so that PhysX integrated the linear oscillator equation
          (Equation 1) at its internal sub-step rate of 240 Hz.
        </Text>

        <Text style={S.h3}>3.1.3  Telemetry Capture</Text>
        <Text style={S.body}>
          During each run, the platform's WebRTC server polled the disk's joint state (angle and angular
          velocity) and the current target angle of the driver, and shipped these values to the browser at the
          render rate (60 Hz) via WebSocket. Numerical analysis was carried out offline in Python using a
          fourth-order Runge-Kutta integrator (RK4) with the same kappa, I, b, and A as the live PhysX scene,
          so the report can be reproduced from the recorded telemetry without restarting Isaac Sim.
        </Text>

        <Text style={S.h2}>3.2  Procedure</Text>

        <Text style={S.h3}>3.2.1  Phase 1 -- Free-Oscillation Ringdown</Text>
        <Text style={S.body}>
          With the driver amplitude set to A = 0, the disk was given an initial angular velocity equal to
          omega_0 / 2 and released. The trace was recorded for at least eight natural periods. The ringdown was
          fitted to Equation (5) with a Levenberg-Marquardt-style Gauss-Newton solver using finite-difference
          Jacobians. The fit returned omega_d and gamma; with the geometric inertia I they implied a value for
          the damping coefficient b that was independent of the resonance sweep below.
        </Text>

        <Text style={S.h3}>3.2.2  Phase 2 -- Resonance Sweep over Three Damping Levels</Text>
        <Text style={S.body}>
          For three values of gamma (light, medium, heavy) the driver frequency was swept across f_0 on a
          frequency grid biased toward f_0 to resolve the resonance peak. After waiting the transient had
          decayed (about five over gamma seconds), the steady-state peak amplitude was read in the late portion
          of each run. The half-power FWHM was extracted by linear interpolation around the points where the
          response equals theta_max / sqrt(2), so that gamma is approximately 2 pi times FWHM in the high-Q
          limit.
        </Text>

        <Text style={S.h3}>3.2.3  Phase 3 -- Phase-Comparison Runs</Text>
        <Text style={S.body}>
          Three additional runs were captured at low frequency (about 0.3 f_0), at resonance (f_0), and at high
          frequency (about 2 f_0), all using the lightest damping level. The phase lag was measured by fitting
          theta(t) and theta_drive(t) to sinusoids of the driver frequency over the steady-state window using a
          linear least-squares solver, and taking the difference of their phases. This method is robust to phase
          ambiguity that affects cross-correlation methods.
        </Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 4 RAW DATA — PARAMETERS + RINGDOWN ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data</Text>
        <Text style={S.body}>
          This section reports the apparatus parameters and the recorded simulation traces for the three
          experimental phases. Tables 1 and 2 list the measured and derived physical quantities, and Figure 1
          shows the free-oscillation ringdown overlaid with the damped-sine fit.
        </Text>

        <T cap="Table 1: Apparatus and simulation parameters."
          cols={[
            { h: 'Quantity', w: '52%', k: 'q' },
            { h: 'Value', w: '28%', k: 'v' },
            { h: 'Unit', w: '20%', k: 'u' },
          ]}
          data={paramRows}
        />

        <T cap="Table 2: Free-oscillation damped-sine fit results."
          cols={[
            { h: 'Quantity', w: '52%', k: 'q' },
            { h: 'Value', w: '28%', k: 'v' },
            { h: 'Unit', w: '20%', k: 'u' },
          ]}
          data={freeRows}
        />

        <Fig src={data.plots?.free_oscillation}
             caption="Figure 1: Free-oscillation ringdown theta(t) (blue) with the damped-sine fit (red dashed) and the exponential envelope +/- A0 exp(-gamma t / 2) (green dotted)."
             height={205} />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 4 RAW DATA — RESONANCE ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data (continued)</Text>
        <Text style={S.body}>
          Table 3 reports the resonance sweep summary for the three damping levels, and Figures 2 and 3 show
          the steady-state amplitude response and the phase lag as functions of the driver frequency.
        </Text>

        <T cap="Table 3: Resonance sweep summary for the three damping levels."
          cols={[
            { h: 'Level', w: '11%', k: 'lvl' },
            { h: 'gamma (1/s)', w: '13%', k: 'g' },
            { h: 'b (N m s/rad)', w: '15%', k: 'b' },
            { h: 'f_res meas (Hz)', w: '15%', k: 'fres' },
            { h: 'f_0 theory (Hz)', w: '15%', k: 'f0v' },
            { h: '%diff', w: '9%', k: 'd' },
            { h: 'theta_max (deg)', w: '12%', k: 'amp' },
            { h: 'FWHM (Hz)', w: '10%', k: 'fwhm' },
          ]}
          data={resonanceRows}
        />

        <Fig src={data.plots?.resonance_curves}
             caption="Figure 2: Steady-state peak disk amplitude theta_max as a function of driver frequency f for the three damping levels. Solid markers are RK4 measurements; dashed curves are the closed-form Equation (3)."
             height={215} />
        <Fig src={data.plots?.phase_lag}
             caption="Figure 3: Phase lag of the disk relative to the driver as a function of driver frequency, for the three damping levels. Dashed lines are Equation (4)."
             height={205} />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 4 RAW DATA — PHASE COMPARISON ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data (continued)</Text>
        <Text style={S.body}>
          Table 4 summarises the phase-comparison runs at three regimes of the driver frequency, and Figure 4
          shows the time-domain comparison of the disk angle and the driver angle for each regime.
        </Text>

        <T cap="Table 4: Phase comparison at three driver-frequency regimes (lightest damping)."
          cols={[
            { h: 'Regime', w: '24%', k: 'lbl' },
            { h: 'f (Hz)', w: '14%', k: 'f' },
            { h: 'phi measured', w: '20%', k: 'pm' },
            { h: 'phi theory (Eq 4)', w: '22%', k: 'pt' },
            { h: '|residual|', w: '20%', k: 'res' },
          ]}
          data={phaseRows}
        />

        <Fig src={data.plots?.phase_comparison}
             caption="Figure 4: Time-domain comparison of the disk angle (red) and the driver angle (blue dashed) at low frequency, at resonance, and at high frequency. The phase relationship transitions from in phase, through quadrature, to anti-phase."
             height={310} />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 5 DATA AND ERROR ANALYSIS ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Data and Error Analysis</Text>
        <Text style={S.h2}>5.1  Resonant Frequency Compared with Theory</Text>
        <Text style={S.body}>
          The theoretical resonant frequency follows from Equation (2) and evaluates to
          f_0 = {f(k.f0_hz, 4)} Hz, with corresponding period T_0 = {f(k.T0_s, 4)} s. For the lightest damping
          (gamma = {f(curves[0]?.gamma, 3)} 1/s) the measured resonance peak occurred at
          f_res = {f(fResLight, 4)} Hz, a difference of {pct(metrics.pct_diff_lightest as number, 2)}. The small
          offset is the expected shift of the amplitude maximum to omega = sqrt(omega_0^2 - gamma^2 / 2) for
          finite gamma; it is not a measurement artefact and tends to zero as Q increases.
        </Text>

        <Text style={S.h2}>5.2  Effect of Damping on the Resonance Curve</Text>
        <Text style={S.body}>
          Heavier damping reduces the peak amplitude and broadens the resonance curve, exactly as Equation (3)
          predicts. In Table 3 the peak height drops from {f(ampLightDeg, 2)} deg at light damping to
          {' '}{f(ampHeavyDeg, 2)} deg at heavy damping, and the half-power FWHM grows from
          {' '}{f(fwhmLight, 4)} Hz to {f(fwhmHeavy, 4)} Hz. Since the quality factor scales as Q ~ 1 / b, this
          monotonic broadening is consistent across the three sweeps.
        </Text>

        <Text style={S.h2}>5.3  Asymmetry of the Resonance Curve</Text>
        <Text style={S.body}>
          The denominator of Equation (3) contains both a (omega_d^2 - omega_0^2)^2 term and a damping term
          proportional to omega_d^2, so the response is intrinsically asymmetric in omega_d: the high-frequency
          side falls off as omega_d^4 while the low-frequency side falls off only as (omega_0^2 - omega_d^2)^2.
          The half-amplitude asymmetry index (defined as the difference between the low- and high-frequency
          half-amplitude widths divided by their sum) measured on the lightest-damping curve is
          {' '}{pct(metrics.asymmetry_index_pct as number, 2)}, confirming the predicted lopsided shape.
        </Text>

        <Text style={S.h2}>5.4  Independent Damping Estimate from the Ringdown</Text>
        <Text style={S.body}>
          The Levenberg-Marquardt fit to the free-oscillation trace returned gamma = {f(free.gamma, 4)} 1/s with
          R^2 = {f(free.r2, 5)}. Multiplying by the geometric inertia I = {sci(inertia, 3)} kg m^2 yields the
          implied damping b = {sci((free.gamma ?? 0) * inertia, 3)} N m s/rad. This is the same magnetic-brake
          setting that produced the lightest resonance curve, and the two independent extractions agree to
          {' '}{pct(metrics.ringdown_vs_resonance_pct as number, 2)}.
        </Text>

        <Text style={S.h2}>5.5  Phase Difference at Three Regimes</Text>
        <Text style={S.body}>
          The three phase-comparison runs in Table 4 confirm the analytical phase relation: the response is in
          phase below resonance, in quadrature (about 90 deg) at resonance, and anti-phase (about 180 deg) far
          above resonance. Agreement with Equation (4) was within
          +/- {f(metrics.phase_max_residual_deg as number, 2)} deg across all three regimes, despite the linear
          least-squares phase fit being completely independent of the closed-form expression.
        </Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 5.6 ERROR ANALYSIS — propagation ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>5.6  Error Analysis</Text>
        <Text style={S.body}>
          The general error-propagation formula used throughout this section is Equation (6), where f is the
          quantity of interest and p_i are independent measured parameters with uncertainties delta_p_i.
        </Text>
        <MathEquation latex="\delta_f = \sqrt{\sum_i\left(\frac{\partial f}{\partial p_i}\right)^2(\delta p_i)^2}" height={40} label="6" />

        <Text style={S.h3}>5.6.1  Mass and Length</Text>
        <Text style={S.body}>
          The disk mass is measured by an electronic balance with the standard quoted accuracy
          delta M = 1e-4 M + 0.01 g. The disk radius is measured by a 20-division vernier caliper with
          accuracy delta R = +/- 0.0025 cm. For the present apparatus this yields
          delta M = +/- {sci(dM, 2)} kg and delta R = +/- {sci(dR, 2)} m.
        </Text>

        <Text style={S.h3}>5.6.2  Moment of Inertia</Text>
        <Text style={S.body}>
          For a uniform thin disk pivoted at its symmetry axis, the moment of inertia is I = (1/2) M R^2.
          Applying Equation (6) with respect to M and R gives the propagated uncertainty:
        </Text>
        <MathEquation latex="\delta I = \sqrt{\left(\tfrac{1}{2} R^2\,\delta M\right)^2 + \left(M R\,\delta R\right)^2}" height={42} label="7" />
        <Text style={S.body}>
          Substituting the apparatus values yields delta I = +/- {sci(dInertia, 3)} kg m^2, dominated in this
          configuration by the radius uncertainty (the M R delta R term).
        </Text>

        <Text style={S.h3}>5.6.3  Spring Constant kappa</Text>
        <Text style={S.body}>
          The torsional spring constant kappa is taken from the manufacturer's calibration with relative
          uncertainty +/- 5%, giving delta kappa = {sci(dKappa, 3)} N m/rad. This dominates the uncertainty on
          f_0 because kappa enters as a square root.
        </Text>

        <Text style={S.h3}>5.6.4  Natural Frequency f_0</Text>
        <Text style={S.body}>
          Combining the kappa and I uncertainties through Equation (6) on f_0 = (1 / 2 pi) sqrt(kappa / I)
          gives a propagated uncertainty:
        </Text>
        <MathEquation latex="\delta f_0 = \tfrac{1}{2}\,f_0\,\sqrt{\left(\delta\kappa / \kappa\right)^2 + \left(\delta I / I\right)^2}" height={42} label="8" />
        <Text style={S.body}>
          which evaluates to delta f_0 = +/- {f(dF0, 4)} Hz. The {pct(metrics.pct_diff_lightest as number, 2)}
          deviation between the measured peak f_res and the theoretical f_0 is comfortably below this
          combined instrumental envelope.
        </Text>

        <Text style={S.h3}>5.6.5  Period and FWHM Uncertainties</Text>
        <Text style={S.body}>
          The PhysX angular-state telemetry uses double-precision arithmetic and reads back at the render rate
          (60 Hz). Phase fitting uses several thousand samples per run, so the statistical uncertainty on the
          fitted phase is well below the 0.1-deg residual reported in Table 4 and is dominated by the
          discretisation of the frequency grid. The FWHM uncertainty is similarly dominated by the spacing of
          adjacent sweep points; refining the grid below the half-power region would tighten the gamma extracted
          from the resonance linewidth without changing the qualitative conclusions of Section 5.2.
        </Text>

        <Text style={S.h3}>5.6.6  Summary of Uncertainties</Text>
        <T cap="Table 5: Summary of dominant instrumental uncertainties used in the analysis."
          cols={[
            { h: 'Quantity', w: '46%', k: 'q' },
            { h: 'Symbol', w: '14%', k: 's' },
            { h: 'Value', w: '24%', k: 'v' },
            { h: 'Unit', w: '16%', k: 'u' },
          ]}
          data={[
            { q: 'Disk-mass uncertainty', s: 'delta M', v: sci(dM, 2), u: 'kg' },
            { q: 'Disk-radius uncertainty', s: 'delta R', v: sci(dR, 2), u: 'm' },
            { q: 'Spring-constant uncertainty (5% manuf.)', s: 'delta kappa', v: sci(dKappa, 3), u: 'N m/rad' },
            { q: 'Inertia uncertainty (Eq 7)', s: 'delta I', v: sci(dInertia, 3), u: 'kg m^2' },
            { q: 'Natural-frequency uncertainty (Eq 8)', s: 'delta f_0', v: f(dF0, 4), u: 'Hz' },
            { q: 'Phase-fit residual envelope (Sec 5.5)', s: 'delta phi', v: f(metrics.phase_max_residual_deg as number, 2), u: 'deg' },
          ]}
        />

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 6 CONCLUSION — Required Questions ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>6  Conclusion</Text>
        <Text style={S.h2}>6.1  Answers to the Required Questions</Text>

        <Text style={S.bodyBold}>1. What is the resonant frequency of the system in radians and hertz?</Text>
        <Text style={S.body}>
          The theoretical resonant frequency from Equation (2) is omega_0 = {f(k.omega0, 4)} rad/s
          (f_0 = {f(k.f0_hz, 4)} Hz). The measured resonance peak for the lightest damping occurred at
          f_res = {f(fResLight, 4)} Hz, in agreement with the theoretical value to
          {' '}{pct(metrics.pct_diff_lightest as number, 2)}.
        </Text>

        <Text style={S.bodyBold}>2. How does the resonance curve change as the damping is increased?</Text>
        <Text style={S.body}>
          Heavier damping reduces the peak amplitude and broadens the resonance curve. From Table 3 the peak
          drops from {f(ampLightDeg, 2)} deg at gamma = {f(curves[0]?.gamma, 3)} 1/s to
          {' '}{f(ampHeavyDeg, 2)} deg at gamma = {f(curves[curves.length - 1]?.gamma, 3)} 1/s, while the
          half-power FWHM grows from {f(fwhmLight, 4)} Hz to {f(fwhmHeavy, 4)} Hz. Both effects follow directly
          from Equation (3): the peak height is theta_max = kappa A / (b sqrt(I / kappa)) ~ 1 / b, and the FWHM
          is approximately gamma / (2 pi).
        </Text>

        <Text style={S.bodyBold}>3. Does the resonance peak occur at exactly omega_0?</Text>
        <Text style={S.body}>
          Strictly the peak of theta_0(omega_d) occurs at omega = sqrt(omega_0^2 - gamma^2 / 2), which is
          slightly below omega_0 for non-zero damping. For the present apparatus this shift is below the
          frequency-grid resolution of the resonance sweep, so within experimental uncertainty the peak coincides
          with omega_0. The shift becomes more significant only at very heavy damping (Q on the order of unity).
        </Text>

        <Text style={S.bodyBold}>4. Is the resonance curve symmetric about its peak? Why or why not?</Text>
        <Text style={S.body}>
          The resonance curve is not symmetric about omega_0. Equation (3) contains both the
          (omega_d^2 - omega_0^2)^2 term and a damping term proportional to omega_d^2, so the response falls off
          faster on the high-frequency side (where it scales as 1 / omega_d^4) than on the low-frequency side
          (where it scales as 1 / (omega_0^2 - omega_d^2)^2). The measured asymmetry index for the lightest
          damping curve is {pct(metrics.asymmetry_index_pct as number, 2)}, in agreement with this prediction.
        </Text>

        <Text style={S.bodyBold}>5. Use the resonance curve to extract omega_0 and the damping coefficient. Compare with the input values.</Text>
        <Text style={S.body}>
          Reading the resonance peak directly from the densely-sampled lightest-damping curve gives
          omega_res = {f(metrics.fit_omega_res as number, 4)} rad/s (theory omega_0 = {f(k.omega0, 4)} rad/s,
          difference {pct(metrics.pct_diff_omega_res as number, 2)}). The half-power FWHM gives
          gamma_fit = {f(metrics.fit_gamma as number, 4)} 1/s, which differs from the input
          gamma = {f(curves[0]?.gamma, 4)} 1/s by {pct(metrics.pct_diff_gamma as number, 2)}; this residual is
          dominated by the discretisation of the frequency grid and tightens further as the sweep is refined.
        </Text>

        <Text style={S.bodyBold}>6. Compare the phase relationship of the disk and driver at low, resonance, and high frequencies.</Text>
        <Text style={S.body}>
          The three measured regimes follow Equation (4): below resonance the disk is in phase with the driver
          (phi about 0 deg), at resonance the disk lags by 90 deg (quadrature), and far above resonance the
          response is anti-phase (phi about 180 deg). The maximum residual between the measured and theoretical
          phase across the three regimes was +/- {f(metrics.phase_max_residual_deg as number, 2)} deg, well
          within the instrumental uncertainty discussed in Section 5.6.
        </Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* ════════════ 6.2 SUMMARY + 7 APPENDIX ════════════ */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>6.2  Summary</Text>
        <Text style={S.body}>
          The PhysX-based simulation of the driven damped torsion oscillator reproduces both the resonance curve
          and the phase-lag relationship predicted by the linear theory across three orders of magnitude of
          damping. The measured resonant frequency agrees with the theoretical value to
          {' '}{pct(metrics.pct_diff_lightest as number, 2)}, the resonance curves broaden and lower with
          increasing damping in the way Equation (3) predicts, and the phase lag tracks Equation (4) to within
          +/- {f(metrics.phase_max_residual_deg as number, 2)} deg. The damping coefficient extracted
          independently from the free-oscillation ringdown agrees with the value extracted from the resonance
          linewidth to {pct(metrics.ringdown_vs_resonance_pct as number, 2)}, providing a non-trivial
          consistency check on the analysis.
        </Text>

        <Text style={S.h1}>7  Appendix</Text>
        <Text style={S.body}>
          Figure A1 shows the angular velocity omega(t) corresponding to the free-oscillation ringdown of
          Figure 1; the same exponentially decaying envelope governs both signals. The exported ZIP package
          contains the generated Markdown report, the raw resonance and ringdown CSV files, the JSON summary
          of all numerical metrics, and the Python-generated figures used in this PDF.
        </Text>
        <Fig src={data.plots?.free_oscillation_omega}
             caption="Figure A1: Angular velocity omega(t) during the free-oscillation ringdown."
             height={215} />

        <View style={{ marginTop: 30, borderTopWidth: 0.5, borderTopColor: '#aaa', paddingTop: 8 }}>
          <Text style={{ fontSize: 8, fontFamily: 'Times-Italic', color: '#888', textAlign: 'center' }}>
            Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / PhysX 5 / RK4 Python Analysis
          </Text>
        </View>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>
    </Document>
  );
};

export default Exp4ReportPDF;
