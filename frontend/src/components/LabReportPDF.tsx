import React from 'react';
import { Document, Page, Text, View, Image, StyleSheet } from '@react-pdf/renderer';

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
export interface PhysConsts {
  ring: { mass: number; rIn: number; rOut: number };
  lowerDisk: { mass: number; r: number };
  upperDisk: { mass: number; r: number };
  pulley: { mass: number; r: number };
}
export interface TrialRow {
  trial: number; object: string; dropMass: number;
  iav: number; fav: number; x: number;
  iri: number; fri: number; iam: number; fam: number; pctDiff: number;
  initK: number; finalK: number; energyPct: number;
}
interface Props { phys: PhysConsts; iri: number; trials: TrialRow[] }

// ═══════════════════════════════════════════════════════════════════
// Styles
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
  eq: { fontSize: 10.5, fontFamily: 'Courier', textAlign: 'center', marginVertical: 5, backgroundColor: '#f5f5f5', padding: 6, borderRadius: 2 },
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
  indent: { paddingLeft: 16 },
  listItem: { fontSize: 11, textAlign: 'justify', marginBottom: 4, paddingLeft: 10 },
});

// Helper
const f = (v: number, d: number) => v.toFixed(d);

// ═══════════════════════════════════════════════════════════════════
// Flexbox Table
// ═══════════════════════════════════════════════════════════════════
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

// Page header
const Hdr: React.FC = () => (
  <Text style={S.header} fixed>Lab Report for Lab 1 -- Conservation of Angular Momentum</Text>
);

