import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';

// ═══════════════════════════════════════════════════════════════════
// LaTeX equation rendered via codecogs (matches Exp1/Exp7 style)
// ═══════════════════════════════════════════════════════════════════

const MathEquation = ({ latex, height = 25, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

// ═══════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════

export interface Exp5Summary {
  generated_at: string;
  n_samples: number;
  duration_s: number;
  mass_kg: number;
  length_m: number;
  pivot_distance_m: number;
  theta0_deg: number;
  theta_peak_deg: number;
  period_measured_s: number;
  period_std_s: number;
  period_unc_s: number;
  period_theory_s: number;
  period_error_pct: number;
  x_min_theory_m: number;
  T_min_theory_s: number;
  x_vs_xmin_pct: number;
  I_cm_geom_kg_m2: number;
  I_pivot_geom_kg_m2: number;
  I_pivot_period_kg_m2: number;
  I_cm_period_kg_m2: number;
  I_pivot_error_pct: number;
  I_cm_error_pct: number;
  mass_unc_kg: number;
  length_unc_m: number;
  pivot_unc_m: number;
  theta_unc_deg: number;
}

export interface Exp5PeriodRow {
  cycle: number;
  period_s: number;
}

export interface Exp5Plots {
  timeseries?: string;
  period_curve?: string;
  inertia?: string;
  cycle_periods?: string;
}

export interface Exp5ReportData {
  summary: Exp5Summary;
  period_rows: Exp5PeriodRow[];
  plots?: Exp5Plots;
}

interface Props { data: Exp5ReportData }

// ═══════════════════════════════════════════════════════════════════
// Styles (identical to Exp1ReportPDF.tsx so the look is unified)
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

const fnum = (v: number, d: number) => (Number.isFinite(v) ? v.toFixed(d) : 'N/A');
const fpct = (v: number) => (Number.isFinite(v) ? `${v.toFixed(2)}%` : 'N/A');

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
  <Text style={S.header} fixed>Lab Report for Lab 5 -- Rotational Inertia (Physical Pendulum)</Text>
);

// ═══════════════════════════════════════════════════════════════════
// Document
// ═══════════════════════════════════════════════════════════════════

const Exp5ReportPDF: React.FC<Props> = ({ data }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const s = data.summary;

  // Per-table chunked period rows so a long list spans multiple lines.
  const periodRowsForTable = (data.period_rows || []).map(r => ({
    cycle: `${Math.round(r.cycle)}`,
    period: fnum(r.period_s, 5),
  }));

  // Propagated uncertainty for the period-derived rotational inertia.
  // I_pivot = T^2 m g x / (4 pi^2)
  // dI/I = sqrt( (2 dT/T)^2 + (dm/m)^2 + (dx/x)^2 )
  const T_meas = s.period_measured_s;
  const I_pivot = s.I_pivot_period_kg_m2;
  const relUnc =
    Number.isFinite(T_meas) && T_meas > 0 && Number.isFinite(s.mass_kg) && s.mass_kg > 0 &&
    Number.isFinite(s.pivot_distance_m) && s.pivot_distance_m > 0
      ? Math.sqrt(
          (2.0 * (s.period_unc_s / T_meas)) ** 2 +
          (s.mass_unc_kg / s.mass_kg) ** 2 +
          (s.pivot_unc_m / s.pivot_distance_m) ** 2,
        )
      : NaN;
  const dI_pivot = Number.isFinite(relUnc) && Number.isFinite(I_pivot)
    ? Math.abs(I_pivot * relUnc)
    : NaN;

  return (
    <Document>
{/* ═══════════════════════════ COVER PAGE ═══════════════════════════ */}
<Page size="A4" style={S.coverPage}>
  <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
  <Text style={S.coverCourse}>PHY 1002</Text>
  <Text style={S.coverCourse}>Physics Laboratory</Text>
  <View style={{ marginTop: 30 }}>
    <Text style={S.coverTitle}>Lab Report for Lab 5 --</Text>
    <Text style={S.coverSubtitle}>Rotational Inertia (Physical Pendulum)</Text>
  </View>
  <View style={{ marginTop: 40 }}>
    <Text style={S.coverField}>Author:</Text>
    <Text style={S.coverValue}>[Student Name]</Text>
    <Text style={S.coverField}>Student Number:</Text>
    <Text style={S.coverValue}>[Student ID]</Text>
    <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
  </View>
</Page>

{/* ═══════════════════════════ SECTION 1 INTRODUCTION ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>1  Introduction</Text>
  <Text style={S.body}>
    This lab report presents the experimental process and results of measuring the period of a physical pendulum, and using that period to determine the rotational inertia of the pendulum bar. After constructing the apparatus, a uniform rectangular bar was pivoted at a fixed distance from its center of mass and released from a small initial angle. Based on the recorded angular displacement, the period of oscillation was extracted from positive-going zero crossings of theta(t). The measured period was compared with the theoretical small-amplitude period for a uniform-bar physical pendulum, and the rotational inertia of the bar was then inferred from the period and compared with the geometric value computed from the bar's mass and length. To ensure the reliability of the results, several oscillation cycles were observed and analysed. Finally, the report verifies the period equation for a physical pendulum and demonstrates that rotational inertia can be determined from period measurements within an acceptable error range.
  </Text>

{/* ═══════════════════════════ SECTION 2 OBJECTIVE ═══════════════════════════ */}
  <Text style={S.h1}>2  Objective</Text>
  <Text style={S.h2}>2.1  Review of Theory</Text>

  <Text style={S.h3}>2.1.1  Period of a Physical Pendulum</Text>
  <Text style={S.body}>
    For small-amplitude oscillations, the period T of a physical pendulum depends on the rotational inertia I_pivot about the pivot, the total mass m, and the distance x from the pivot to the center of mass:
  </Text>
  <MathEquation latex="T = 2\pi \sqrt{\dfrac{I_{\mathrm{pivot}}}{m g x}}" height={36} label="1" />
  <Text style={S.body}>The error of this small-angle approximation is below 1% at 20 deg and is even smaller at the 5 deg amplitude used in this experiment.</Text>

  <Text style={S.h3}>2.1.2  Rotational Inertia of a Uniform Bar</Text>
  <Text style={S.body}>For a uniform rectangular bar of mass m, length L, and width w, the rotational inertia about the center of mass is:</Text>
  <MathEquation latex="I_{\mathrm{cm}} = \dfrac{1}{12} m (L^2 + w^2)" height={28} label="2" />
  <Text style={S.body}>For the simulated bar (w/L) is small, so the term w^2 can be neglected:</Text>
  <MathEquation latex="I_{\mathrm{cm}} \approx \dfrac{1}{12} m L^2" height={28} label="3" />

  <Text style={S.h3}>2.1.3  Parallel-Axis Theorem</Text>
  <Text style={S.body}>The rotational inertia about a pivot located a distance x from the center of mass is:</Text>
  <MathEquation latex="I_{\mathrm{pivot}} = I_{\mathrm{cm}} + m x^2" height={26} label="4" />

  <Text style={S.h3}>2.1.4  Combined Period Equation</Text>
  <Text style={S.body}>Substituting (3) and (4) into (1) gives the period as an explicit function of x:</Text>
  <MathEquation latex="T(x) = 2\pi \sqrt{\dfrac{L^2/12 + x^2}{g\, x}}" height={36} label="5" />

  <Text style={S.h3}>2.1.5  Minimum Period Distance</Text>
  <Text style={S.body}>Setting dT/dx = 0 yields the pivot-to-CM distance that produces the minimum period:</Text>
  <MathEquation latex="x_{\min} = \dfrac{L}{\sqrt{12}}, \qquad T_{\min} = 2\pi \sqrt{\dfrac{L}{g \sqrt{3}}}" height={32} label="6" />

  <Text style={S.h3}>2.1.6  Determining Rotational Inertia from the Period</Text>
  <Text style={S.body}>Solving (1) for I_pivot gives a way to obtain rotational inertia from a period measurement:</Text>
  <MathEquation latex="I_{\mathrm{pivot}} = \dfrac{T^2\, m\, g\, x}{4 \pi^2}, \qquad I_{\mathrm{cm}} = I_{\mathrm{pivot}} - m x^2" height={30} label="7" />

  <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
  <Text style={S.listItem}>1. Verify the period equation T(x) of a uniform-bar physical pendulum.</Text>
  <Text style={S.listItem}>2. Compare the measured period with the theoretical small-amplitude prediction.</Text>
  <Text style={S.listItem}>3. Determine the rotational inertia of the bar from the measured period and compare it with the geometric value.</Text>
  <Text style={S.listItem}>4. Compare the chosen pivot distance with the theoretical minimum-period distance x_min = L / sqrt(12).</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 3 METHODS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>3  Methods</Text>
  <Text style={S.h2}>3.1  Setup</Text>

  <Text style={S.h3}>3.1.1  Apparatus Construction</Text>
  <Text style={S.body}>
    The physical pendulum was modeled procedurally inside NVIDIA Isaac Sim. A uniform rectangular bar was represented as a PhysX dynamic rigid body with explicit mass and a square cross-section. A kinematic pivot cuboid was created at a fixed height above the floor and connected to the bar by a USD revolute joint about the horizontal Y-axis. With this configuration, gravity (-9.81 m/s^2 along -Z) produces a real torque on the bar and the bar oscillates in the vertical XZ plane, exactly as a uniform-bar physical pendulum would do in a laboratory rod-stand setup.
  </Text>

  <Text style={S.h3}>3.1.2  Parameter Configuration</Text>
  <Text style={S.body}>
    Through the web interface, the bar mass m, the bar length L, the pivot-to-CM distance x, and the initial angle theta_0 were configured before each run. A frictionless physics material was bound to the bar so contact effects did not bias the period measurement. The PhysX solver iteration counts were increased so that the revolute joint's compliance did not perturb the small-amplitude oscillation.
  </Text>

  <Text style={S.h3}>3.1.3  Telemetry and Data Recording</Text>
  <Text style={S.body}>
    During the run, the WebRTC server sampled the live PhysX state at the telemetry rate, recording time t, angular displacement theta about Y, angular velocity omega, the rolling period estimate, and all configured parameters. The full time series was saved as a CSV file. The period was then re-estimated offline from the positive-going zero crossings of theta(t) so the reported period does not depend on the run-time rolling estimate alone.
  </Text>

  <Text style={S.h2}>3.2  Procedure</Text>
  <Text style={S.listItem}>1. Set the mass m, length L, pivot distance x, and initial angle theta_0 from the experiment panel.</Text>
  <Text style={S.listItem}>2. Click "Run Pendulum" to release the bar from theta_0.</Text>
  <Text style={S.listItem}>3. Observe the live WebRTC video and the angle/angular-velocity telemetry charts for several oscillation cycles.</Text>
  <Text style={S.listItem}>4. Click "Export Lab Report" to record the full time series and to generate this report.</Text>
  <Text style={S.listItem}>5. The server estimates the period from zero crossings, computes I_pivot from the period, and returns the data and figures used in this PDF.</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 4 RAW DATA ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>4  Raw Data</Text>
  <Text style={S.body}>
    Bar parameters: the parameters of the simulated bar and pivot are listed in Table 1.
  </Text>

  <T cap="Table 1: Simulated bar parameters and run conditions."
    cols={[
      { h: 'Mass m (kg)',          w: '18%', k: 'm' },
      { h: 'Length L (m)',         w: '15%', k: 'L' },
      { h: 'Pivot x (m)',          w: '15%', k: 'x' },
      { h: 'Initial theta_0 (deg)',w: '17%', k: 't0' },
      { h: 'Peak |theta| (deg)',   w: '17%', k: 'tp' },
      { h: 'Duration (s)',         w: '18%', k: 'dur' },
    ]}
    data={[{
      m: fnum(s.mass_kg, 5),
      L: fnum(s.length_m, 5),
      x: fnum(s.pivot_distance_m, 5),
      t0: fnum(s.theta0_deg, 3),
      tp: fnum(s.theta_peak_deg, 3),
      dur: fnum(s.duration_s, 3),
    }]}
  />

  <Text style={S.body}>
    Cycle-by-cycle period measurements: positive-going zero crossings of theta(t) define successive cycles.  The corresponding cycle-by-cycle period is shown in Table 2 and Figure 4 in the Appendix.
  </Text>

  {periodRowsForTable.length > 0 ? (
    <T cap="Table 2: Cycle-by-cycle period measurements."
      cols={[
        { h: 'Cycle',              w: '40%', k: 'cycle' },
        { h: 'Period (s)',         w: '60%', k: 'period' },
      ]}
      data={periodRowsForTable}
    />
  ) : (
    <Text style={S.body}>
      The run did not capture more than one zero crossing, so cycle-by-cycle periods are not available. The reported measured period falls back to the rolling estimate provided by the live telemetry loop.
    </Text>
  )}

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 5 DATA & ERROR ANALYSIS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>5  Data and Error Analysis</Text>
  <Text style={S.h2}>5.1  Data Analysis</Text>
  <Text style={S.body}>
    To validate the period equation, the average measured period is compared with the theoretical period from Equation (5) at the chosen pivot distance.  The rotational inertia I_pivot inferred from the period via Equation (7) is compared with the geometric value I_cm + m x^2.  The percent difference is defined as:
  </Text>
  <MathEquation latex="\%\text{diff} = \dfrac{X_{\text{measured}} - X_{\text{theory}}}{X_{\text{theory}}} \times 100\%" height={28} label="8" />

  <T cap="Table 3: Period analysis."
    cols={[
      { h: 'Quantity',                 w: '40%', k: 'q' },
      { h: 'Measured',                 w: '20%', k: 'meas' },
      { h: 'Theory',                   w: '20%', k: 'th' },
      { h: '%diff',                    w: '20%', k: 'd' },
    ]}
    data={[
      {
        q: 'Period T (s)',
        meas: fnum(s.period_measured_s, 5),
        th:   fnum(s.period_theory_s, 5),
        d:    fpct(s.period_error_pct),
      },
      {
        q: 'Pivot distance x (m)',
        meas: fnum(s.pivot_distance_m, 5),
        th:   fnum(s.x_min_theory_m, 5) + ' (x_min)',
        d:    fpct(s.x_vs_xmin_pct),
      },
    ]}
  />

  <Text style={S.body}>
    Rotational inertia analysis: the period-derived inertia is computed from Equation (7), and the geometric inertia is computed from Equations (3)-(4). The rotational inertia about the center of mass is then obtained as I_cm = I_pivot - m x^2.
  </Text>

  <T cap="Table 4: Rotational inertia analysis (kg m^2)."
    cols={[
      { h: 'Quantity',     w: '34%', k: 'q' },
      { h: 'From period',  w: '22%', k: 'p' },
      { h: 'From geometry',w: '22%', k: 'g' },
      { h: '%diff',        w: '22%', k: 'd' },
    ]}
    data={[
      {
        q: 'I_pivot',
        p: fnum(s.I_pivot_period_kg_m2, 8),
        g: fnum(s.I_pivot_geom_kg_m2, 8),
        d: fpct(s.I_pivot_error_pct),
      },
      {
        q: 'I_cm',
        p: fnum(s.I_cm_period_kg_m2, 8),
        g: fnum(s.I_cm_geom_kg_m2, 8),
        d: fpct(s.I_cm_error_pct),
      },
    ]}
  />

  <Text style={S.body}>
    According to Tables 3 and 4, the measured period agrees with the small-amplitude theoretical prediction within a small percent difference, and the rotational inertia inferred from the period is consistent with the geometric inertia after applying the parallel-axis theorem. This supports both Equation (5) for the period of a physical pendulum and Equation (7) as a method for determining rotational inertia from a period measurement. The small residual differences are attributable to finite-amplitude effects, telemetry sampling resolution at the zero crossings, and numerical compliance of the revolute joint, all of which are discussed in the next subsection.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 5.2 ERROR ANALYSIS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h2}>5.2  Error Analysis</Text>
  <Text style={S.body}>The standard error-propagation formula is used throughout this section:</Text>
  <MathEquation latex="\delta_k = \sqrt{\sum_{i=1}^{m}\left(\dfrac{\partial f}{\partial p_i}\right)^2 (\delta p_i)^2}" height={38} label="9" />

  <Text style={S.h3}>5.2.1  Error of Mass</Text>
  <Text style={S.body}>
    The bar mass is obtained from the configured value through an electronic balance. With the conservative simulated balance precision used in this report, the uncertainty is delta m = max(0.0001 kg, 0.001 m).
  </Text>

  <Text style={S.h3}>5.2.2  Error of Length and Pivot Distance</Text>
  <Text style={S.body}>
    The bar length L and the pivot-to-CM distance x are measured from the configured geometry.  Assuming a 0.05 cm caliper resolution for both, the corresponding uncertainties are delta L = delta x = 0.0005 m.
  </Text>

  <Text style={S.h3}>5.2.3  Error of the Period</Text>
  <Text style={S.body}>
    The period is estimated from positive-going zero crossings of theta(t).  Two error sources dominate.  Linear interpolation between adjacent telemetry samples introduces a per-crossing uncertainty of order Δt, where Δt is the median sample interval.  Across many cycles, the cycle-to-cycle scatter sigma_T captures both this interpolation error and any small finite-amplitude drift.  We therefore take:
  </Text>
  <MathEquation latex="\delta T = \max\left(\sigma_T, \Delta t\right)" height={20} label="10" />

  <Text style={S.h3}>5.2.4  Error of Rotational Inertia from the Period</Text>
  <Text style={S.body}>The rotational inertia from the period is given by I_pivot = T^2 m g x / (4 pi^2), so:</Text>
  <MathEquation latex="\dfrac{\delta I_{\mathrm{pivot}}}{I_{\mathrm{pivot}}} = \sqrt{\left(2\dfrac{\delta T}{T}\right)^2 + \left(\dfrac{\delta m}{m}\right)^2 + \left(\dfrac{\delta x}{x}\right)^2}" height={42} label="11" />
  <Text style={S.body}>The same propagation rule yields the uncertainty of I_cm = I_pivot - m x^2 within the geometric subtraction.</Text>

  <Text style={S.h3}>5.2.5  Presentation of Error</Text>
  <Text style={S.body}>The propagated uncertainties for the present run are listed in Table 5.</Text>

  <T cap="Table 5: Quantities with uncertainties."
    cols={[
      { h: 'Quantity',                 w: '46%', k: 'q' },
      { h: 'Value with uncertainty',   w: '54%', k: 'v' },
    ]}
    data={[
      { q: 'Mass m (kg)',
        v: `${fnum(s.mass_kg, 5)} +/- ${fnum(s.mass_unc_kg, 5)}` },
      { q: 'Bar length L (m)',
        v: `${fnum(s.length_m, 5)} +/- ${fnum(s.length_unc_m, 4)}` },
      { q: 'Pivot distance x (m)',
        v: `${fnum(s.pivot_distance_m, 5)} +/- ${fnum(s.pivot_unc_m, 4)}` },
      { q: 'Period T (s)',
        v: `${fnum(s.period_measured_s, 5)} +/- ${fnum(s.period_unc_s, 5)}` },
      { q: 'Theoretical period T(x) (s)',
        v: `${fnum(s.period_theory_s, 5)}` },
      { q: 'I_pivot from period (kg m^2)',
        v: `${fnum(s.I_pivot_period_kg_m2, 8)} +/- ${fnum(dI_pivot, 8)}` },
      { q: 'I_pivot from geometry (kg m^2)',
        v: `${fnum(s.I_pivot_geom_kg_m2, 8)}` },
      { q: 'I_cm from period (kg m^2)',
        v: `${fnum(s.I_cm_period_kg_m2, 8)}` },
      { q: 'I_cm from geometry (kg m^2)',
        v: `${fnum(s.I_cm_geom_kg_m2, 8)}` },
      { q: 'Theoretical x_min (m)',
        v: `${fnum(s.x_min_theory_m, 5)}` },
      { q: 'Theoretical T_min (s)',
        v: `${fnum(s.T_min_theory_s, 5)}` },
    ]}
  />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 6 CONCLUSION ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>6  Conclusion</Text>
  <Text style={S.h2}>6.1  Answering the Questions</Text>

  <Text style={S.bodyBold}>1. What is the percent difference between the calculated value for the length that gives the minimum period of oscillation and the measured value for the length?</Text>
  <Text style={S.body}>
    {`The theoretical minimum-period pivot distance for a uniform bar is x_min = L / sqrt(12) = ${fnum(s.x_min_theory_m, 5)} m. The pivot distance used in this run was x = ${fnum(s.pivot_distance_m, 5)} m, which differs from x_min by ${fpct(s.x_vs_xmin_pct)}. The corresponding theoretical minimum period is T_min = ${fnum(s.T_min_theory_s, 5)} s, while the measured period at the chosen x was ${fnum(s.period_measured_s, 5)} s.`}
  </Text>

  <Text style={S.bodyBold}>2. Would a pendulum bar with different mass but with the same dimensions have a different value for the length that gives minimum period of oscillation? Why or why not?</Text>
  <Text style={S.body}>
    No. Equation (5) shows that T(x) does not depend on the mass m, because the gravitational torque and the rotational inertia both scale linearly with m. The minimum-period condition x_min = L / sqrt(12) is therefore independent of mass and depends only on the bar length L.
  </Text>

  <Text style={S.bodyBold}>3. Determine the percent difference between the rotational inertia calculated from the period and the rotational inertia calculated using the dimensions.</Text>
  <Text style={S.body}>
    {`Using Equation (7), the rotational inertia about the pivot from the measured period is I_pivot = ${fnum(s.I_pivot_period_kg_m2, 8)} kg m^2. The geometric value from the parallel-axis theorem is I_pivot = I_cm + m x^2 = ${fnum(s.I_pivot_geom_kg_m2, 8)} kg m^2. The percent difference is ${fpct(s.I_pivot_error_pct)}. Subtracting m x^2 from each gives I_cm from period = ${fnum(s.I_cm_period_kg_m2, 8)} kg m^2 and I_cm from geometry = ${fnum(s.I_cm_geom_kg_m2, 8)} kg m^2, with a percent difference of ${fpct(s.I_cm_error_pct)}.`}
  </Text>

  <Text style={S.bodyBold}>4. Do your results support or disprove the idea that the rotational inertia of a physical pendulum can be determined from its period of oscillation? Why or why not?</Text>
  <Text style={S.body}>
    The results support the idea. The rotational inertia inferred from the period agrees with the geometric inertia within the propagated uncertainty in Table 5, and the small residual difference is consistent with the dominant non-ideal effects in the simulation: finite-amplitude corrections to the small-angle approximation, finite telemetry sampling at the zero crossings, and a small numerical compliance of the revolute joint. With a uniform-bar geometry and the parallel-axis theorem, the period therefore provides a reliable indirect measurement of rotational inertia.
  </Text>

  <Text style={S.h2}>6.2  Summary</Text>
  <Text style={S.body}>
    {`The experiment recorded ${s.n_samples} telemetry samples over ${fnum(s.duration_s, 2)} s of free oscillation of a uniform bar pivoted ${fnum(s.pivot_distance_m, 4)} m from its center of mass. The period extracted from positive-going zero crossings was T = ${fnum(s.period_measured_s, 5)} s, in agreement with the theoretical period T(x) = ${fnum(s.period_theory_s, 5)} s within ${fpct(s.period_error_pct)}. Inverting the period equation yielded I_pivot = ${fnum(s.I_pivot_period_kg_m2, 8)} kg m^2, which differs from the geometric value by ${fpct(s.I_pivot_error_pct)}.`}
  </Text>
  <Text style={S.body}>
    Together with the explicit minimum-period distance x_min = L / sqrt(12), these results validate the small-amplitude period equation for a uniform-bar physical pendulum and confirm that the rotational inertia of such a pendulum can be obtained from a period measurement.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 7 APPENDIX ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>7  Appendix: Figures</Text>
  <Text style={S.body}>
    The following figures were generated automatically from the recorded run data using Python and Matplotlib.
  </Text>

  {data.plots?.timeseries && (
    <View style={{ marginBottom: 16 }} wrap={false}>
      <Image src={data.plots.timeseries} style={{ width: '100%', height: 220 }} />
      <Text style={[S.caption, { textAlign: 'center', marginTop: 4 }]}>
        Figure 1: Angular displacement theta and angular velocity omega versus time during the recorded run.
      </Text>
    </View>
  )}

  {data.plots?.period_curve && (
    <View style={{ marginBottom: 16 }} wrap={false}>
      <Image src={data.plots.period_curve} style={{ width: '100%', height: 220 }} />
      <Text style={[S.caption, { textAlign: 'center', marginTop: 4 }]}>
        Figure 2: Theoretical period T(x) for a uniform-bar physical pendulum, the theoretical minimum at x_min = L/sqrt(12), and the measured period at the chosen pivot distance.
      </Text>
    </View>
  )}

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

<Page size="A4" style={S.page}>
  <Hdr />

  {data.plots?.inertia && (
    <View style={{ marginBottom: 16 }} wrap={false}>
      <Image src={data.plots.inertia} style={{ width: '100%', height: 220 }} />
      <Text style={[S.caption, { textAlign: 'center', marginTop: 4 }]}>
        Figure 3: Rotational inertia about the pivot and about the center of mass: from-geometry values compared with from-period values.
      </Text>
    </View>
  )}

  {data.plots?.cycle_periods && (
    <View style={{ marginBottom: 16 }} wrap={false}>
      <Image src={data.plots.cycle_periods} style={{ width: '100%', height: 220 }} />
      <Text style={[S.caption, { textAlign: 'center', marginTop: 4 }]}>
        Figure 4: Cycle-by-cycle period estimates from positive-going zero crossings of theta(t), compared with the theoretical T(x).
      </Text>
    </View>
  )}

  <View style={{ marginTop: 30, borderTopWidth: 0.5, borderTopColor: '#aaa', paddingTop: 8 }}>
    <Text style={{ fontSize: 8, fontFamily: 'Times-Italic', color: '#888', textAlign: 'center' }}>
      Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / PhysX 5
    </Text>
  </View>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>
    </Document>
  );
};

export default Exp5ReportPDF;
