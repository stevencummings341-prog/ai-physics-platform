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

export interface Exp6ReportSummary {
  generated_at?: string;
  n_samples?: number;
  duration_s?: number;
  steady_start_s?: number;
  mass_kg?: number;
  radius_target_m?: number;
  omega_target_rad_s?: number;
  spring_k_N_m?: number;
  damper_N_s_m?: number;
  mean_radius_m?: number;
  std_radius_m?: number;
  mean_speed_m_s?: number;
  std_speed_m_s?: number;
  mean_omega_rad_s?: number;
  mean_extension_m?: number;
  mean_force_N?: number;
  std_force_N?: number;
  mean_theory_force_N?: number;
  mean_kinematic_force_N?: number;
  force_error_pct?: number;
  kinematic_error_pct?: number;
  mass_unc_kg?: number;
  radius_unc_m?: number;
  speed_unc_m_s?: number;
  force_unc_N?: number;
  propagated_force_unc_N?: number;
}

export interface Exp6ReportData {
  summary?: Exp6ReportSummary;
  plots?: {
    timeseries?: string;
    force_compare?: string;
    orbit?: string;
    error?: string;
  };
}

interface Props {
  data: Exp6ReportData;
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
  bodyItalic: { fontSize: 11, fontFamily: 'Times-Italic', textAlign: 'justify', marginBottom: 4 },
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 4, marginTop: 10 },
  eq: { fontSize: 10.5, fontFamily: 'Courier', textAlign: 'center', marginVertical: 5, backgroundColor: '#f5f5f5', padding: 6, borderRadius: 2 },
  pageNum: { position: 'absolute', bottom: 30, right: 50, fontSize: 9, color: '#555' },
  tbl: { marginBottom: 12, width: '100%' },
  tblTop: { borderTopWidth: 1.5, borderTopColor: '#000' },
  tblMid: { borderTopWidth: 0.6, borderTopColor: '#000' },
  tblBot: { borderBottomWidth: 1.5, borderBottomColor: '#000' },
  row: { flexDirection: 'row', minHeight: 16, alignItems: 'center' },
  thCell: { fontSize: 8.7, fontFamily: 'Times-Bold', textAlign: 'center', paddingVertical: 3, paddingHorizontal: 1 },
  tdCell: { fontSize: 8.7, textAlign: 'center', paddingVertical: 2.5, paddingHorizontal: 1 },
  listItem: { fontSize: 11, textAlign: 'justify', marginBottom: 4, paddingLeft: 10 },
  small: { fontSize: 9.5, color: '#333', textAlign: 'justify', marginBottom: 4 },
});

