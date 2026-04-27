/**
 * Generate publication-quality chart images for the Exp3 (Ballistic Pendulum)
 * lab report. Uses Canvas 2D API → base64 PNG data URLs for @react-pdf/renderer.
 *
 * Charts produced:
 *   - renderTrialPendulumChart   per-trial θ(t) (deg) curve with apex marker and
 *                                ball-impact marker, in the style of the lab manual.
 *   - renderV0Comparison         scatter of v₀ set vs v₀ measured + y = x line +
 *                                mean line (formula verification).
 *   - renderKEChart              grouped bar chart of KE_in vs KE_after across trials.
 */
import type { Exp3Trial } from '../components/Exp3ReportPDF';

const DPR = 2;

const PALETTE = {
  primary: '#1d4ed8',
  apex: '#dc2626',
  impact: '#16a34a',
  grid: '#dcdcdc',
  axis: '#111827',
  text: '#111827',
  muted: '#6b7280',
  yEqualsX: '#9ca3af',
  ke_in: '#7c3aed',
  ke_after: '#0ea5e9',
};

// ---------------------------------------------------------------------- helpers

function newCanvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas');
  c.width = w * DPR;
  c.height = h * DPR;
  const ctx = c.getContext('2d')!;
  ctx.scale(DPR, DPR);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  return [c, ctx];
}

function niceStep(range: number, target: number): number {
  if (range <= 0) return 1;
  const raw = range / target;
  const exp = Math.floor(Math.log10(raw));
  const base = raw / Math.pow(10, exp);
  let nice: number;
  if (base < 1.5) nice = 1;
  else if (base < 3) nice = 2;
  else if (base < 7) nice = 5;
  else nice = 10;
  return nice * Math.pow(10, exp);
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  pad: { l: number; r: number; t: number; b: number },
  title: string,
  xLabel: string,
  yLabel: string,
): { plotL: number; plotR: number; plotT: number; plotB: number; plotW: number; plotH: number } {
  const plotL = pad.l;
  const plotR = w - pad.r;
  const plotT = pad.t;
  const plotB = h - pad.b;
  const plotW = plotR - plotL;
  const plotH = plotB - plotT;

  ctx.fillStyle = PALETTE.text;
  ctx.font = 'bold 14px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillText(title, w / 2, 12);

  ctx.font = '11px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.muted;
  ctx.fillText(xLabel, plotL + plotW / 2, h - 22);

  ctx.save();
  ctx.translate(16, plotT + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();

  return { plotL, plotR, plotT, plotB, plotW, plotH };
}

function drawAxes(
  ctx: CanvasRenderingContext2D,
  box: { plotL: number; plotR: number; plotT: number; plotB: number; plotW: number; plotH: number },
) {
  ctx.strokeStyle = PALETTE.axis;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(box.plotL, box.plotT);
  ctx.lineTo(box.plotL, box.plotB);
  ctx.lineTo(box.plotR, box.plotB);
  ctx.stroke();
}

// --------------------------------------------------------------- trial chart

export interface PendulumChartOptions {
  title: string;
  series: { t: number; theta: number }[];     // θ in DEGREES
  thetaMax: number;                           // deg
  apexTime?: number;                          // seconds, optional
  impactTime?: number;                        // seconds, optional
  v0_set: number;                             // m/s — annotation
  v0_measured: number;                        // m/s — annotation
}

export function renderTrialPendulumChart(opts: PendulumChartOptions): string {
  const { title, series, thetaMax, apexTime, impactTime, v0_set, v0_measured } = opts;
  if (series.length < 4) return '';

  const W = 720;
  const H = 420;
  const pad = { l: 78, r: 30, t: 50, b: 70 };
  const [canvas, ctx] = newCanvas(W, H);
  const box = drawFrame(ctx, W, H, pad, title, 'Time t (s)', 'Pendulum angle θ (°)');

  const tMin = series[0].t;
  const tMax = series[series.length - 1].t;
  const tRange = Math.max(tMax - tMin, 0.05);
  const yTop = Math.max(thetaMax * 1.20, 5, ...series.map(s => s.theta));
  const yBot = Math.min(0, ...series.map(s => s.theta));
  const yPad = Math.max((yTop - yBot) * 0.10, 1.0);
  const yMin = yBot - yPad;
  const yMax = yTop + yPad;

  const xStep = niceStep(tRange, 6);
  const yStep = niceStep(yMax - yMin, 6);

  const toX = (t: number) => box.plotL + ((t - tMin) / tRange) * box.plotW;
  const toY = (v: number) => box.plotT + (1 - (v - yMin) / (yMax - yMin)) * box.plotH;

  ctx.strokeStyle = PALETTE.grid;
  ctx.lineWidth = 0.5;
  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.muted;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  for (let v = Math.ceil(yMin / yStep) * yStep; v <= yMax; v += yStep) {
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(box.plotL, y);
    ctx.lineTo(box.plotR, y);
    ctx.stroke();
    ctx.fillText(v.toFixed(yStep < 1 ? 1 : 0), box.plotL - 6, y);
  }
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let t = Math.ceil(tMin / xStep) * xStep; t <= tMax; t += xStep) {
    const x = toX(t);
    ctx.beginPath();
    ctx.moveTo(x, box.plotT);
    ctx.lineTo(x, box.plotB);
    ctx.stroke();
    ctx.fillText(t.toFixed(xStep < 1 ? 1 : 0), x, box.plotB + 6);
  }

  drawAxes(ctx, box);

  ctx.strokeStyle = PALETTE.primary;
  ctx.lineWidth = 2.2;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  for (let i = 0; i < series.length; i++) {
    const x = toX(series[i].t);
    const y = toY(series[i].theta);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  const annotate = (
    color: string, x: number, y: number, label: string, anchor: 'left' | 'right',
  ) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.font = 'bold 11px "Helvetica Neue", Arial, sans-serif';
    const tw = ctx.measureText(label).width;
    const padBox = 6;
    const boxW = tw + padBox * 2;
    const boxH = 18;
    const offX = anchor === 'right' ? 10 : -boxW - 10;
    const bx = x + offX;
    const by = y - boxH / 2 - 6;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.0;
    ctx.fillRect(bx, by, boxW, boxH);
    ctx.strokeRect(bx, by, boxW, boxH);
    ctx.fillStyle = color;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, bx + padBox, by + boxH / 2);
  };

  if (typeof impactTime === 'number') {
    const idx = series.findIndex(s => s.t >= impactTime);
    if (idx >= 0) annotate(PALETTE.impact, toX(series[idx].t), toY(series[idx].theta),
      `Impact t=${impactTime.toFixed(2)}s`, 'right');
  }
  if (typeof apexTime === 'number') {
    const idx = series.reduce((best, s, i) =>
      Math.abs(s.theta) > Math.abs(series[best].theta) ? i : best, 0);
    annotate(PALETTE.apex, toX(series[idx].t), toY(series[idx].theta),
      `θ_max=${thetaMax.toFixed(2)}°`, 'left');
  }

  ctx.font = '10.5px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.text;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  const note1 = `v₀ set = ${v0_set.toFixed(3)} m/s`;
  const note2 = `v₀ measured = ${v0_measured.toFixed(3)} m/s`;
  ctx.fillText(note1, box.plotR - 4, box.plotT + 4);
  ctx.fillText(note2, box.plotR - 4, box.plotT + 18);

  return canvas.toDataURL('image/png', 0.95);
}