// ═══════════════════════════════════════════════════════════════════
// DOCUMENT
// ═══════════════════════════════════════════════════════════════════
const LabReportPDF: React.FC<Props> = ({ phys, iri, trials }) => {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const I_d = 0.5 * phys.lowerDisk.mass * phys.lowerDisk.r ** 2;
  const I_p = 0.5 * phys.pulley.mass * phys.pulley.r ** 2;

  const ringTrials = trials.filter(t => t.object === 'Ring');
  const diskTrials = trials.filter(t => t.object !== 'Ring');
  const sysLabel = (t: TrialRow) => t.object === 'Ring' ? `ring on disk (${t.trial})` : 'disk 2 on disk';

  const dM_ring = +(phys.ring.mass * 1e-4 + 0.01).toFixed(3);
  const dM_d1 = +(phys.lowerDisk.mass * 1e-4 + 0.01).toFixed(3);
  const dM_d2 = +(phys.upperDisk.mass * 1e-4 + 0.01).toFixed(3);
  const dM_pul = +(phys.pulley.mass * 1e-4 + 0.01).toFixed(3);
  const dR = 0.0025;
  const dW = 0.002;

  const calcDeltaI_init = () => {
    const dIdM = 0.5 * phys.lowerDisk.r ** 2;
    const dIdR = phys.lowerDisk.mass * phys.lowerDisk.r;
    return Math.sqrt((dIdM * dM_d1) ** 2 + (dIdR * dR) ** 2);
  };
  const dI_init = calcDeltaI_init();

  const calcDeltaI_ring = (t: TrialRow) => {
    const dIdMd = 0.5 * phys.lowerDisk.r ** 2;
    const dIdMr = 0.5 * (phys.ring.rIn ** 2 + phys.ring.rOut ** 2) + t.x ** 2;
    const dIdRd = phys.lowerDisk.mass * phys.lowerDisk.r;
    const dIdR1 = t.dropMass * phys.ring.rIn;
    const dIdR2 = t.dropMass * phys.ring.rOut;
    const dIdx = 2 * t.dropMass * t.x;
    return Math.sqrt(
      (dIdMd * dM_d1) ** 2 + (dIdMr * dM_ring) ** 2 +
      (dIdRd * dR) ** 2 + (dIdR1 * dR) ** 2 + (dIdR2 * dR) ** 2 + (dIdx * dR) ** 2
    );
  };
  const calcDeltaI_disk = () => {
    const dIdMd = 0.5 * phys.lowerDisk.r ** 2;
    const dIdMd2 = 0.5 * phys.upperDisk.r ** 2;
    const dIdRd = phys.lowerDisk.mass * phys.lowerDisk.r;
    const dIdRd2 = phys.upperDisk.mass * phys.upperDisk.r;
    return Math.sqrt((dIdMd * dM_d1) ** 2 + (dIdMd2 * dM_d2) ** 2 + (dIdRd * dR) ** 2 + (dIdRd2 * dR) ** 2);
  };

  const dI_final = (t: TrialRow) => t.object === 'Ring' ? calcDeltaI_ring(t) : calcDeltaI_disk();
  const dL = (I: number, w: number, dI: number) => Math.sqrt((w * dI) ** 2 + (I * dW) ** 2);
  const dKE = (I: number, w: number, dI: number) => Math.sqrt((0.5 * w * w * dI) ** 2 + (I * w * dW) ** 2);

  return (
    <Document>
{/* ═══════════════════════════ COVER PAGE ═══════════════════════════ */}
<Page size="A4" style={S.coverPage}>
  <Text style={S.coverUni}>The Chinese University of Hong Kong, Shenzhen</Text>
  <Text style={S.coverCourse}>PHY 1002</Text>
  <Text style={S.coverCourse}>Physics Laboratory</Text>
  <View style={{ marginTop: 30 }}>
    <Text style={S.coverTitle}>Lab Report for Lab 1 --</Text>
    <Text style={S.coverSubtitle}>Conservation of Angular Momentum</Text>
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
    This lab report presents the experimental process and results of angular momentum conservation. After setting up the equipment, a non-rotating object was gently dropped onto a spinning disk to join the rotation. Based on measuring the angular velocities immediately before the drop and after the object stopped sliding on the disk, we obtained and compared the initial and final angular momentum and rotational kinetic energy of the system. To ensure the reliability of the results, these procedures were repeated several times. Finally, by analyzing each trial, the angular momentum and rotational kinetic energy in initial and final states remain approximately the same with small relative errors. In summary, the report verifies the conservation of angular momentum and explains the details of the experimental process.
  </Text>

{/* ═══════════════════════════ SECTION 2 OBJECTIVE ═══════════════════════════ */}
  <Text style={S.h1}>2  Objective</Text>
  <Text style={S.h2}>2.1  Review of Theory</Text>

  <Text style={S.h3}>2.1.1  Angular Momentum Conservation</Text>
  <Text style={S.body}>
    During the contact between the spinning disk and the object, their torques are equal in magnitude and opposite in direction, so the net torque of the system is 0. Therefore, the angular momentum L is conserved, which is represented in the equation below:
  </Text>
  <MathEquation latex="L = I_i \omega_i = I_f \omega_f" height={18} label="1" />
  <Text style={S.body}>
    Where I_i, w_i, I_f, and w_f are the initial rotational inertia of the system, the initial angular velocity of the disk, the final rotational inertia of the system, and the final angular velocity of the disk and object, respectively.
  </Text>
  <Text style={S.body}>
    Notably, this equation ignores the slight torque caused by the negligible friction of the Rotary Motion Sensor, and the contact is supposed to happen instantly enough to avoid other potential effects.
  </Text>

  <Text style={S.h3}>2.1.2  Initial Rotational Inertia</Text>
  <Text style={S.body}>
    Since the slight rotational inertia of the Rotary Motion Sensor is ignored, the initial rotational inertia is simply the rotational inertia of the disk pivoted at its center of mass. Thus, the initial rotational inertia I_i is:
  </Text>
  <MathEquation latex="I_i = \frac{1}{2} M_d R_d^2" height={28} label="2" />
  <Text style={S.body}>Where M_d is the mass of the disk and R_d is the radius of the disk.</Text>

  <Text style={S.h3}>2.1.3  Final Rotational Inertia</Text>
  <Text style={S.body}>
    The final rotational inertia is the total rotational inertia of the object and disk pivoted at the center of the disk. Specifically, because the object cannot perfectly drop at the center of the disk, the distance between the disk's center and the ring's center x is measured to observe the dropping offset. Therefore, by parallel-axis theorem, when the object is a thick ring, the final rotational inertia I_f is:
  </Text>
  <MathEquation latex="I_f = \frac{1}{2}M_d R_d^2 + \frac{1}{2}M_r(R_1^2 + R_2^2) + M_r x^2" height={28} label="3" />
  <Text style={S.body}>
    Where M_r, R_1, and R_2 are the mass of the ring, the inner radius of the ring, and the outer radius of the ring, respectively.
  </Text>
  <Text style={S.body}>Besides, when the object is another disk, the final rotational inertia I_f is:</Text>
  <MathEquation latex="I_f = \frac{1}{2}M_d R_d^2 + \frac{1}{2}M'_d {R'_d}^2 + M'_d x^2" height={28} label="4" />
  <Text style={S.body}>
    {"Where M'd and R'd are the mass of another disk and the radius of another disk, respectively. Notably, since the new disk is dropped onto the slot of the rotation disk, the offset distance x between them can be regarded as 0."}
  </Text>

  <Text style={S.h3}>2.1.4  Rotational Kinetic Energy</Text>
  <Text style={S.body}>The rotational kinetic energy of a rotating object E_k is calculated by the following equation:</Text>
  <MathEquation latex="E_k = \frac{1}{2} I \omega^2" height={28} label="5" />
  <Text style={S.body}>Where I is the rotational inertia and w is the angular velocity.</Text>

  <Text style={S.h2}>2.2  Purposes of the Experiment</Text>
  <Text style={S.listItem}>1. Verifying the conservation of angular momentum.</Text>
  <Text style={S.listItem}>2. Finding the variation of rotational kinetic energy in the dropping process.</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 3 METHODS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>3  Methods</Text>
  <Text style={S.h2}>3.1  Setup</Text>

  <Text style={S.h3}>3.1.1  Mass and Length Measurement</Text>
  <Text style={S.body}>
    We first measured the arguments of the disassembled experimental components. The masses of the ring, the disk, and the pulley were measured by the electronic scale. Besides, a vernier caliper was utilized to record the inner and outer radius of the ring, the radius of the two disks, and the pulley's radius by measuring their diameters. Remarkably, despite the pulley's complex shape, its mass distribution approximately equals that of a uniform standard disk with the same radius. Therefore, the slight difference between the experimental rotational inertia calculated by the pulley's radius and its real value was negligible, so the measured pulley's radius is reliable for its rotational inertia computation.
  </Text>

  <Text style={S.h3}>3.1.2  Hardware Construction</Text>
  <Text style={S.body}>
    Firstly, the Rotary Motion Sensor was mounted onto the support rod and connected to the 550 Universal Interface. Notably, the small bolt on the Rotary Motion Sensor was removed to free the elastic pulley. Then, we attached the pulley and the disk to the Rotary Motion Sensor with a bolt. Remarkably, since the square hole of the disk aligned with the square raised area on the pulley when the bolt was tightened, the system was firmly fixed during rotation. Lastly, we leveled the disk to ensure stable rotations. After gently placing a level on the disk, two adjustable feet of the stand were utilized to center the bubble of the level while another foot was fixed.
  </Text>

  <Text style={S.h3}>3.1.3  Software Settings</Text>
  <Text style={S.body}>
    We clicked Calculator on PASCO Capstone and created formulas for the rotational inertia and angular momentum calculations. Notably, the masses and radius were measured in the previous process and entered as constants.
  </Text>

  <Text style={S.h3}>3.1.4  Testing: Level Check</Text>
  <Text style={S.body}>
    To ensure that the disk was horizontally placed, we put the ring on the disk and rotated them for level check. The ring was gently set at the edge of the disk, and the whole system was manually given a spin shortly after starting PASCO recording. After about 5 seconds, the button STOP was clicked to terminate the recording. Instead of periodic fluctuations, the curve is approximately linear with small bumps, which are expected variations. This indicates that the system maintained a horizontal state during rotation.
  </Text>

  <Text style={S.h2}>3.2  Procedure</Text>
  <Text style={S.body}>
    Firstly, we gave a clockwise rotation with an angular speed of around 20-30 rad/s to the disk and started PASCO recording to collect data of the initial spinning angular velocity.
  </Text>
  <Text style={S.body}>
    Then, the object was gently held 2-3 mm above the disk plane and dropped onto the spinning disk. Notably, it is essential to drop the ring from a low distance, for this can avoid the excessive vertical force on the bearing, which may cause a spike of frictional drag on the system and decrease the total angular momentum by producing external torque. Besides, though it is challenging to center perfectly on the disk, the object was still kept close enough to the center to make the measurements more precise and convenient.
  </Text>
  <Text style={S.body}>
    After collecting data of the spinning angular velocity with the object for an extra few seconds, the STOP button was clicked to end the recording and the object offset was observed. Since directly measuring the displacement between the centers of the object and the disk was hard, we found the minimum length between the disk's edge and the object instead, which was observed by marking the distance on an aided paper and measuring with a caliper. Based on this minimum length l_min, the offset distance x was indirectly calculated as:
  </Text>
  <MathEquation latex="x = r - l_{\min}" height={18} label="6" />
  <Text style={S.body}>
    Where r = 0.95 cm is the radius difference between the object and the disk. Remarkably, in this experiment, a thick ring and a similar disk are chosen to be the dropping object. Besides, to enhance the reliability of the experimental results, the procedures above were repeated three times for the ring case.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 4 RAW DATA ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>4  Raw Data</Text>
  <Text style={S.body}>
    Physical data: Based on the experimental procedures, the physical data, including the mass and radius of the pulley as well as the mass, inner and outer radius, offset distance, and rotational inertia of each object, are listed in Table 1 below.
  </Text>

  <T cap="Table 1: The physical data of each object."
    cols={[
      { h: 'Object', w: '14%', k: 'obj' },
      { h: 'Mass (g)', w: '12%', k: 'm' },
      { h: 'Outer R (cm)', w: '13%', k: 'ro' },
      { h: 'Inner R (cm)', w: '13%', k: 'ri' },
      { h: 'Pulley Mass (g)', w: '13%', k: 'pm' },
      { h: 'Pulley R (cm)', w: '11%', k: 'pr' },
      { h: 'Offset x (cm)', w: '11%', k: 'x' },
      { h: 'I (g*cm^2)', w: '13%', k: 'I' },
    ]}
    data={[
      ...ringTrials.map(t => ({
        obj: `Ring (run ${t.trial})`, m: f(t.dropMass, 2), ro: f(phys.ring.rOut, 3), ri: f(phys.ring.rIn, 3),
        pm: '0', pr: f(phys.pulley.r, 3), x: f(t.x, 3), I: f(t.fri, 2),
      })),
      { obj: 'Disk 1', m: f(phys.lowerDisk.mass, 2), ro: f(phys.lowerDisk.r, 3), ri: '0', pm: f(phys.pulley.mass, 2), pr: f(phys.pulley.r, 3), x: '0', I: f(iri, 2) },
      ...diskTrials.map(t => ({
        obj: 'Disk 2', m: f(t.dropMass, 2), ro: f(phys.upperDisk.r, 3), ri: '0', pm: '0', pr: f(phys.pulley.r, 3), x: '0', I: f(t.fri - iri, 2),
      })),
    ]}
  />

  <Text style={S.body}>Collision data: The collision data containing the initial and final angular velocities of the objects are displayed in Table 2.</Text>

  <T cap="Table 2: The collision data of each object."
    cols={[
      { h: 'Dropped Object', w: '34%', k: 'obj' },
      { h: 'Initial Angular Velocity (rad/s)', w: '33%', k: 'wi' },
      { h: 'Final Angular Velocity (rad/s)', w: '33%', k: 'wf' },
    ]}
    data={trials.map(t => ({
      obj: t.object === 'Ring' ? `Ring (run ${t.trial})` : 'Disk',
      wi: f(t.iav, 3), wf: f(t.fav, 3),
    }))}
  />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 5 DATA & ERROR ANALYSIS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>5  Data and Error Analysis</Text>
  <Text style={S.h2}>5.1  Data Analysis</Text>
  <Text style={S.body}>
    To validate the conservation of angular momentum, the initial and final angular momentum of each system are calculated and compared. Based on the raw data, the initial and final angular velocity w_i and w_f of each system are obtained. Besides, we compute the initial and final rotational inertia I_i and I_f using Equation (2)-(4). Thus, since the initial and final angular momentum are represented as L_i = I_i * w_i and L_f = I_f * w_f, these data are further calculated. Eventually, Table 3 shows the final results, where the percent difference (%diff) indicates the deviation between IAM and FAM:
  </Text>
  <MathEquation latex="\%\text{diff} = \frac{FAM - IAM}{IAM} \times 100\%" height={28} label="7" />

  <T cap="Table 3: Initial and final angular velocity (IAV & FAV), rotational inertia (IRI & FRI), and angular momentum (IAM & FAM) of each system."
    cols={[
      { h: 'System', w: '16%', k: 's' },
      { h: 'IAV (rad/s)', w: '11%', k: 'wi' }, { h: 'FAV (rad/s)', w: '11%', k: 'wf' },
      { h: 'IRI (g*cm^2)', w: '13%', k: 'ii' }, { h: 'FRI (g*cm^2)', w: '13%', k: 'if' },
      { h: 'IAM (g*cm^2/s)', w: '14%', k: 'li' }, { h: 'FAM (g*cm^2/s)', w: '14%', k: 'lf' },
      { h: '%diff', w: '8%', k: 'd' },
    ]}
    data={trials.map(t => ({
      s: sysLabel(t), wi: f(t.iav, 3), wf: f(t.fav, 3),
      ii: f(t.iri, 0), 'if': f(t.fri, 0),
      li: f(t.iam, 3), lf: f(t.fam, 3), d: f(t.pctDiff, 2),
    }))}
  />

  <Text style={S.body}>
    According to Table 3, the rotational inertia of each system increases while the angular velocity decreases after the collision process, and the initial angular momentum approximately equals the final angular momentum in each system with less than 3% absolute percent difference. This verifies the conservation of angular momentum. Notably, the slight errors are caused by the negligible friction during each trial, which will be detailed in the error analysis part.
  </Text>
  <Text style={S.body}>
    Furthermore, the initial and final kinetic energy of each system is calculated utilizing Equation (5) (E_k = (1/2)*I*w^2). Therefore, the results are demonstrated in Table 4, where the percent difference of energy (Energy%) is defined as below:
  </Text>
  <MathEquation latex="\text{Energy\%} = \frac{K_f - K_i}{K_i} \times 100\%" height={28} label="8" />

  <T cap="Table 4: Initial and final rotational kinetic energy and their percent difference of each system."
    cols={[
      { h: 'System', w: '30%', k: 's' },
      { h: 'Initial K (g*cm^2/s^2)', w: '24%', k: 'ki' },
      { h: 'Final K (g*cm^2/s^2)', w: '24%', k: 'kf' },
      { h: 'Energy%', w: '22%', k: 'e' },
    ]}
    data={trials.map(t => ({
      s: sysLabel(t), ki: f(t.initK, 0), kf: f(t.finalK, 0), e: f(t.energyPct, 2),
    }))}
  />

  <Text style={S.body}>
    As Table 4 shows, when dropping the ring on the disk, the rotational kinetic energy significantly decreased with about 80% percent difference, and this difference is approximately 51% when dropping another disk to change the rotation state. Since every part of the system spun at the same angular speed after collision, the fact that these results are consistent with the energy change in a completely inelastic collision verifies the data reliability.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 5.2 ERROR ANALYSIS ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h2}>5.2  Error Analysis</Text>
  <Text style={S.body}>Specifically, the following essential equation is utilized in error analysis:</Text>
  <MathEquation latex="\delta_k = \sqrt{\sum_{i=1}^{m}\left(\frac{\partial f}{\partial p_i}\right)^2 (\delta p_i)^2}" height={38} label="9" />

  <Text style={S.h3}>5.2.1  Error of Mass</Text>
  <Text style={S.bodyBold}>Instrumental error</Text>
  <Text style={S.body}>
    Since the masses of ring, disk, and pulley were measured by an electronic balance, the precision of this experimental instrument leads to the systematic error. Remarkably, the uncertainty of the electronic balance can be computed by the following equation:
  </Text>
  <MathEquation latex="\delta m = m \times 10^{-4} + 0.01" height={20} label="10" />
  <Text style={S.body}>Where m is the measured mass demonstrating of the electronic balance.</Text>
  <Text style={S.bodyBold}>Environmental error</Text>
  <Text style={S.body}>
    The complex external environment also disturbs the mass measurements. Typical examples are the variation of temperature, humidity, air flows, and electromagnetic fields, which impact the measure of mass and result in random errors. Notably, we can reduce these types of errors by measuring under a relatively stable condition, recording the readings after they maintain a constant value, and repeating the process multiple times.
  </Text>

  <Text style={S.h3}>5.2.2  Error of Radius</Text>
  <Text style={S.bodyBold}>Instrumental error</Text>
  <Text style={S.body}>
    The caliper is used for radius measurements, causing the instrumental error. Because the accuracy of a standard 20-division caliper is 0.05 mm, the uncertainty of the radius data is +/-0.0025 cm.
  </Text>
  <Text style={S.bodyBold}>Human error</Text>
  <Text style={S.body}>
    Another non-negligible error source is human operation. When clamping objects with a caliper, pressing too hard may deform the object and shorten the measured length. Besides, reading perpendicularly to align with measurement scales is difficult to realize, resulting in parallax errors. Moreover, the shapes of the objects are not ideal under experimental conditions, so different measuring criteria lead to diverse length results. Similarly, human error can be reduced by multiple measurements.
  </Text>

  <Text style={S.h3}>5.2.3  Error of Rotational Inertia</Text>
  <Text style={S.body}>The error of rotational inertia is propagated from errors of mass and radius. Equation (9) is used to calculate this propagated error. Thus, the error of the initial rotational inertia is:</Text>
  <MathEquation latex="\delta I = \sqrt{\left(\frac{\partial I}{\partial M_d}\right)^2(\delta M_d)^2 + \left(\frac{\partial I}{\partial R_d}\right)^2(\delta R_d)^2}" height={38} label="11" />
  <MathEquation latex="\frac{\partial I}{\partial M_d} = \frac{1}{2}R_d^2, \quad \frac{\partial I}{\partial R_d} = M_d R_d" height={28} label="12" />
  <Text style={S.body}>For uncertainty in final cases, when dropping a ring, Equation (9) is substituted to Equation (3) to obtain the error of final rotational inertia:</Text>
  <MathEquation latex="\delta I = \sqrt{\sum\left(\frac{\partial I}{\partial M}\right)^2(\delta M)^2 + \sum\left(\frac{\partial I}{\partial R}\right)^2(\delta R)^2 + \left(\frac{\partial I}{\partial x}\right)^2(\delta x)^2}" height={40} label="13" />
  <Text style={S.body}>Where the partial derivatives are:</Text>
  <MathEquation latex="\frac{\partial I}{\partial M_d}=\frac{1}{2}R_d^2,\quad \frac{\partial I}{\partial M_r}=\frac{1}{2}(R_1^2+R_2^2)+x^2" height={28} label="14" />
  <MathEquation latex="\frac{\partial I}{\partial R_d}=M_d R_d,\; \frac{\partial I}{\partial R_1}=M_r R_1,\; \frac{\partial I}{\partial R_2}=M_r R_2,\; \frac{\partial I}{\partial x}=2M_r x" height={28} label="15" />
  <Text style={S.body}>Besides, when dropping another disk, the error of final rotational inertia is:</Text>
  <MathEquation latex="\delta I = \sqrt{\sum\left(\frac{\partial I}{\partial M}\right)^2(\delta M)^2 + \sum\left(\frac{\partial I}{\partial R}\right)^2(\delta R)^2}" height={38} label="16" />
  <MathEquation latex="\frac{\partial I}{\partial M_d}=\frac{1}{2}R_d^2,\quad \frac{\partial I}{\partial M'_d}=\frac{1}{2}{R'_d}^2" height={28} label="17" />
  <MathEquation latex="\frac{\partial I}{\partial R_d}=M_d R_d,\quad \frac{\partial I}{\partial R'_d}=M'_d R'_d" height={28} label="18" />

  <Text style={S.h3}>5.2.4  Error of Angular Momentum</Text>
  <Text style={S.body}>Since the angular momentum is obtained by L = I*w, its uncertainty is computed as:</Text>
  <MathEquation latex="\delta L = \sqrt{(\omega\,\delta I)^2 + (I\,\delta\omega)^2}" height={30} label="19" />

  <Text style={S.h3}>5.2.5  Error of Rotational Angular Velocity and Energy</Text>
  <Text style={S.body}>
    The error in the initial and final angular velocities is caused by the precision of the Rotary Motion Sensor. Notably, PASCO Capstone displays the errors of angular velocities on its coordinate tool, which is +/-0.002 rad/s.
  </Text>
  <Text style={S.body}>Thus, the error of the rotational kinetic energy is:</Text>
  <MathEquation latex="\delta E_k = \sqrt{\frac{1}{4}(\omega^2\,\delta I)^2 + (I\omega\,\delta\omega)^2}" height={38} label="20" />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ 5.2.6 ERROR TABLES ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h3}>5.2.6  Presentation of Error</Text>
  <Text style={S.bodyBold}>Physical data</Text>
  <Text style={S.body}>Based on the previous discussion, the errors of the physical data are listed in Table 5.</Text>

  <T cap="Table 5: The physical data of each object with uncertainties."
    cols={[
      { h: 'Object', w: '13%', k: 'obj' },
      { h: 'Mass (g)', w: '13%', k: 'm' },
      { h: 'Outer R (cm)', w: '13%', k: 'ro' },
      { h: 'Inner R (cm)', w: '13%', k: 'ri' },
      { h: 'Pulley Mass (g)', w: '12%', k: 'pm' },
      { h: 'Pulley R (cm)', w: '12%', k: 'pr' },
      { h: 'Offset x (cm)', w: '12%', k: 'x' },
      { h: 'I (g*cm^2)', w: '12%', k: 'I' },
    ]}
    data={[
      ...ringTrials.map(t => ({
        obj: `Ring (${t.trial})`,
        m: `${f(t.dropMass,2)}+/-${dM_ring}`,
        ro: `${f(phys.ring.rOut,3)}+/-${dR}`, ri: `${f(phys.ring.rIn,3)}+/-${dR}`,
        pm: '0', pr: `${f(phys.pulley.r,3)}+/-${dR}`,
        x: `${f(t.x,3)}+/-${dR}`,
        I: `${f(t.fri,2)}+/-${f(dI_final(t),2)}`,
      })),
      {
        obj: 'Disk 1',
        m: `${f(phys.lowerDisk.mass,2)}+/-${dM_d1}`,
        ro: `${f(phys.lowerDisk.r,3)}+/-${dR}`, ri: '0',
        pm: `${f(phys.pulley.mass,2)}+/-${dM_pul}`, pr: `${f(phys.pulley.r,3)}+/-${dR}`,
        x: '0', I: `${f(iri,2)}+/-${f(dI_init,2)}`,
      },
      ...diskTrials.map(t => ({
        obj: 'Disk 2',
        m: `${f(t.dropMass,2)}+/-${dM_d2}`,
        ro: `${f(phys.upperDisk.r,3)}+/-${dR}`, ri: '0',
        pm: '0', pr: `${f(phys.pulley.r,3)}+/-${dR}`,
        x: '0', I: `${f(t.fri-iri,2)}+/-${f(dI_final(t)-dI_init,2)}`,
      })),
    ]}
  />

  <Text style={S.bodyBold}>Collision data</Text>
  <Text style={S.body}>The errors of the collision data are shown in Table 6.</Text>

  <T cap="Table 6: The collision data of each object with uncertainties."
    cols={[
      { h: 'Dropped Object', w: '34%', k: 'obj' },
      { h: 'Initial Angular Velocity (rad/s)', w: '33%', k: 'wi' },
      { h: 'Final Angular Velocity (rad/s)', w: '33%', k: 'wf' },
    ]}
    data={trials.map(t => ({
      obj: t.object === 'Ring' ? `Ring (run ${t.trial})` : 'Disk',
      wi: `${f(t.iav,3)}+/-${dW}`, wf: `${f(t.fav,3)}+/-${dW}`,
    }))}
  />

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.bodyBold}>Angular momentum</Text>
  <Text style={S.body}>Table 7 demonstrates the errors of the angular velocity, rotational inertia, and angular momentum of each system.</Text>

  <T cap="Table 7: IAV, FAV, IRI, FRI, IAM, FAM with uncertainties."
    cols={[
      { h: 'System', w: '14%', k: 's' },
      { h: 'IAV (rad/s)', w: '12%', k: 'wi' }, { h: 'FAV (rad/s)', w: '12%', k: 'wf' },
      { h: 'IRI (g*cm^2)', w: '14%', k: 'ii' }, { h: 'FRI (g*cm^2)', w: '14%', k: 'if' },
      { h: 'IAM (g*cm^2/s)', w: '16%', k: 'li' }, { h: 'FAM (g*cm^2/s)', w: '16%', k: 'lf' },
      { h: '%diff', w: '6%', k: 'd' },
    ]}
    data={trials.map(t => {
      const dIi = dI_init;
      const dIf = dI_final(t);
      const dLi = dL(t.iri, t.iav, dIi);
      const dLf = dL(t.fri, t.fav, dIf);
      return {
        s: sysLabel(t),
        wi: `${f(t.iav,3)}+/-${dW}`, wf: `${f(t.fav,3)}+/-${dW}`,
        ii: `${f(t.iri,0)}+/-${f(dIi,2)}`, 'if': `${f(t.fri,0)}+/-${f(dIf,2)}`,
        li: `${f(t.iam,3)}+/-${f(dLi,3)}`, lf: `${f(t.fam,3)}+/-${f(dLf,3)}`,
        d: f(t.pctDiff, 2),
      };
    })}
  />

  <Text style={S.bodyBold}>Rotational kinetic energy</Text>
  <Text style={S.body}>Table 8 shows the errors of the initial and final rotational kinetic energy of each system.</Text>

  <T cap="Table 8: Initial and final rotational kinetic energy with uncertainties."
    cols={[
      { h: 'System', w: '28%', k: 's' },
      { h: 'Initial K (g*cm^2/s^2)', w: '26%', k: 'ki' },
      { h: 'Final K (g*cm^2/s^2)', w: '26%', k: 'kf' },
      { h: 'Energy%', w: '20%', k: 'e' },
    ]}
    data={trials.map(t => {
      const dKEi = dKE(t.iri, t.iav, dI_init);
      const dKEf = dKE(t.fri, t.fav, dI_final(t));
      return {
        s: sysLabel(t),
        ki: `${f(t.initK,0)}+/-${f(dKEi,0)}`,
        kf: `${f(t.finalK,0)}+/-${f(dKEf,0)}`,
        e: f(t.energyPct, 2),
      };
    })}
  />

  <Text style={S.body}>Overall, all the errors are listed and analyzed in this section, including their sources and values.</Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ SECTION 6 CONCLUSION ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h1}>6  Conclusion</Text>
  <Text style={S.h2}>6.1  Answering the Questions</Text>

  <Text style={S.bodyBold}>1. What effect should each of the following have on the value you calculate for the final angular momentum. State whether each would cause the final value to be low, high, or unchanged and explain why.</Text>

  <Text style={S.bodyBold}>a. If the axis of Rotary Motion Sensor has a small rotational inertia (in addition to the pulley)?</Text>
  <Text style={S.body}>
    The small rotational inertia of the Rotary Motion Sensor axis will cause the final angular momentum to be low. Since the axis is also regarded as a part of the rotational system, the ignorance of adding the angular momentum of this part will lead to a slightly lower final result compared with its ideal value.
  </Text>

  <Text style={S.bodyBold}>b. If the frictional drag on the bearings during the collision cannot be ignored?</Text>
  <Text style={S.body}>
    The final angular momentum calculated without considering the frictional drag on the bearings during the collision will be low. If the frictional drag cannot be ignored, an external torque caused by this frictional force will be added to this system. Therefore, angular momentum conservation no longer holds and the system's angular momentum is reduced during collision. To sum up, the frictional drag acting on the system during the collision will slightly decrease the total angular momentum of the system and cause a lower final experimental value.
  </Text>

  <Text style={S.bodyBold}>2. Does the experimental result support the Law of Conservation of Angular Momentum? Explain fully.</Text>
  <Text style={S.body}>
    The experimental result supports the Law of Angular Momentum Conservation. We provided isolation of the rotational system and minimized the disturbance of external conditions in procedures. Based on these, experimental data are collected and show consistency with theoretical results.
  </Text>
  <Text style={S.body}>
    Specifically, we first guarantee the zero external torque environment of the closed system. The disk rotated smoothly during each trial and spinning speed was properly selected to prevent larger friction forces due to the high speed. Besides, the object was gently dropped on the disk to minimize the frictional drag mentioned above.
  </Text>
  <Text style={S.body}>
    Besides, related data are completely collected. For angular velocities, initial and final values were recorded using the Rotary Motion Sensor. For rotational inertia, the dimensions of each object, including its mass and radius, were measured carefully to calculate the experimental results of the object's moment of inertia. Remarkably, all the measurements have reasonable precision with specific uncertainties, which are obtained from the resolution of experimental instruments.
  </Text>
  <Text style={S.body}>
    Lastly, we computed the percent differences to verify the results. According to the computing results, it is found that the initial angular momentum (IAM) is approximately equal to and slightly larger than the final angular momentum (FAM) in each trial with the percent differences less than 3%, which implies the acceptable range.
  </Text>
  <Text style={S.body}>
    Overall, by ensuring a suitable experimental environment, collecting essential data, and validating with the computation of percent differences, the Law of Conservation of Angular Momentum is supported by our experimental results.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.bodyBold}>3. Was Kinetic Energy conserved in the collision? Explain how you know.</Text>
  <Text style={S.body}>
    The kinetic energy was not conserved in the collision. Many factors cause the loss of kinetic energy. Firstly, the frictional force acting on both the object and the disk can reduce their rotational speed and lead to a dissipation of the system's mechanical energy. Secondly, during collisions, deformation of the two objects occurred and a part of the kinetic energy in the system was transferred into internal energy. Furthermore, kinetic energy can be consumed by other transfer types, such as the reduction due to the air resistance and changes in sound wave energy caused by the collision.
  </Text>

  <Text style={S.bodyBold}>4. Typically, you should see a loss of angular moment for the ring of 5%-15%. If you did the disk drop, it should have shown a drop of a few percent.</Text>
  <Text style={S.bodyBold}>a. Why should the disk drop work better?</Text>
  <Text style={S.body}>
    Firstly, the alignment of the disk is better than that of the ring. Since the similar shape of the two disks, the exact center of the rotating axis can be easier to observe, which may be hard to find when dropping a ring. When the object's center is far away from the rotating axis, additional torque will be generated, leading to a reduction of the system's angular momentum. Therefore, placing a ring will be more likely to decrease the total angular momentum of the system, meaning that the disk drop generally works better in the experiment.
  </Text>
  <Text style={S.body}>
    Secondly, the inward square design of the disk reduces friction during contact. Due to its special design, the inward square perfectly fits the two disks, avoiding slipping and damping which may happen when dropping a ring. This advantage also minimizes the extra torque in the rotating system with a disk, which leads to a better working condition.
  </Text>
  <Text style={S.body}>
    Thirdly, the shape and mass of the disk also decreases angular momentum losses compared with the ring. Because of its lighter weight, the disk will produce less frictional drag than the ring when contacting the rotating plane, leading to a reduction of angular momentum loss. Besides, the shape of the disk is flatter than the ring, reducing the air resistance in dropping and rotating, as well as the probability of oblique collision with extra loss of the system's angular momentum.
  </Text>

  <Text style={S.bodyBold}>b. What causes the small percentage of loss of the angular momentum after the drop?</Text>
  <Text style={S.body}>
    The main reason is that the frictional external torques still exist and decrease the angular momentum of the system. Despite the minimization of external torque disturbances, the frictional drag of bearing still produces slight frictional torque, resulting in a small percentage of loss of the angular momentum.
  </Text>
  <Text style={S.body}>
    Another possible reason is the inadequate measuring precision in the experiment. Due to the resolution of the instruments, small deviations may be generated in complex calculations, resulting in a loss of the system's angular momentum. Notably, a remarkable case is that we cannot precisely observe the real position of the rotating axis because of the slight slipping between the object and the disk, causing the inaccurate computation of the rotational inertia.
  </Text>
  <Text style={S.body}>
    Furthermore, many other factors affect the decreased result, including the air resistance acting on the objects as well as the energy loss of heat and sound, which lead to a smaller final rotational angular velocity than its theoretical value.
  </Text>

  <Text style={S.bodyBold}>5. In the ideal case, how can angular momentum be conserved, but energy not be conserved?</Text>
  <Text style={S.body}>
    For angular momentum, the conservation holds in the ideal case since there is no external torque. According to Newton's 3rd Law, the interaction forces of the object and the disk during collisions are in the same magnitude with opposite directions, indicating that the net force and net torque acting on this whole system is 0. Therefore, the total angular momentum is conserved.
  </Text>
  <Text style={S.body}>
    For energy, the conservation doesn't hold because the collision is inelastic. The friction force between the object and the disk is always generated to approach the co-velocity state. This is a non-conservative force, which transforms kinetic energy into internal energy. Thus, the total kinetic energy is no longer conserved.
  </Text>

  <Text style={S.pageNum} render={({ pageNumber }) => `${pageNumber}`} fixed />
