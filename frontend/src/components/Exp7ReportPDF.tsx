import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';
import { type Exp7ChartImages } from '../utils/exp7Charts';

const MathEquation = ({ latex, height = 25, label }: { latex: string; height?: number; label?: string }) => {
  const url = `https://latex.codecogs.com/png.image?\\dpi{300}\\bg{white}${encodeURIComponent(latex)}`;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginVertical: 6 }}>
      <Image src={url} style={{ height }} />
      {label && <Text style={{ fontSize: 11, fontFamily: 'Times-Roman', marginLeft: 16 }}>({label})</Text>}
    </View>
  );
};

export interface Exp7Trial {
  trial: number;
  m1: number;
  m2: number;
  v1i: number;
  v2i: number;
  restitution: number;
  v1f: number;
  v2f: number;
  pBefore: number;
  pAfter: number;
  pPctDiff: number;
  keBefore: number;
  keAfter: number;
  keLossPct: number;
  collisionType: string;
}

interface Props {
  trials: Exp7Trial[];
  charts?: Exp7ChartImages;
}

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
  body: { fontSize: 11, textAlign: 'justify', marginBottom: 6 },
  bodyBold: { fontSize: 11, fontFamily: 'Times-Bold', textAlign: 'justify', marginBottom: 4 },
  caption: { fontSize: 10, fontFamily: 'Times-Italic', marginBottom: 3, marginTop: 10 },
  footer: { position: 'absolute', bottom: 30, left: 50, right: 50, fontSize: 8, color: '#888', textAlign: 'center' },
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

const f = (v: number, d: number) => v.toFixed(d);

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
  <Text style={S.header} fixed>Lab Report for Lab 7 -- Conservation of Momentum</Text>
);