// --------------------------------------------------------------- v0 scatter

export function renderV0Comparison(trials: Exp3Trial[]): string {
  if (trials.length === 0) return '';
  const W = 720;
  const H = 440;
  const pad = { l: 78, r: 32, t: 50, b: 70 };
  const [canvas, ctx] = newCanvas(W, H);
  const box = drawFrame(
    ctx, W, H, pad,
    'v₀ verification: set value vs. derived from θ_max',
    'v₀ set (m/s)', 'v₀ derived from θ_max (m/s)',
  );

  const xs = trials.map(t => t.v0_input);
  const ys = trials.map(t => t.v0_measured);
  const lo = Math.max(0, Math.min(...xs, ...ys) - 0.5);
  const hi = Math.max(...xs, ...ys) + 0.5;

  const step = niceStep(hi - lo, 6);
  const toX = (v: number) => box.plotL + ((v - lo) / (hi - lo)) * box.plotW;
  const toY = (v: number) => box.plotT + (1 - (v - lo) / (hi - lo)) * box.plotH;

  ctx.strokeStyle = PALETTE.grid;
  ctx.lineWidth = 0.5;
  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.muted;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(box.plotL, y);
    ctx.lineTo(box.plotR, y);
    ctx.stroke();
    ctx.fillText(v.toFixed(step < 1 ? 1 : 0), box.plotL - 6, y);
  }
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    const x = toX(v);
    ctx.beginPath();
    ctx.moveTo(x, box.plotT);
    ctx.lineTo(x, box.plotB);
    ctx.stroke();
    ctx.fillText(v.toFixed(step < 1 ? 1 : 0), x, box.plotB + 6);
  }

  drawAxes(ctx, box);

  ctx.strokeStyle = PALETTE.yEqualsX;
  ctx.lineWidth = 1.2;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(toX(lo), toY(lo));
  ctx.lineTo(toX(hi), toY(hi));
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.muted;
  ctx.textAlign = 'right';
  ctx.fillText('y = x', toX(hi) - 6, toY(hi) + 12);

  trials.forEach((t, i) => {
    const x = toX(t.v0_input);
    const y = toY(t.v0_measured);
    ctx.fillStyle = PALETTE.primary;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = PALETTE.text;
    ctx.font = 'bold 10px "Helvetica Neue", Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(`#${t.trial}`, x + 9, y - 3);
    ctx.font = '9px "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = Math.abs(t.v0_error_pct) < 3 ? '#16a34a' : '#dc2626';
    ctx.fillText(`${t.v0_error_pct >= 0 ? '+' : ''}${t.v0_error_pct.toFixed(2)}%`, x + 9, y + 9);
  });

  return canvas.toDataURL('image/png', 0.95);
}