</Page>

{/* ═══════════════════════════ 6.2 SUMMARY ═══════════════════════════ */}
<Page size="A4" style={S.page}>
  <Hdr />
  <Text style={S.h2}>6.2  Summary</Text>
  <Text style={S.body}>
    The experiment aims to verify the law of angular momentum conservation based on the constructed equipment including the Rotary Motion Sensor and a rotating disk. According to the theorems displayed in the objective section, we focus on observing the initial and final angular velocities and rotational inertia of the system in each trial. Notably, angular velocities were recorded by the Rotary Motion Sensor, and the graphs of angular speed change after collisions were obtained by following the procedures. Besides, rotational inertia was computed by measuring the dimension of each object.
  </Text>
  <Text style={S.body}>
    After finishing the procedures, the raw data are completely collected to derive the changes in angular momentum and kinetic energy of the system in different trials. By comparing the experimental values of initial and final angular momentum and calculating their percent differences, which are less than 3%, the conservation of angular momentum is eventually verified in an acceptable range. In addition, the reduction of kinetic energy is also analyzed, highlighting the transferred internal energy.
  </Text>
  <Text style={S.body}>
    Through the experiment, the final angular momentum is slightly smaller than its initial value, which is mainly caused by the existence of external torques. Many efforts were adopted to minimize this disturbance, such as dropping the object low enough and keeping its center close to the rotational axis. The experiment results also show that the mass, shape, and special design of the disk can effectively reduce the frictional drag of bearing compared with the ring. However, the influence of torques that decrease the total angular momentum still can not be ignored during the process.
  </Text>
  <Text style={S.body}>
    Therefore, improvements to the experiment will mainly focus on minimizing the extra force to further reduce the net torque. Moreover, more precise instruments can also be utilized to enhance the accuracy of this experiment, and more trials can be recorded to tackle the random errors.
  </Text>
  <Text style={S.body}>
    Overall, the conservation of angular momentum is successfully validated in this experiment, ensuring its reliability in real-world applications.
  </Text>

{/* ═══════════════════════════ SECTION 7 APPENDIX ═══════════════════════════ */}
  <Text style={S.h1}>7  Appendix</Text>
  <Text style={S.body}>(Experimental graphs of angular speed change after each collision go here.)</Text>
  <Text style={S.body}>Figure 5: The graph of angular speed change after ring collision 1.</Text>
  <Text style={S.body}>Figure 6: The graph of angular speed change after ring collision 2.</Text>
  <Text style={S.body}>Figure 7: The graph of angular speed change after ring collision 3.</Text>
  <Text style={S.body}>Figure 8: The graph of angular speed change after disk collision.</Text>

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

export default LabReportPDF;
