import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';

const MathEquation = ({ latex, height = 24, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

export interface Exp2PeriodRow {
  amp_set: number | null;
  amp_measured: number | null;
  period_measured: number | null;
  T0_theory: number | null;
  T0_measured_from_period_zero: number | null;
  T_series_2term: number | null;
  T_series_3term: number | null;
  T_series_4term: number | null;
  T_series_5term: number | null;
}

export interface Exp2ReportData {
  T0_theory?: number;
  T0_measured?: number;
  amp_mid?: number | null;
  sweep_points?: number;
  params?: Record<string, number>;
  props?: Record<string, number | null>;
  metrics?: Record<string, number | null>;
  period_rows?: Exp2PeriodRow[];
  plots?: {
    overlay?: string;
    period?: string;
    error?: string;
    small_amp?: string;
    large_amp?: string;
  };
  report_md: string;
  period_csv: string;
  zip_b64: string;
}

interface Props {
  data: Exp2ReportData;
}

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
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 4, marginTop: 10 },
  pageNum: { position: 'absolute', bottom: 30, right: 50, fontSize: 9, color: '#555' },
  tbl: { marginBottom: 12, width: '100%' },
  tblTop: { borderTopWidth: 1.5, borderTopColor: '#000' },
  tblMid: { borderTopWidth: 0.6, borderTopColor: '#000' },
  tblBot: { borderBottomWidth: 1.5, borderBottomColor: '#000' },
  row: { flexDirection: 'row', minHeight: 16, alignItems: 'center' },
  thCell: { fontSize: 8.5, fontFamily: 'Times-Bold', textAlign: 'center', paddingVertical: 3, paddingHorizontal: 1 },
  tdCell: { fontSize: 8.5, textAlign: 'center', paddingVertical: 2.5, paddingHorizontal: 1 },
  listItem: { fontSize: 11, textAlign: 'justify', marginBottom: 4, paddingLeft: 10 },
});