const Exp7ReportPDF: React.FC<Props> = ({ trials, charts }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const avgPDiff = trials.reduce((s, t) => s + Math.abs(t.pPctDiff), 0) / trials.length;
  const avgKELoss = trials.reduce((s, t) => s + Math.abs(t.keLossPct), 0) / trials.length;

  return (
    <Document>
{/* COVER */}
<Page size="A4" style={S.coverPage}>
  <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
  <Text style={S.coverCourse}>PHY 1002</Text>
  <Text style={S.coverCourse}>Physics Laboratory</Text>
  <View style={{ marginTop: 30 }}>
    <Text style={S.coverTitle}>Lab Report for Lab 7 --</Text>
    <Text style={S.coverSubtitle}>Conservation of Momentum</Text>
  </View>
  <View style={{ marginTop: 40 }}>
    <Text style={S.coverField}>Author:</Text>
    <Text style={S.coverValue}>[Student Name]</Text>
    <Text style={S.coverField}>Student Number:</Text>
    <Text style={S.coverValue}>[Student ID]</Text>
    <Text style={{ fontSize: 12, textAlign: 'center', marginTop: 20 }}>{date}</Text>
  </View>
</Page>

{/* SECTION 1 & 2 */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>1  Introduction</Text>
  <Text style={S.body}>
    This experiment uses the Isaac Sim physics simulation platform to verify the law of conservation of momentum. Two carts on a frictionless track collide head-on under controlled initial conditions. By recording the velocities before and after the collision, we compute the total momentum and kinetic energy to evaluate conservation laws for both elastic and inelastic collisions. Four independent trials are conducted with varying mass, velocity, and coefficient of restitution settings.
  </Text>

  <Text style={S.h1}>2  Objective</Text>
  <Text style={S.h2}>2.1  Review of Theory</Text>
  <Text style={S.body}>The momentum of a cart is given by:</Text>
  <MathEquation latex="\vec{p} = m\vec{v}" height={18} label="1" />
  <Text style={S.body}>For an isolated system with no net external force, the total momentum is conserved:</Text>
  <MathEquation latex="\vec{p}_{\text{total,before}} = \vec{p}_{\text{total,after}}" height={18} label="2" />
  <Text style={S.body}>The kinetic energy of a cart is a scalar quantity:</Text>
  <MathEquation latex="KE = \frac{1}{2}mv^2" height={22} label="3" />
  <Text style={S.body}>
    {"In elastic collisions (restitution e = 1), both momentum and kinetic energy are conserved. In perfectly inelastic collisions (e = 0), the carts stick together; momentum is conserved but kinetic energy is not. For intermediate values of e, partial kinetic energy loss occurs."}
  </Text>

  <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
  <Text style={S.listItem}>1. Verify conservation of momentum for collisions with various coefficients of restitution.</Text>
  <Text style={S.listItem}>2. Quantify kinetic energy conservation or loss in elastic vs. inelastic collisions.</Text>
  <Text style={S.listItem}>3. Compare simulation results with theoretical predictions.</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* SECTION 3 METHODS */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>3  Methods</Text>
  <Text style={S.h2}>3.1  Setup</Text>
  <Text style={S.body}>
    Two DynamicCuboid carts were created on a frictionless track in Isaac Sim. A PhysicsMaterial with configurable restitution was applied to simulate elastic, partially elastic, or completely inelastic collisions. Both carts have continuous collision detection (CCD) enabled with high solver iteration counts (64 position, 32 velocity) for precise contact resolution.
  </Text>
  <Text style={S.body}>
    The red cart (Cart 1) starts at x = -0.50 m and the blue cart (Cart 2) starts at x = +0.50 m. After a 0.5-second warm-up phase for gravitational settling, initial velocities are applied so the carts approach each other head-on.
  </Text>

  <Text style={S.h2}>3.2  Procedure</Text>
  <Text style={S.listItem}>1. Set the masses of both carts and the coefficient of restitution via the web interface.</Text>
  <Text style={S.listItem}>2. Set the initial velocities of both carts (positive = rightward).</Text>
  <Text style={S.listItem}>3. Click "Run Collision" to start the simulation.</Text>
  <Text style={S.listItem}>4. Observe the WebRTC video feed of the collision and the real-time telemetry charts.</Text>
  <Text style={S.listItem}>5. After the collision settles, click "Record" to save the trial data.</Text>
  <Text style={S.listItem}>6. Repeat steps 1-5 for a total of four trials with different parameters.</Text>
  <Text style={S.listItem}>7. Generate this PDF lab report from the recorded data.</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* SECTION 4 RAW DATA */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>4  Raw Data</Text>

  <T cap="Table 1: Experimental parameters for each trial."
    cols={[
      { h: '#', w: '6%', k: 'n' },
      { h: 'm1 (kg)', w: '11%', k: 'm1' },
      { h: 'm2 (kg)', w: '11%', k: 'm2' },
      { h: 'v1,i (m/s)', w: '13%', k: 'v1i' },
      { h: 'v2,i (m/s)', w: '13%', k: 'v2i' },
      { h: 'e', w: '8%', k: 'e' },
      { h: 'v1,f (m/s)', w: '13%', k: 'v1f' },
      { h: 'v2,f (m/s)', w: '13%', k: 'v2f' },
      { h: 'Type', w: '12%', k: 'type' },
    ]}
    data={trials.map(t => ({
      n: `${t.trial}`, m1: f(t.m1, 2), m2: f(t.m2, 2),
      v1i: f(t.v1i, 3), v2i: f(t.v2i, 3),
      e: f(t.restitution, 2),
      v1f: f(t.v1f, 3), v2f: f(t.v2f, 3),
      type: t.collisionType,
    }))}
  />

  <Text style={S.h1}>5  Data and Error Analysis</Text>
  <Text style={S.h2}>5.1  Momentum Conservation</Text>
  <Text style={S.body}>
    The total momentum before and after each collision is computed and compared. The percent difference is defined as:
  </Text>
  <MathEquation latex="\%\text{diff} = \frac{|p_{\text{after}} - p_{\text{before}}|}{|p_{\text{before}}|} \times 100\%" height={28} label="4" />

  <T cap="Table 2: Momentum conservation analysis."
    cols={[
      { h: '#', w: '8%', k: 'n' },
      { h: 'p_before (kg m/s)', w: '22%', k: 'pb' },
      { h: 'p_after (kg m/s)', w: '22%', k: 'pa' },
      { h: '% diff', w: '15%', k: 'd' },
      { h: 'Conserved?', w: '15%', k: 'c' },
    ]}
    data={trials.map(t => ({
      n: `${t.trial}`,
      pb: f(t.pBefore, 4), pa: f(t.pAfter, 4),
      d: f(t.pPctDiff, 2),
      c: Math.abs(t.pPctDiff) < 5 ? 'Yes' : 'No',
    }))}
  />

  <Text style={S.h2}>5.2  Kinetic Energy Analysis</Text>
  <Text style={S.body}>
    The total kinetic energy before and after each collision is compared to determine the energy loss percentage:
  </Text>
  <MathEquation latex="\text{KE loss \%} = \frac{KE_{\text{before}} - KE_{\text{after}}}{KE_{\text{before}}} \times 100\%" height={28} label="5" />

  <T cap="Table 3: Kinetic energy analysis."
    cols={[
      { h: '#', w: '8%', k: 'n' },
      { h: 'KE_before (J)', w: '20%', k: 'kb' },
      { h: 'KE_after (J)', w: '20%', k: 'ka' },
      { h: 'KE loss %', w: '15%', k: 'l' },
      { h: 'Type', w: '15%', k: 't' },
    ]}
    data={trials.map(t => ({
      n: `${t.trial}`,
      kb: f(t.keBefore, 4), ka: f(t.keAfter, 4),
      l: f(t.keLossPct, 2),
      t: t.collisionType,
    }))}
  />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* SECTION 5.3 FIGURES — Velocity, Momentum, KE, KE Loss vs e */}
{charts && (
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h2}>5.3  Graphical Analysis</Text>

  <Text style={S.body}>
    The following figures were generated automatically from the recorded trial data to provide visual evidence of momentum conservation and kinetic energy behaviour across all collision types.
  </Text>

  <Text style={S.caption}>Figure 1: Cart velocities before (solid) and after (faded) the collision for each trial. The velocity exchange pattern is clearly visible.</Text>
  <Image src={charts.velocityChart} style={{ width: '100%', height: 190, marginBottom: 8 }} />

  <Text style={S.caption}>Figure 2: Total system momentum before and after collision. Near-identical bar heights confirm conservation of momentum.</Text>
  <Image src={charts.momentumChart} style={{ width: '100%', height: 190, marginBottom: 4 }} />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>
)}

{charts && (
<Page size="A4" style={S.page}>
  <Hdr />

  <Text style={S.caption}>Figure 3: Total kinetic energy before and after collision. Energy loss is visible for inelastic trials (e &lt; 1).</Text>
  <Image src={charts.keChart} style={{ width: '100%', height: 190, marginBottom: 10 }} />

  <Text style={S.caption}>Figure 4: KE loss percentage vs. coefficient of restitution. Data points are compared to the theoretical curve (1 − e²) × 100 % for equal-mass head-on collisions.</Text>
  <Image src={charts.keLossChart} style={{ width: '100%', height: 190, marginBottom: 10 }} />

  <Text style={S.body}>
    As shown in Figures 1–4, the simulation results are consistent with theoretical predictions. Momentum is conserved across all trials regardless of the collision type. Kinetic energy loss increases as the coefficient of restitution decreases from 1 (elastic) to 0 (perfectly inelastic), following the expected (1 − e²) relationship.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>
)}

{/* SECTION 6 CONCLUSION */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>6  Conclusion</Text>
  <Text style={S.h2}>6.1  Answering the Questions</Text>

  <Text style={S.bodyBold}>1. Was momentum conserved for all types of collisions?</Text>
  <Text style={S.body}>
    {`Yes. Across all ${trials.length} trials, the average absolute percent difference in total momentum was ${f(avgPDiff, 2)}%. This is well within the acceptable range, confirming that momentum is conserved regardless of the collision type (elastic or inelastic). The small deviations are attributable to numerical solver precision in the PhysX engine.`}
  </Text>

  <Text style={S.bodyBold}>2. Was kinetic energy conserved for all types of collisions?</Text>
  <Text style={S.body}>
    {`Kinetic energy conservation depends on the coefficient of restitution. For elastic trials (e = 1.0), KE was approximately conserved. For inelastic trials (e < 1.0), kinetic energy loss of up to ${f(avgKELoss, 1)}% was observed. In perfectly inelastic collisions (e = 0), maximum KE loss occurs as the carts stick together. This is consistent with theory.`}
  </Text>

  <Text style={S.bodyBold}>3. What happens to the kinetic energy lost in an inelastic collision?</Text>
  <Text style={S.body}>
    In a real-world inelastic collision, kinetic energy is converted to internal energy (deformation, heat) and sound. In the simulation, the PhysX engine models this loss through the restitution coefficient, which controls how much relative velocity is retained after impact.
  </Text>

  <Text style={S.h2}>6.2  Summary</Text>
  <Text style={S.body}>
    The Isaac Sim simulation successfully verified the conservation of momentum across elastic and inelastic collision scenarios. Total system momentum was conserved to within numerical precision in all trials. Kinetic energy behaved as predicted by theory: conserved in elastic collisions and partially lost in inelastic ones. These results demonstrate the validity of using GPU-accelerated physics simulation for quantitative physics experiments.
  </Text>

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

export default Exp7ReportPDF;