// --------------------------------------------------------------- KE bar chart

export function renderKEChart(trials: Exp3Trial[]): string {
  if (trials.length === 0) return '';
  const W = 720;
  const H = 420;
  const pad = { l: 78, r: 32, t: 50, b: 84 };
  const [canvas, ctx] = newCanvas(W, H);
  const box = drawFrame(
    ctx, W, H, pad,
    'Kinetic energy before vs after the inelastic collision',
    'Trial #', 'Kinetic energy (J)',
  );

  const yMax = Math.max(...trials.map(t => t.ke_input), 0.001) * 1.20;
  const yStep = niceStep(yMax, 5);
  const toY = (v: number) => box.plotT + (1 - v / yMax) * box.plotH;

  ctx.strokeStyle = PALETTE.grid;
  ctx.lineWidth = 0.5;
  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = PALETTE.muted;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  for (let v = 0; v <= yMax; v += yStep) {
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(box.plotL, y);
    ctx.lineTo(box.plotR, y);
    ctx.stroke();
    ctx.fillText(v.toFixed(yStep < 0.1 ? 3 : yStep < 1 ? 2 : 1), box.plotL - 6, y);
  }
  drawAxes(ctx, box);

  const groupW = box.plotW / trials.length;
  const barW = Math.min(38, groupW * 0.35);
  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = 'center';

  trials.forEach((t, i) => {
    const cx = box.plotL + groupW * (i + 0.5);
    const y_in = toY(t.ke_input);
    const y_after = toY(t.ke_after_ideal);
    ctx.fillStyle = PALETTE.ke_in;
    ctx.fillRect(cx - barW - 2, y_in, barW, box.plotB - y_in);
    ctx.fillStyle = PALETTE.ke_after;
    ctx.fillRect(cx + 2, y_after, barW, box.plotB - y_after);

    ctx.fillStyle = PALETTE.text;
    ctx.textBaseline = 'top';
    ctx.fillText(`#${t.trial}`, cx, box.plotB + 6);
    ctx.fillStyle = '#dc2626';
    ctx.font = 'bold 10px "Helvetica Neue", Arial, sans-serif';
    ctx.fillText(`-${t.ke_loss_percent.toFixed(1)}%`, cx, box.plotB + 22);
    ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  });

  const legY = H - 14;
  const legend = [
    { color: PALETTE.ke_in, label: 'KE before (½ m_ball v₀²)' },
    { color: PALETTE.ke_after, label: 'KE after (½ M v²)' },
  ];
  let legX = box.plotL;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  ctx.font = '10.5px "Helvetica Neue", Arial, sans-serif';
  legend.forEach(l => {
    ctx.fillStyle = l.color;
    ctx.fillRect(legX, legY - 6, 14, 12);
    ctx.fillStyle = PALETTE.text;
    ctx.fillText(l.label, legX + 20, legY);
    legX += ctx.measureText(l.label).width + 60;
  });

  return canvas.toDataURL('image/png', 0.95);
}

// --------------------------------------------------------------- public bundle

export interface Exp3ChartImages {
  trialCharts: string[];   // one per trial — θ(t)
  v0Comparison: string;
  keChart: string;
}

export function generateExp3Charts(trials: Exp3Trial[]): Exp3ChartImages {
  return {
    trialCharts: trials.map(t => {
      if (!t.thetaSeries || t.thetaSeries.length < 4) return '';
      return renderTrialPendulumChart({
        title: `Run #${t.trial} — pendulum angle θ(t)`,
        series: t.thetaSeries,
        thetaMax: t.theta_max_deg,
        apexTime: t.apex_time,
        impactTime: t.impact_time,
        v0_set: t.v0_input,
        v0_measured: t.v0_measured,
      });
    }),
    v0Comparison: renderV0Comparison(trials),
    keChart: renderKEChart(trials),
  };
}