const f = (v: number | null | undefined, d: number) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : 'N/A';
const pct = (v: number | null | undefined, d = 2) => typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(d)}%` : 'N/A';
const deg = (rad: number | null | undefined) => typeof rad === 'number' && Number.isFinite(rad) ? (rad * 180 / Math.PI).toFixed(1) : 'N/A';

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
  <Text style={S.header} fixed>Lab Report for Lab 2 -- Large Amplitude Pendulum</Text>
);

const Fig: React.FC<{ src?: string; caption: string; height?: number }> = ({ src, caption, height = 205 }) => (
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

const Exp2ReportPDF: React.FC<Props> = ({ data }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const rows = data.period_rows ?? [];
  const displayedRows = rows.slice(0, 12);
  const p = data.params ?? {};
  const props = data.props ?? {};
  const m = data.metrics ?? {};

  const parameterRows = [
    { q: 'Rod length L (m)', v: f(p.rod_length, 3), u: 'm' },
    { q: 'Rod mass', v: f(p.rod_mass, 4), u: 'kg' },
    { q: 'Lower bob mass', v: f(p.bob_mass_1, 4), u: 'kg' },
    { q: 'Upper bob mass', v: f(p.bob_mass_2, 4), u: 'kg' },
    { q: 'Pivot to lower bob r1', v: f(p.r1, 3), u: 'm' },
    { q: 'Pivot to upper bob r2', v: f(p.r2, 3), u: 'm' },
    { q: 'Damping coefficient', v: f(p.damping, 4), u: 'N m s/rad' },
    { q: 'Sampling interval', v: f(p.dt, 5), u: 's' },
  ];

  return (
    <Document>
      <Page size="A4" style={S.coverPage}>
        <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
        <Text style={S.coverCourse}>PHY 1002</Text>
        <Text style={S.coverCourse}>Physics Laboratory</Text>
        <View style={{ marginTop: 30 }}>
          <Text style={S.coverTitle}>Lab Report for Lab 2 --</Text>
          <Text style={S.coverSubtitle}>Large Amplitude Pendulum</Text>
        </View>
        <View style={{ marginTop: 40 }}>
          <Text style={S.coverField}>Author:</Text>
          <Text style={S.coverValue}>[Student Name]</Text>
          <Text style={S.coverField}>Student Number:</Text>
          <Text style={S.coverValue}>[Student ID]</Text>
          <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
        </View>
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>1  Introduction</Text>
        <Text style={S.body}>
          This experiment investigated the motion of a physical pendulum at both small and large amplitudes. For small oscillations, the sine of the angular displacement can be approximated by the angle itself, and the pendulum behaves almost as a simple harmonic oscillator. At large amplitudes this approximation fails, so the angular displacement, velocity, acceleration, and period must be compared with the large-amplitude series solution.
        </Text>

        <Text style={S.h1}>2  Objective</Text>
        <Text style={S.h2}>2.1  Review of Theory</Text>
        <Text style={S.body}>For a physical pendulum with moment of inertia I about the pivot and center-of-mass offset d, the small-amplitude period is:</Text>
        <MathEquation latex="T_0 = 2\pi\sqrt{\frac{I}{mgd}}" height={28} label="1" />
        <Text style={S.body}>When the amplitude is large, the restoring torque is nonlinear. The period is expanded as:</Text>
        <MathEquation latex="T = T_0\left[1+\frac{1}{4}\sin^2\frac{\theta_0}{2}+\frac{9}{64}\sin^4\frac{\theta_0}{2}+\frac{25}{256}\sin^6\frac{\theta_0}{2}+\frac{1225}{16384}\sin^8\frac{\theta_0}{2}\right]" height={42} label="2" />
        <Text style={S.body}>This report uses the measured simulation data to test how well the small-angle period and the truncated series describe the observed period.</Text>

        <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
        <Text style={S.listItem}>1. Compare small-amplitude and large-amplitude theta, omega, and angular acceleration curves.</Text>
        <Text style={S.listItem}>2. Measure the period as a function of amplitude.</Text>
        <Text style={S.listItem}>3. Quantify the error caused by using the small-angle approximation at large angles.</Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>3  Methods</Text>
        <Text style={S.body}>
          The experiment was run in Isaac Sim with a visual compound pendulum and a Python RK4 integrator. The pendulum used a 0.35 m lightweight rod with two equal bobs mounted at slightly different distances from the pivot, creating a small nonzero center-of-mass offset. The simulation recorded angular displacement, angular velocity, and angular acceleration at each time step.
        </Text>
        <Text style={S.body}>
          A small-amplitude run and a large-amplitude run were first generated for qualitative comparison. A near-zero-amplitude run was then used to estimate T0 from ten cycles. Finally, amplitudes from {f(p.amp_start, 2)} rad to {f(p.amp_end, 2)} rad were swept in {f(p.amp_step, 2)} rad increments. For each sweep point, the period was obtained from zero crossings separated by two full cycles, while the representative amplitude was measured from the central positive peak.
        </Text>

        <T cap="Table 1: Simulation and pendulum parameters."
          cols={[
            { h: 'Quantity', w: '48%', k: 'q' },
            { h: 'Value', w: '26%', k: 'v' },
            { h: 'Unit', w: '26%', k: 'u' },
          ]}
          data={parameterRows}
        />

        <T cap="Table 2: Derived physical quantities."
          cols={[
            { h: 'Quantity', w: '45%', k: 'q' },
            { h: 'Value', w: '30%', k: 'v' },
            { h: 'Unit', w: '25%', k: 'u' },
          ]}
          data={[
            { q: 'Total mass m', v: f(props.m_total, 4), u: 'kg' },
            { q: 'Center-of-mass offset d', v: f(props.d, 5), u: 'm' },
            { q: 'Moment of inertia I', v: f(props.I, 6), u: 'kg m^2' },
            { q: 'Theoretical T0', v: f(data.T0_theory, 5), u: 's' },
            { q: 'Measured T0', v: f(data.T0_measured, 5), u: 's' },
          ]}
        />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data</Text>
        <Fig src={data.plots?.small_amp} caption={`Figure 1: Small-amplitude theta, omega, and alpha versus time at A0 = ${f(p.small_amp, 2)} rad.`} />
        <Fig src={data.plots?.large_amp} caption={`Figure 2: Large-amplitude theta, omega, and alpha versus time at A0 = ${f(p.large_amp, 2)} rad.`} />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data</Text>
        <T cap="Table 3: Period measurements and series predictions from the amplitude sweep."
          cols={[
            { h: 'A set (rad)', w: '11%', k: 'set' },
            { h: 'A meas. (rad)', w: '12%', k: 'amp' },
            { h: 'A meas. (deg)', w: '12%', k: 'deg' },
            { h: 'T meas. (s)', w: '12%', k: 'tm' },
            { h: 'T0 (s)', w: '11%', k: 't0' },
            { h: '2 terms (s)', w: '14%', k: 't2' },
            { h: '3 terms (s)', w: '14%', k: 't3' },
            { h: '5 terms (s)', w: '14%', k: 't5' },
          ]}
          data={displayedRows.map(r => ({
            set: f(r.amp_set, 2),
            amp: f(r.amp_measured, 4),
            deg: deg(r.amp_measured),
            tm: f(r.period_measured, 5),
            t0: f(r.T0_theory, 5),
            t2: f(r.T_series_2term, 5),
            t3: f(r.T_series_3term, 5),
            t5: f(r.T_series_5term, 5),
          }))}
        />
        <Text style={S.body}>
          The full CSV file is included in the exported ZIP package. The table above includes {displayedRows.length} of {rows.length || data.sweep_points || 0} sweep points for readability.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Data and Error Analysis</Text>
        <Text style={S.h2}>5.1  Period-Amplitude Relationship</Text>
        <Fig src={data.plots?.period} caption="Figure 3: Measured period and large-amplitude series approximations versus amplitude." height={220} />
        <Text style={S.body}>
          The measured period increased with amplitude, while the small-angle period remained constant. This behavior is expected because the exact equation of motion contains sin(theta), not theta. The added terms in Equation (2) improve the prediction as amplitude grows, especially below about 0.8 rad.
        </Text>

        <Text style={S.h2}>5.2  Error Analysis</Text>
        <Fig src={data.plots?.error} caption="Figure 4: Percent error from assuming the small-angle period for all amplitudes." height={210} />
        <Text style={S.body}>
          The maximum observed small-angle error across the sweep was {pct(m.max_small_angle_error_pct, 2)}, and the mean error was {pct(m.avg_small_angle_error_pct, 2)}. The predicted small-angle period error is about {pct(m.error_at_20_deg_pct, 2)} at 20 degrees and {pct(m.error_at_45_deg_pct, 2)} at 45 degrees.
        </Text>
        <Text style={S.body}>
          Sources of uncertainty include finite sampling interval, damping, and peak or zero-crossing detection. The RK4 time step of {f(p.dt, 5)} s makes the numerical integration error small compared with the physical effect of amplitude on period.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>6  Conclusion</Text>
        <Text style={S.h2}>6.1  Answers to Required Questions</Text>
        <Text style={S.bodyBold}>1. Why are two terms enough below 45 degrees?</Text>
        <Text style={S.body}>
          Below 45 degrees, sin(theta0/2) is still modest, so the higher powers in the series are very small. The first correction term captures most of the amplitude dependence, and the remaining terms change the period only slightly.
        </Text>
        <Text style={S.bodyBold}>2. Why does the approximation begin to fail above 90 degrees?</Text>
        <Text style={S.body}>
          Near and above 90 degrees, sin(theta0/2) is large enough that higher-order terms are no longer negligible. A five-term truncation is still only an approximation to the elliptic-integral result, so its error grows at very large amplitudes.
        </Text>
        <Text style={S.bodyBold}>3. How many terms are needed near 3.0 rad?</Text>
        <Text style={S.body}>
          Many more terms, or preferably direct numerical evaluation of the elliptic integral, would be required. At 3.0 rad the amplitude is close to the unstable inverted position, so the series converges slowly and the period becomes very sensitive to amplitude.
        </Text>
        <Text style={S.bodyBold}>4. What are the errors at 20 degrees and 45 degrees?</Text>
        <Text style={S.body}>
          The generated analysis gives approximately {pct(m.error_at_20_deg_pct, 2)} at 20 degrees and {pct(m.error_at_45_deg_pct, 2)} at 45 degrees when the small-angle period is used as if it were valid for all amplitudes.
        </Text>

        <Text style={S.h2}>6.2  Summary</Text>
        <Text style={S.body}>
          The simulation confirms that large-amplitude pendulum motion is not exactly sinusoidal and that the period increases with amplitude. The small-angle period is reliable only for sufficiently small angles, while the series expansion gives a much better description of the measured data over the tested range.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>7  Appendix</Text>
        <Fig src={data.plots?.overlay} caption="Figure 5: Overlay comparison of small- and large-amplitude angular displacement." height={215} />
        <Text style={S.body}>
          The exported ZIP package contains the generated Markdown report, CSV data files, and Python-generated plots used in this PDF. This PDF was generated automatically from the Experiment 2 simulation output.
        </Text>
        <View style={{ marginTop: 30, borderTopWidth: 0.5, borderTopColor: '#aaa', paddingTop: 8 }}>
          <Text style={{ fontSize: 8, fontFamily: 'Times-Italic', color: '#888', textAlign: 'center' }}>
            Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / RK4 Python Analysis
          </Text>
        </View>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>
    </Document>
  );
};

export default Exp2ReportPDF;
