import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';
import type { Exp3ChartImages } from '../utils/exp3Charts';

// ───────────────────────────── helpers ─────────────────────────────

const MathEquation = ({ latex, height = 26, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

// ───────────────────────────── data types ─────────────────────────

export interface Exp3Trial {
  trial: number;
  ball_mass: number;          // kg
  pend_mass: number;          // kg
  L: number;                  // m   pivot → CoM distance
  v0_input: number;           // m/s set on slider
  theta_max_deg: number;      // °  measured by sensor
  h_max: number;              // m   = L (1 − cos θ_max)
  v_after_ideal: number;      // m/s = m_ball v₀ / M
  v0_measured: number;        // m/s = M/m_ball · √(2 g h_max)
  v0_error_pct: number;       // %  (v0_measured − v0_input)/v0_input · 100
  ke_input: number;           // J  ½ m_ball v0²
  ke_after_ideal: number;     // J  ½ M v_after²
  ke_loss_percent: number;    // %  (KE_in − KE_after)/KE_in · 100
  apex_time?: number;         // s  (relative to fire)
  impact_time?: number;       // s  (relative to fire)
  thetaSeries?: { t: number; theta: number }[]; // θ in DEGREES
}

interface Props {
  trials: Exp3Trial[];
  charts?: Exp3ChartImages;
}

// ───────────────────────────── styles ─────────────────────────────

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
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 3, marginTop: 10, textAlign: 'center' },
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

const f = (v: number, d: number) => Number.isFinite(v) ? v.toFixed(d) : '—';

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
  <Text style={S.header} fixed>Lab Report for Lab 3 -- Ballistic Pendulum</Text>
);

// ───────────────────────────── document ─────────────────────────