const f = (v: number | null | undefined, d: number) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : 'N/A';
const pct = (v: number | null | undefined, d = 2) => typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(d)}%` : 'N/A';

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
  <Text style={S.header} fixed>Lab Report for Lab 6 -- Centripetal Force</Text>
);

const Fig: React.FC<{ src?: string; caption: string; height?: number }> = ({ src, caption, height = 215 }) => (
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

const Exp6ReportPDF: React.FC<Props> = ({ data }) => {
  const s = data.summary ?? {};
  const plots = data.plots ?? {};
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const setupRows = [
    { q: 'Moving mass m (kg)', v: `${f(s.mass_kg, 5)} +/- ${f(s.mass_unc_kg, 5)}` },
    { q: 'Target radius r (m)', v: f(s.radius_target_m, 5) },
    { q: 'Target angular speed omega (rad/s)', v: f(s.omega_target_rad_s, 4) },
    { q: 'Spring stiffness k (N/m)', v: f(s.spring_k_N_m, 2) },
    { q: 'Damping c (N*s/m)', v: f(s.damper_N_s_m, 3) },
    { q: 'Number of raw samples', v: f(s.n_samples, 0) },
    { q: 'Recorded duration (s)', v: f(s.duration_s, 3) },
    { q: 'Steady-state window starts at (s)', v: f(s.steady_start_s, 3) },
  ];

  const resultRows = [
    { q: 'Mean actual radius (m)', v: `${f(s.mean_radius_m, 5)} +/- ${f(s.std_radius_m, 5)}` },
    { q: 'Mean tangential speed (m/s)', v: `${f(s.mean_speed_m_s, 5)} +/- ${f(s.std_speed_m_s, 5)}` },
    { q: 'Mean live omega (rad/s)', v: f(s.mean_omega_rad_s, 4) },
    { q: 'Mean spring extension (m)', v: f(s.mean_extension_m, 6) },
    { q: 'Measured spring force k*dx (N)', v: `${f(s.mean_force_N, 5)} +/- ${f(s.std_force_N, 5)}` },
    { q: 'Reference force m*omega^2*r (N)', v: f(s.mean_theory_force_N, 5) },
    { q: 'Kinematic force m*v^2/r (N)', v: f(s.mean_kinematic_force_N, 5) },
    { q: 'Error vs reference (%)', v: pct(s.force_error_pct, 3) },
    { q: 'Error vs kinematic force (%)', v: pct(s.kinematic_error_pct, 3) },
  ];

  return (
    <Document>
      <Page size="A4" style={S.coverPage}>
        <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
        <Text style={S.coverCourse}>PHY 1002</Text>
        <Text style={S.coverCourse}>Physics Laboratory</Text>
        <View style={{ marginTop: 30 }}>
          <Text style={S.coverTitle}>Lab Report for Lab 6 --</Text>
          <Text style={S.coverSubtitle}>Centripetal Force</Text>
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
          This lab report presents the experimental process and results for the centripetal-force experiment.  A moving mass was constrained to travel in a circular path, and the inward force needed to maintain the circular motion was measured.  The original physical apparatus uses a force sensor and a photogate; in this simulation, a PhysX spring constraint supplied the inward force and the bob velocity was read from the physics engine.
        </Text>
        <Text style={S.body}>
          The experiment was designed to test how centripetal force depends on mass, tangential speed, and radius.  The report focuses on the steady-state part of the motion, after the rotating arm has finished accelerating and the bob motion is close to uniform circular motion.
        </Text>

        <Text style={S.h1}>2  Objective</Text>
        <Text style={S.body}>
          The objective was to verify the centripetal-force relationship and to compare three force estimates: the spring force measured from the PhysX constraint, the reference value computed from the controlled angular velocity, and the value calculated from the PhysX-measured tangential speed and radius.
        </Text>

        <Text style={S.h2}>2.1  Review of Theory</Text>
        <Text style={S.body}>
          An object in uniform circular motion has a velocity that continuously changes direction.  Therefore, it must have an inward acceleration and a corresponding net inward force.  This force is called the centripetal force.
        </Text>
        <MathEquation latex="F_c = \frac{m v^2}{r}" height={28} label="1" />
        <Text style={S.body}>
          In Equation (1), m is the mass of the object, v is its tangential speed, and r is the radius of the circular path.  Since the tangential speed can be written as v = omega*r, the same result can be expressed as:
        </Text>
        <MathEquation latex="F_c = m \omega^2 r" height={24} label="2" />
        <Text style={S.body}>
          The centripetal force is not an additional new force.  It is the resultant inward force supplied by real interactions, such as tension, friction, gravity, or in this simulation the spring force of the constraint.
        </Text>
        <MathEquation latex="F_{\mathrm{spring}} = k \Delta x" height={24} label="3" />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>3  Methods</Text>
        <Text style={S.h2}>3.1  Physical Model</Text>
        <Text style={S.body}>
          The simulated apparatus was built as a rotating arm with a dynamic bob attached by a spring-like prismatic joint.  The rotor was driven at the selected angular speed, while the bob was allowed to respond dynamically.  The joint's linear drive supplied a spring force toward the target radius.  PhysX integrated the bob's motion, so the measured force was obtained from the simulated spring extension instead of being prescribed by the analytical formula.
        </Text>
        <Text style={S.body}>
          Gravity was kept on.  A frictionless table supported the bob, representing the normal force of the real apparatus.  The bob's vertical motion and tipping rotations were constrained to avoid unphysical wobble, while horizontal circular motion remained dynamic.
        </Text>

        <Text style={S.h2}>3.2  Data Collection</Text>
        <Text style={S.body}>
          The rotor speed was ramped smoothly to the target value.  During the run, the server recorded the bob position, velocity, radius, spring extension, spring force, and reference force.  Data from the transient ramp were retained in the raw CSV, but steady-state averages were used for numerical comparison.
        </Text>

        <T cap="Table 1: Apparatus settings and data acquisition information."
          cols={[{ h: 'Quantity', w: '55%', k: 'q' }, { h: 'Value', w: '45%', k: 'v' }]}
          data={setupRows}
        />

        <Text style={S.h1}>4  Raw Data</Text>
        <Text style={S.body}>
          The full raw time-series table is exported as a CSV file together with this report.  Table 2 summarizes the steady-state values used for analysis.
        </Text>
        <T cap="Table 2: Steady-state raw and derived data."
          cols={[{ h: 'Quantity', w: '55%', k: 'q' }, { h: 'Value', w: '45%', k: 'v' }]}
          data={resultRows}
        />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Figures</Text>
        <Fig src={plots.timeseries} height={270} caption="Figure 1: Actual radius, tangential speed, and centripetal force versus time.  The dashed line in the force panel is the theoretical reference m*omega^2*r." />
        <Fig src={plots.force_compare} height={245} caption="Figure 2: Measured spring force, force calculated from PhysX-measured v and r, and analytical reference force." />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Figures (continued)</Text>
        <Fig src={plots.orbit} height={270} caption="Figure 3: Top-view orbit of the bob.  The dashed circle indicates the target radius of the spring drive." />
        <Fig src={plots.error} height={235} caption="Figure 4: Percent error between the measured spring force and the analytical reference.  The highlighted region marks the steady-state analysis window." />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>6  Data and Error Analysis</Text>
        <Text style={S.h2}>6.1  Force Comparison</Text>
        <Text style={S.body}>
          In the steady-state window, the measured spring force was {f(s.mean_force_N, 5)} N, while the reference force calculated from m*omega^2*r was {f(s.mean_theory_force_N, 5)} N.  The percent difference was {pct(s.force_error_pct, 3)}.  The force calculated from the PhysX-measured tangential speed and radius was {f(s.mean_kinematic_force_N, 5)} N, which provides an independent check using the simulated motion.
        </Text>
        <Text style={S.body}>
          The initial ramp has a visibly larger deviation because the bob is not yet in uniform circular motion.  During that time, part of the spring force changes radial motion and does not solely provide centripetal acceleration.  Once the transient decays, the three force estimates become much closer.
        </Text>

        <Text style={S.h2}>6.2  Error Analysis</Text>
        <Text style={S.body}>
          The simulated measurement uncertainties were chosen to match the scale of the laboratory instruments: delta m = {f(s.mass_unc_kg, 5)} kg, delta r = {f(s.radius_unc_m, 4)} m, and delta v = {f(s.speed_unc_m_s, 4)} m/s.  Propagating these through Equation (1) gives:
        </Text>
        <MathEquation latex="\delta F = F\sqrt{\left(\frac{\delta m}{m}\right)^2+\left(2\frac{\delta v}{v}\right)^2+\left(\frac{\delta r}{r}\right)^2}" height={34} label="4" />
        <Text style={S.body}>
          The propagated uncertainty of the kinematic force was approximately {f(s.propagated_force_unc_N, 5)} N.  Additional deviations may be caused by residual radial oscillation, numerical constraint compliance, finite telemetry sampling, and damping in the spring drive.
        </Text>

        <Text style={S.h2}>6.3  Interpretation</Text>
        <Text style={S.body}>
          The result is consistent with the expected centripetal-force model.  The measured force is slightly different from the reference because the simulated apparatus uses a finite-stiffness spring rather than an ideal rigid string.  A stiffer spring reduces the extension error, while too small a stiffness allows the bob to move outward significantly.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>7  Conclusion</Text>
        <Text style={S.body}>
          The experiment verified the main relationship for centripetal force.  After the system reached steady circular motion, the inward spring force measured from PhysX agreed with the theoretical force within the reported uncertainty and transient effects.  The result demonstrates that the force measured by the spring or force sensor is the net inward force required to keep the bob in circular motion.
        </Text>

        <Text style={S.h2}>7.1  Answers to Manual Questions</Text>
        <Text style={S.bodyBold}>1. What is the relationship between centripetal force and mass?</Text>
        <Text style={S.body}>
          When radius and tangential speed are held approximately constant, the centripetal force is directly proportional to mass.  This follows from Equation (1), where F_c changes linearly with m.
        </Text>
        <Text style={S.bodyBold}>2. What is the relationship between centripetal force and tangential speed?</Text>
        <Text style={S.body}>
          With mass and radius held constant, the force is proportional to the square of speed.  Therefore, a graph of force versus v squared should be approximately linear.
        </Text>
        <Text style={S.bodyBold}>3. What is the relationship between centripetal force and radius?</Text>
        <Text style={S.body}>
          The answer depends on which speed variable is controlled.  If tangential speed is held constant, F_c = m v squared / r decreases as radius increases.  If angular velocity is held constant, F_c = m omega squared r increases with radius.
        </Text>
        <Text style={S.bodyBold}>4. Is Equation (1) valid, and how can the radius result agree with it?</Text>
        <Text style={S.body}>
          Equation (1) is valid.  The apparent difference in the radius procedure arises because changing radius also changes tangential speed when angular velocity is controlled.  The correct interpretation requires identifying whether v or omega was held constant.
        </Text>
        <Text style={S.bodyBold}>5. How would friction between the mass and rotating arm affect the measured force?</Text>
        <Text style={S.body}>
          Friction would add a non-ideal force along the arm and dissipate energy.  It could reduce the speed and contaminate the force sensor reading, making the measured force differ from the ideal centripetal force.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>8  Appendix</Text>
        <Text style={S.body}>
          The ZIP package generated with this report contains the complete raw CSV file, the Python-generated PNG figures, the Markdown version of the report, and the backend-generated PDF copy.  The front-end PDF version uses the same data but renders the report in a formal PHY 1002 style.
        </Text>
        <Text style={S.bodyItalic}>
          Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / PhysX 5.  All tables and figures are generated from numerical data, not screenshots.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>
    </Document>
  );
};

export default Exp6ReportPDF;