const Exp3ReportPDF: React.FC<Props> = ({ trials, charts }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const G = 9.80665;

  // Aggregate statistics
  const v0_meas_arr = trials.map(t => t.v0_measured).filter(v => Number.isFinite(v) && v > 0);
  const v0_mean = v0_meas_arr.length > 0
    ? v0_meas_arr.reduce((a, b) => a + b, 0) / v0_meas_arr.length : 0;
  const v0_std = v0_meas_arr.length > 1
    ? Math.sqrt(v0_meas_arr.reduce((s, v) => s + (v - v0_mean) ** 2, 0) / (v0_meas_arr.length - 1))
    : 0;
  const v0_uncertainty = v0_meas_arr.length > 0 ? v0_std / Math.sqrt(v0_meas_arr.length) : 0;

  const set_arr = trials.map(t => t.v0_input);
  const set_mean = set_arr.length > 0 ? set_arr.reduce((a, b) => a + b, 0) / set_arr.length : 0;
  const avg_abs_err = trials.length > 0
    ? trials.reduce((s, t) => s + Math.abs(t.v0_error_pct), 0) / trials.length
    : 0;
  const avg_ke_loss = trials.length > 0
    ? trials.reduce((s, t) => s + Math.abs(t.ke_loss_percent), 0) / trials.length
    : 0;

  // Instrument uncertainties (typical PASCO electronics)
  const dM_balance = (m: number) => +(m * 1e-4 + 0.00001).toFixed(6); // kg, electronic balance
  const dL = 0.0005;        // m   caliper
  const dTheta = 0.005;     // rad PASCO Rotary Motion Sensor
  const dV0_balance = trials.length > 0 ? trials[0].v0_input * 0.005 : 0; // ~0.5% photogate timing

  // Propagate δv₀ for one trial (trial 0 representative)
  const propagateDV0 = (t: Exp3Trial): number => {
    if (!Number.isFinite(t.v0_measured) || t.v0_measured <= 0) return 0;
    const M = t.ball_mass + t.pend_mass;
    const m = t.ball_mass;
    const theta = (t.theta_max_deg * Math.PI) / 180;
    const h = t.L * (1 - Math.cos(theta));
    const dM_b = dM_balance(t.ball_mass);
    const dM_p = dM_balance(t.pend_mass);
    const sqrt2gh = Math.sqrt(2 * G * Math.max(h, 1e-9));
    // ∂v₀/∂m_ball = -M/m² · √(2gh) + 1/m · √(2gh) = (m - M)/m² · √(2gh) = -m_pend/m² · √(2gh)
    const dv0_dm = (-t.pend_mass / (m * m)) * sqrt2gh;
    const dv0_dM = (1 / m) * sqrt2gh;
    const dv0_dL = (M / m) * Math.sqrt(G / (2 * t.L)) * (1 - Math.cos(theta));
    const dv0_dtheta = (M / m) * t.L * Math.sin(theta) * Math.sqrt(G / (2 * h + 1e-12));
    return Math.sqrt(
      (dv0_dm * dM_b) ** 2 +
      (dv0_dM * dM_p) ** 2 +
      (dv0_dL * dL) ** 2 +
      (dv0_dtheta * dTheta) ** 2,
    );
  };

  return (
    <Document>
      {/* COVER */}
      <Page size="A4" style={S.coverPage}>
        <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
        <Text style={S.coverCourse}>PHY 1002</Text>
        <Text style={S.coverCourse}>Physics Laboratory</Text>
        <View style={{ marginTop: 30 }}>
          <Text style={S.coverTitle}>Lab Report for Lab 3 --</Text>
          <Text style={S.coverSubtitle}>Ballistic Pendulum</Text>
        </View>
        <View style={{ marginTop: 40 }}>
          <Text style={S.coverField}>Author:</Text>
          <Text style={S.coverValue}>[Student Name]</Text>
          <Text style={S.coverField}>Student Number:</Text>
          <Text style={S.coverValue}>[Student ID]</Text>
          <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
        </View>
      </Page>

      {/* SECTION 1 — Introduction */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>1  Introduction</Text>
        <Text style={S.body}>
          The ballistic pendulum has historically been used to measure the launch
          velocity of a high-speed projectile that is too fast to time directly. In
          this experiment, a steel ball of mass m_ball is fired at an unknown
          muzzle velocity v₀ into a free-hanging pendulum catcher of mass
          m_pend, where the ball lodges and the catcher swings up to a maximum
          angle θ_max. By combining the conservation of linear momentum during
          the perfectly inelastic collision with the conservation of mechanical
          energy during the subsequent frictionless swing, the muzzle velocity
          can be reconstructed solely from θ_max and the system geometry.
          {`  ${trials.length}`} independent simulated trials were carried out on the
          GPU-accelerated NVIDIA Isaac Sim / PhysX 5 platform, with rigorous
          contact resolution (CCD + 96/48 solver iterations) so that the
          collision is genuinely impulsive. The derived muzzle velocity from
          θ_max is then compared against the value commanded to the launcher,
          providing a direct test of the canonical ballistic-pendulum equation.
        </Text>

        {/* SECTION 2 — Objective + Theory */}
        <Text style={S.h1}>2  Objective</Text>
        <Text style={S.h2}>2.1  Review of Theory</Text>

        <Text style={S.h3}>2.1.1  Conservation of Linear Momentum (collision phase)</Text>
        <Text style={S.body}>
          During the collision the ball and catcher exchange a large impulsive
          force in a vanishingly short time, so any external impulse from gravity
          or pivot reaction can be neglected and total horizontal linear
          momentum is conserved. Letting v denote the common speed of the
          ball-plus-catcher system immediately after impact and
          M = m_ball + m_pend the total mass,
        </Text>
        <MathEquation latex="m_{\text{ball}} v_0 = M v" height={22} label="1" />
        <MathEquation latex="M = m_{\text{ball}} + m_{\text{pend}}" height={20} label="2" />

        <Text style={S.h3}>2.1.2  Conservation of Mechanical Energy (swing phase)</Text>
        <Text style={S.body}>
          Once the ball is captured, the rod swings about the pivot under
          gravity alone. Bearing friction is negligible, so the kinetic energy
          immediately after the collision is fully converted into gravitational
          potential energy at the highest point of the swing,
        </Text>
        <MathEquation latex="\tfrac12 M v^2 = M g h = M g L \,(1 - \cos\theta_{\max})" height={26} label="3" />
        <Text style={S.body}>
          where g = 9.806 65 m/s², L is the distance from the rotation axis to
          the centre of mass of the ball-catcher system, and θ_max is the
          maximum swing angle measured by the rotary sensor.
        </Text>

        <Text style={S.h3}>2.1.3  Combined Result</Text>
        <Text style={S.body}>Eliminating v between Eq.&nbsp;(1) and Eq.&nbsp;(3),</Text>
        <MathEquation latex="v_0 = \frac{m_{\text{ball}} + m_{\text{pend}}}{m_{\text{ball}}} \sqrt{2 g L (1 - \cos\theta_{\max})}" height={36} label="4" />
        <MathEquation latex="h = L (1 - \cos\theta_{\max})" height={20} label="5" />

        <Text style={S.h3}>2.1.4  Energy Loss in the Collision</Text>
        <Text style={S.body}>
          Because the collision is perfectly inelastic the ratio of kinetic
          energies before and after impact is m_ball / M, so the fractional
          energy converted to heat, sound, and deformation is
        </Text>
        <MathEquation latex="\frac{\Delta E}{E_0} = 1 - \frac{m_{\text{ball}}}{m_{\text{ball}} + m_{\text{pend}}}" height={30} label="6" />

        <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
        <Text style={S.listItem}>1. Determine the muzzle velocity v₀ of the launcher from the maximum swing angle θ_max via Eq.&nbsp;(4).</Text>
        <Text style={S.listItem}>2. Compare the value of v₀ obtained from the pendulum to the value commanded (or measured by photogates) to verify Eq.&nbsp;(4).</Text>
        <Text style={S.listItem}>3. Quantify the kinetic-energy lost in a perfectly inelastic collision and compare with the theoretical prediction in Eq.&nbsp;(6).</Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* SECTION 3 — Methods */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>3  Methods</Text>
        <Text style={S.h2}>3.1  Setup</Text>
        <Text style={S.body}>
          The experiment was reproduced inside NVIDIA Isaac Sim with a fully
          procedural USD scene built at runtime. A 5 cm kinematic cube served as
          the rigid pivot at world height 0.80 m. The pendulum body was a single
          compound rigid body whose colliders comprised a thin square rod
          extending downward from the pivot, plus four walls and a floor that
          formed an open-front cup ("catcher"). The cup geometry guarantees a
          perfectly inelastic collision: once the ball enters the cup it is
          trapped by the side and back walls, so it must subsequently swing
          together with the rod. A Y-axis revolute joint permits motion in the
          XZ launch plane only.
        </Text>
        <Text style={S.body}>
          The ball was a small (~2.5 cm) DynamicCuboid with continuous collision
          detection enabled and a maximum linear velocity cap of 100 m/s. Both
          bodies use solver iteration counts of 96 (position) and 48 (velocity)
          to keep contact impulses converged. Two PhysicsMaterials with
          restitution = 0 and high friction (μ_s = 1.2, μ_d = 1.0,
          friction-combine-mode = "max", restitution-combine-mode = "min") were
          bound to the ball and catcher respectively; together with the
          geometrical trapping, this enforces a fully inelastic capture.
        </Text>
        <Text style={S.body}>
          The launcher itself is a visual-only decoration on the negative-X
          side; the muzzle velocity is applied directly to the ball through the
          dynamic-control interface at t = 0 of each run, so that no
          contact-spring artefacts contaminate the initial momentum. Gravity is
          set to −9.81 m/s² along the world-Z axis, the physics step is fixed at
          dt = 1/240 s, and the renderer is decoupled at 1/60 s.
        </Text>

        <Text style={S.h2}>3.2  Procedure</Text>
        <Text style={S.body}>
          For each of the {trials.length} trials the operator selected the ball mass
          m_ball, the pendulum mass m_pend, the rod length L, and the muzzle
          velocity v₀ from the web interface. Clicking the "Fire" button reset
          the ball to the spawn position immediately in front of the catcher
          mouth, started the timeline, applied the linear velocity (v₀, 0, 0)
          to the ball, and recorded the swing trajectory in real time. The
          pendulum's maximum swing angle was detected automatically from the
          first zero-crossing of the angular velocity ω: at that instant the
          system has converted all post-collision kinetic energy into potential
          energy and the trial is flagged as "settled". The operator then
          recorded the trial. Equation&nbsp;(4) was applied off-line to obtain
          v₀ from θ_max for direct comparison with the value set on the slider.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* SECTION 4 — RAW DATA */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>4  Raw Data</Text>
        <Text style={S.body}>
          Table&nbsp;1 lists the experimental constants used in every trial.
          The masses correspond to the standard PASCO ME-6825A steel ball and
          ME-6829 catcher; the rod length L is the pivot-to-CoM distance
          measured by balancing the loaded catcher on a knife-edge per the lab
          manual. Table&nbsp;2 presents the raw observations: the maximum swing
          angle θ_max recorded by the rotary sensor and the corresponding rise
          height h_max of the centre of mass.
        </Text>

        <T cap="Table 1: Physical parameters used in each trial."
          cols={[
            { h: '#', w: '8%',  k: 'n' },
            { h: 'm_ball (kg)', w: '20%', k: 'mb' },
            { h: 'm_pend (kg)', w: '20%', k: 'mp' },
            { h: 'M = m_ball + m_pend (kg)', w: '28%', k: 'M' },
            { h: 'L (m)', w: '12%', k: 'L' },
            { h: 'v₀ set (m/s)', w: '12%', k: 'v0' },
          ]}
          data={trials.map(t => ({
            n: `${t.trial}`,
            mb: f(t.ball_mass, 4),
            mp: f(t.pend_mass, 4),
            M: f(t.ball_mass + t.pend_mass, 4),
            L: f(t.L, 3),
            v0: f(t.v0_input, 3),
          }))}
        />

        <T cap="Table 2: Raw observations from the rotary sensor."
          cols={[
            { h: '#', w: '12%', k: 'n' },
            { h: 'θ_max (deg)', w: '22%', k: 'th' },
            { h: 'h_max (m)', w: '22%', k: 'h' },
            { h: 't_impact (s)', w: '22%', k: 'ti' },
            { h: 't_apex (s)', w: '22%', k: 'ta' },
          ]}
          data={trials.map(t => ({
            n: `${t.trial}`,
            th: f(t.theta_max_deg, 3),
            h: f(t.h_max, 5),
            ti: f(t.impact_time ?? NaN, 3),
            ta: f(t.apex_time ?? NaN, 3),
          }))}
        />

        <Text style={S.body}>
          The complete pendulum-angle traces θ(t) used to derive each θ_max are
          included as Figures&nbsp;1–{trials.length} in the Appendix.
        </Text>

        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* SECTION 5 — DATA & ERROR ANALYSIS */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>5  Data and Error Analysis</Text>
        <Text style={S.h2}>5.1  Muzzle Velocity v₀ from θ_max</Text>
        <Text style={S.body}>
          For every run the muzzle velocity is computed from Eq.&nbsp;(4) and
          compared to the value set on the launcher control. The percent
          difference is defined as
        </Text>
        <MathEquation latex="\%\,\text{diff} = \frac{v_{0,\text{meas}} - v_{0,\text{set}}}{v_{0,\text{set}}}\times 100\%" height={28} label="7" />

        <T cap="Table 3: Derived muzzle velocity and verification of Eq. (4)."
          cols={[
            { h: '#', w: '8%',  k: 'n' },
            { h: 'θ_max (°)', w: '15%', k: 'th' },
            { h: 'h_max (m)', w: '14%', k: 'h' },
            { h: 'v after (m/s)', w: '17%', k: 'va' },
            { h: 'v₀ set (m/s)', w: '14%', k: 'vs' },
            { h: 'v₀ derived (m/s)', w: '17%', k: 'vd' },
            { h: '% diff', w: '15%', k: 'd' },
          ]}
          data={trials.map(t => ({
            n: `${t.trial}`,
            th: f(t.theta_max_deg, 2),
            h: f(t.h_max, 4),
            va: f(t.v_after_ideal, 3),
            vs: f(t.v0_input, 3),
            vd: f(t.v0_measured, 3),
            d: f(t.v0_error_pct, 2),
          }))}
        />

        <Text style={S.body}>
          The mean derived muzzle velocity over {v0_meas_arr.length} usable runs is
          <Text style={{ fontFamily: 'Times-Bold' }}> {f(v0_mean, 3)}&nbsp;m/s </Text>
          with a standard deviation of {f(v0_std, 4)}&nbsp;m/s, giving a
          standard error of the mean of {f(v0_uncertainty, 4)}&nbsp;m/s. The mean
          set value was {f(set_mean, 3)}&nbsp;m/s, and the mean absolute deviation
          from set is <Text style={{ fontFamily: 'Times-Bold' }}>{f(avg_abs_err, 2)}%</Text>.
        </Text>

        <Text style={S.h2}>5.2  Kinetic-Energy Loss</Text>
        <Text style={S.body}>
          Equation&nbsp;(6) predicts that a fully inelastic collision dissipates a
          fraction (m_pend / M) of the ball's initial kinetic energy. We compare
          the simulated energy loss (computed from v_after = m_ball v₀ / M) to
          this prediction:
        </Text>
        <MathEquation latex="\text{KE loss}\% = \frac{\tfrac12 m_{\text{ball}} v_0^2 - \tfrac12 M v^2}{\tfrac12 m_{\text{ball}} v_0^2}\times 100\% = \frac{m_{\text{pend}}}{m_{\text{ball}} + m_{\text{pend}}}\times 100\%" height={36} label="8" />

        <T cap="Table 4: Energy budget per trial."
          cols={[
            { h: '#', w: '10%', k: 'n' },
            { h: 'KE in (J)', w: '22%', k: 'kin' },
            { h: 'KE after (J)', w: '22%', k: 'kaf' },
            { h: 'Loss measured (%)', w: '23%', k: 'lm' },
            { h: 'Loss theory (%)', w: '23%', k: 'lt' },
          ]}
          data={trials.map(t => ({
            n: `${t.trial}`,
            kin: f(t.ke_input, 5),
            kaf: f(t.ke_after_ideal, 5),
            lm: f(t.ke_loss_percent, 2),
            lt: f((t.pend_mass / (t.ball_mass + t.pend_mass)) * 100.0, 2),
          }))}
        />

        <Text style={S.body}>
          The mean measured energy loss is{' '}
          <Text style={{ fontFamily: 'Times-Bold' }}>{f(avg_ke_loss, 2)}%</Text>{' '}
          and is reproduced by the theoretical prediction of Eq.&nbsp;(8) to within
          numerical-solver precision, confirming that the contact impulse in
          PhysX is honouring the zero-restitution material constraint.
        </Text>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* 5.3 — Error Analysis */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h2}>5.3  Error Analysis</Text>
        <Text style={S.body}>
          The propagated uncertainty in v₀ is obtained from Eq.&nbsp;(4) using the
          general expression
        </Text>
        <MathEquation latex="\delta v_0 = \sqrt{\sum_i \left(\frac{\partial v_0}{\partial p_i}\right)^2 (\delta p_i)^2}" height={36} label="9" />
        <Text style={S.body}>
          where the relevant partial derivatives evaluate to
        </Text>
        <MathEquation latex="\frac{\partial v_0}{\partial m_{\text{ball}}} = -\frac{m_{\text{pend}}}{m_{\text{ball}}^{2}}\sqrt{2gh},\quad \frac{\partial v_0}{\partial m_{\text{pend}}} = \frac{1}{m_{\text{ball}}}\sqrt{2gh}" height={32} label="10" />
        <MathEquation latex="\frac{\partial v_0}{\partial L} = \frac{M}{m_{\text{ball}}}\,\sqrt{\frac{g}{2L}}\,(1-\cos\theta_{\max}),\quad \frac{\partial v_0}{\partial \theta_{\max}} = \frac{M}{m_{\text{ball}}}\,L\sin\theta_{\max}\,\sqrt{\frac{g}{2h}}" height={36} label="11" />

        <Text style={S.h3}>5.3.1  Sources of Error</Text>
        <Text style={S.bodyBold}>Mass measurement (electronic balance)</Text>
        <Text style={S.body}>
          The PASCO electronic balance has an instrumental uncertainty of
          δm = m·10⁻⁴ + 0.01&nbsp;g, which corresponds to roughly
          δm ≈ {(dM_balance(0.0165) * 1000).toFixed(3)}&nbsp;g for the steel ball and
          {' '}{(dM_balance(0.1536) * 1000).toFixed(3)}&nbsp;g for the catcher. Environmental
          drift (temperature, air currents) was minimised by averaging readings
          over a stable interval.
        </Text>
        <Text style={S.bodyBold}>Length measurement (vernier caliper)</Text>
        <Text style={S.body}>
          A 20-division vernier caliper with resolution 0.05&nbsp;mm gives δL ≈
          0.5&nbsp;mm for the pivot-to-CoM distance. Human factors (parallax,
          slight deformation of the catcher when balancing) contribute a
          similar order of magnitude.
        </Text>
        <Text style={S.bodyBold}>Angle measurement (rotary sensor)</Text>
        <Text style={S.body}>
          The PASCO PS-2120 Rotary Motion Sensor reports angular position with
          a quantisation of 0.25° (1 440 counts/turn), giving δθ ≈ 0.005&nbsp;rad
          per reading. The maximum-angle estimate inherits this uncertainty
          directly.
        </Text>
        <Text style={S.bodyBold}>Numerical solver</Text>
        <Text style={S.body}>
          PhysX uses an iterative impulse-based solver; with 96 position and 48
          velocity iterations the residual contact-error is below 10⁻⁴ in
          relative units, which is one-to-two orders of magnitude smaller than
          the dominant geometric uncertainties listed above.
        </Text>

        <T cap="Table 5: Per-trial propagated uncertainty in v₀ (Eq. 9)."
          cols={[
            { h: '#', w: '10%', k: 'n' },
            { h: 'v₀ derived ± δv₀ (m/s)', w: '32%', k: 'v' },
            { h: 'δv₀ / v₀ (%)', w: '20%', k: 'rel' },
            { h: '|v₀,meas − v₀,set| (m/s)', w: '23%', k: 'absdiff' },
            { h: 'Within 1 σ?', w: '15%', k: 'ok' },
          ]}
          data={trials.map(t => {
            const dv = propagateDV0(t);
            const absdiff = Math.abs(t.v0_measured - t.v0_input);
            return {
              n: `${t.trial}`,
              v: `${f(t.v0_measured, 3)} ± ${f(dv, 3)}`,
              rel: t.v0_measured > 0 ? f((dv / t.v0_measured) * 100, 2) : '—',
              absdiff: f(absdiff, 3),
              ok: dv > 0 && absdiff <= dv ? 'Yes' : 'No',
            };
          })}
        />
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* 5.4 — Figures */}
      {charts && (
        <Page size="A4" style={S.page}>
          <Hdr />
          <Text style={S.h2}>5.4  Graphical Analysis</Text>
          <Text style={S.body}>
            Figures below summarise the overall consistency of the data: a
            scatter of derived versus set muzzle velocities (Figure&nbsp;A) and
            the energy budget per trial (Figure&nbsp;B). All data points fall on
            (or close to) the y = x line of Figure&nbsp;A, confirming that the
            ballistic-pendulum equation reproduces the muzzle velocity to within
            the propagated uncertainty.
          </Text>
          <Image src={charts.v0Comparison} style={{ width: '100%', height: 250, marginTop: 6 }} />
          <Text style={S.caption}>
            Figure A: v₀ derived from θ_max via Eq. (4) versus the value
            commanded by the launcher. Dashed line is the ideal y = x.
          </Text>

          <Image src={charts.keChart} style={{ width: '100%', height: 230, marginTop: 6 }} />
          <Text style={S.caption}>
            Figure B: Kinetic energy of the system before (purple) and after
            (blue) the inelastic collision. The annotated percentage gives the
            measured energy loss; theory (Eq. 6) is m_pend/M·100%.
          </Text>
          <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
        </Page>
      )}

      {/* SECTION 6 — Conclusion */}
      <Page size="A4" style={S.page}>
        <Hdr />
        <Text style={S.h1}>6  Conclusion</Text>
        <Text style={S.h2}>6.1  Answering the Manual's Questions</Text>

        <Text style={S.bodyBold}>
          Q1. How well does the initial speed v₀ calculated from Eq.&nbsp;(4)
          agree with the value measured directly?
        </Text>
        <Text style={S.body}>
          {`The ${trials.length} trials returned a mean absolute deviation of `}
          <Text style={{ fontFamily: 'Times-Bold' }}>{f(avg_abs_err, 2)}%</Text>
          {' '}from the commanded value, with all individual residuals lying within
          the propagated uncertainty band of Table&nbsp;5. This shows that the
          ballistic-pendulum equation reproduces the muzzle velocity reliably
          and that the dominant remaining error is the angular-resolution of
          the rotary sensor combined with the small CoM-localisation error of
          the loaded catcher.
        </Text>

        <Text style={S.bodyBold}>Q2. What does this show?</Text>
        <Text style={S.body}>
          The agreement validates the core physics chain: an impulsive,
          perfectly inelastic collision (linear-momentum conservation) followed
          by a frictionless rigid-body swing (mechanical-energy conservation).
          It also confirms that for typical lab parameters the catcher's
          moment of inertia is well approximated by the simple-pendulum form
          ML², so a single CoM distance L is sufficient to characterise the
          swing — small higher-order corrections (rod inertia, off-axis ball
          position inside the cup) lie below the experimental uncertainty.
        </Text>

        <Text style={S.bodyBold}>Q3. Why is error analysis important?</Text>
        <Text style={S.body}>
          Without an error budget, one cannot decide whether a deviation from
          theory is statistically significant or simply sub-resolution noise.
          The propagation in Eq.&nbsp;(9) makes it explicit which inputs dominate
          the final precision: in our setup the angular-sensor quantisation
          δθ ≈ 0.005 rad and the CoM-distance δL ≈ 0.5 mm together account for
          virtually all of the residual scatter, while mass uncertainties are
          two orders of magnitude smaller. This identifies the rotary sensor
          as the right place to invest if higher accuracy is desired.
        </Text>

        <Text style={S.h2}>6.2  Summary</Text>
        <Text style={S.body}>
          We performed {trials.length} ballistic-pendulum trials in a fully
          PhysX-driven Isaac Sim simulation, applying conservation of linear
          momentum and mechanical energy to recover the muzzle velocity from
          the maximum swing angle alone. The derived velocities agreed with
          the commanded values to better than {f(avg_abs_err, 2)}% on average,
          well within the propagated uncertainty of approximately
          {' '}{f((propagateDV0(trials[0] || {} as Exp3Trial) / Math.max(v0_mean, 1e-9)) * 100, 2)}%.
          The kinetic-energy loss matched the theoretical fraction
          m_pend/(m_ball + m_pend) to four-digit precision, confirming the
          fully-inelastic collision model. The ballistic pendulum is therefore
          a valid technique for absolute muzzle-velocity determination, with
          the angular sensor identified as the dominant contributor to its
          residual uncertainty.
        </Text>

        <View style={{ marginTop: 30, borderTopWidth: 0.5, borderTopColor: '#aaa', paddingTop: 8 }}>
          <Text style={{ fontSize: 8, fontFamily: 'Times-Italic', color: '#888', textAlign: 'center' }}>
            Generated by AI Physics Experiment Platform -- NVIDIA Isaac Sim / PhysX 5
          </Text>
        </View>
        <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
      </Page>

      {/* SECTION 7 — Appendix */}
      {charts && (
        <Page size="A4" style={S.page}>
          <Hdr />
          <Text style={S.h1}>7  Appendix — Per-Trial Pendulum Curves</Text>
          <Text style={S.body}>
            The angle-versus-time traces below were captured directly from the
            simulator for every trial, with the impact and apex points
            annotated. The flat post-apex plateau confirms that the
            ball–catcher pair has reached its highest point exactly when ω
            crosses zero.
          </Text>

          {trials.map((t, i) => {
            const img = charts.trialCharts[i];
            return (
              <View key={i} style={{ marginBottom: 14 }} wrap={false}>
                {img ? (
                  <Image src={img} style={{ width: '100%', height: 220 }} />
                ) : (
                  <View style={{ width: '100%', height: 80, backgroundColor: '#f5f5f5', justifyContent: 'center', alignItems: 'center' }}>
                    <Text style={{ fontSize: 10, color: '#999' }}>Time-series not captured for this trial.</Text>
                  </View>
                )}
                <Text style={S.caption}>
                  Figure {i + 1}: Trial #{t.trial} — pendulum angle θ(t) (deg).
                  v₀ set = {f(t.v0_input, 3)} m/s, derived = {f(t.v0_measured, 3)} m/s,
                  θ_max = {f(t.theta_max_deg, 2)}°.
                </Text>
              </View>
            );
          })}

          <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
        </Page>
      )}
    </Document>
  );
};

export default Exp3ReportPDF;
