/**
 * Generate publication-quality chart images for the Exp7 lab report.
 * Uses Canvas 2D API → base64 PNG data URLs for @react-pdf/renderer.
 */
import { type Exp7Trial } from '../components/Exp7ReportPDF';

export interface Exp7ChartImages {
  velocityChart: string;
  momentumChart: string;
  keChart: string;
  keLossChart: string;
}

const DPR = 2;
const W = 680;
const H = 360;
const M = { t: 44, r: 24, b: 52, l: 62 };

const C = {
  v1i: '#DC2626', v2i: '#2563EB', v1f: '#F87171', v2f: '#60A5FA',
  pBefore: '#047857', pAfter: '#34D399',
  keBefore: '#B45309', keAfter: '#FBBF24',
  theory: '#6366F1',
  grid: '#E5E7EB', axis: '#374151', text: '#111827', muted: '#6B7280',
};

function mkCanvas(): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas');
  c.width = W * DPR;
  c.height = H * DPR;
  const ctx = c.getContext('2d')!;
  ctx.scale(DPR, DPR);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, W, H);
  return [c, ctx];
}

function niceRange(vals: number[]): [number, number] {
  const mn = Math.min(...vals);
  const mx = Math.max(...vals);
  const pad = Math.max(Math.abs(mx - mn) * 0.15, 0.01);
  const lo = mn < 0 ? mn - pad : 0;
  const hi = mx + pad;
  return [parseFloat(lo.toFixed(4)), parseFloat(hi.toFixed(4))];
}

function linspace(a: number, b: number, n: number): number[] {
  const s = (b - a) / (n - 1);
  return Array.from({ length: n }, (_, i) => parseFloat((a + i * s).toFixed(6)));
}

function yPx(v: number, yMin: number, yMax: number): number {
  return M.t + (1 - (v - yMin) / (yMax - yMin)) * (H - M.t - M.b);
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  title: string, xLabel: string, yLabel: string,
  yMin: number, yMax: number,
): number[] {
  const pL = M.l, pR = W - M.r, pT = M.t, pB = H - M.b;

  ctx.fillStyle = C.text;
  ctx.font = 'bold 13px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(title, W / 2, 22);

  ctx.save();
  ctx.translate(14, (pT + pB) / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = C.muted;
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();

  ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
  ctx.fillStyle = C.muted;
  ctx.textAlign = 'center';
  ctx.fillText(xLabel, (pL + pR) / 2, H - 6);

  const ticks = linspace(yMin, yMax, 6);
  ctx.textAlign = 'right';
  ctx.font = '9px "Helvetica Neue", Arial, sans-serif';
  for (const v of ticks) {
    const y = yPx(v, yMin, yMax);
    ctx.strokeStyle = C.grid;
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(pL, y); ctx.lineTo(pR, y); ctx.stroke();
    ctx.fillStyle = C.muted;
    ctx.fillText(v.toFixed(Math.abs(v) < 0.1 ? 4 : 2), pL - 5, y + 3);
  }

  if (yMin < 0 && yMax > 0) {
    const y0 = yPx(0, yMin, yMax);
    ctx.strokeStyle = C.axis;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(pL, y0); ctx.lineTo(pR, y0); ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.strokeStyle = C.axis;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pL, pT); ctx.lineTo(pL, pB); ctx.lineTo(pR, pB);
  ctx.stroke();

  return ticks;
}

function drawLegend(ctx: CanvasRenderingContext2D, items: { color: string; label: string }[], y: number) {
  ctx.font = '9px "Helvetica Neue", Arial, sans-serif';
  let totalW = items.reduce((s, it) => s + ctx.measureText(it.label).width + 26, 0);
  let x = (W - totalW) / 2;
  for (const it of items) {
    ctx.fillStyle = it.color;
    ctx.fillRect(x, y, 10, 10);
    ctx.strokeStyle = '#00000030';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(x, y, 10, 10);
    ctx.fillStyle = C.text;
    ctx.textAlign = 'left';
    ctx.fillText(it.label, x + 14, y + 9);
    x += ctx.measureText(it.label).width + 26;
  }
}

function drawBar(ctx: CanvasRenderingContext2D, x: number, w: number, yBase: number, yVal: number, color: string) {
  const top = Math.min(yBase, yVal);
  const h = Math.abs(yVal - yBase);
  if (h < 0.5) return;
  ctx.fillStyle = color;
  ctx.fillRect(x, top, w, h);
  ctx.strokeStyle = '#00000020';
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x, top, w, h);
}

// ════════════════════════════════════════════════════════════════════
// Chart 1: Velocity Comparison (grouped bars per trial)
// ════════════════════════════════════════════════════════════════════

function velocityChart(trials: Exp7Trial[]): string {
  const [canvas, ctx] = mkCanvas();
  const allV = trials.flatMap(t => [t.v1i, t.v2i, t.v1f, t.v2f]);
  const [yMin, yMax] = niceRange(allV);
  drawFrame(ctx, 'Figure 1: Cart Velocities Before and After Collision', 'Trial', 'Velocity (m/s)', yMin, yMax);

  const pL = M.l, pR = W - M.r, pB = H - M.b;
  const n = trials.length;
  const gW = (pR - pL) / n;
  const bW = gW / 5.5;
  const y0 = yPx(0, yMin, yMax);

  for (let i = 0; i < n; i++) {
    const t = trials[i];
    const gx = pL + i * gW + gW * 0.12;
    drawBar(ctx, gx, bW, y0, yPx(t.v1i, yMin, yMax), C.v1i);
    drawBar(ctx, gx + bW * 1.1, bW, y0, yPx(t.v2i, yMin, yMax), C.v2i);
    drawBar(ctx, gx + bW * 2.2, bW, y0, yPx(t.v1f, yMin, yMax), C.v1f);
    drawBar(ctx, gx + bW * 3.3, bW, y0, yPx(t.v2f, yMin, yMax), C.v2f);

    ctx.fillStyle = C.muted;
    ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`Trial ${t.trial}`, pL + i * gW + gW / 2, pB + 16);
  }

  drawLegend(ctx, [
    { color: C.v1i, label: 'v₁ initial' },
    { color: C.v2i, label: 'v₂ initial' },
    { color: C.v1f, label: 'v₁ final' },
    { color: C.v2f, label: 'v₂ final' },
  ], 30);

  return canvas.toDataURL('image/png');
}

// ════════════════════════════════════════════════════════════════════
// Chart 2: Total Momentum Before vs After
// ════════════════════════════════════════════════════════════════════

function momentumChart(trials: Exp7Trial[]): string {
  const [canvas, ctx] = mkCanvas();
  const allP = trials.flatMap(t => [t.pBefore, t.pAfter]);
  const [yMin, yMax] = niceRange(allP);
  drawFrame(ctx, 'Figure 2: Total System Momentum — Before vs After Collision', 'Trial', 'Total Momentum (kg·m/s)', yMin, yMax);

  const pL = M.l, pR = W - M.r, pB = H - M.b;
  const n = trials.length;
  const gW = (pR - pL) / n;
  const bW = gW / 3.2;
  const y0 = yPx(0, yMin, yMax);

  for (let i = 0; i < n; i++) {
    const t = trials[i];
    const gx = pL + i * gW + gW * 0.18;
    drawBar(ctx, gx, bW, y0, yPx(t.pBefore, yMin, yMax), C.pBefore);
    drawBar(ctx, gx + bW * 1.15, bW, y0, yPx(t.pAfter, yMin, yMax), C.pAfter);

    ctx.fillStyle = C.muted;
    ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`Trial ${t.trial}`, pL + i * gW + gW / 2, pB + 16);

    ctx.font = '8px "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = '#059669';
    ctx.fillText(`Δ=${t.pPctDiff.toFixed(1)}%`, pL + i * gW + gW / 2, pB + 28);
  }

  drawLegend(ctx, [
    { color: C.pBefore, label: 'p_total (before)' },
    { color: C.pAfter, label: 'p_total (after)' },
  ], 30);

  return canvas.toDataURL('image/png');
}

// ════════════════════════════════════════════════════════════════════
// Chart 3: Total KE Before vs After
// ════════════════════════════════════════════════════════════════════

function keChart(trials: Exp7Trial[]): string {
  const [canvas, ctx] = mkCanvas();
  const allKE = trials.flatMap(t => [t.keBefore, t.keAfter]);
  const [, yMax] = niceRange(allKE);
  drawFrame(ctx, 'Figure 3: Total Kinetic Energy — Before vs After Collision', 'Trial', 'Total KE (J)', 0, yMax);

  const pL = M.l, pR = W - M.r, pB = H - M.b;
  const n = trials.length;
  const gW = (pR - pL) / n;
  const bW = gW / 3.2;
  const y0 = yPx(0, 0, yMax);

  for (let i = 0; i < n; i++) {
    const t = trials[i];
    const gx = pL + i * gW + gW * 0.18;
    drawBar(ctx, gx, bW, y0, yPx(t.keBefore, 0, yMax), C.keBefore);
    drawBar(ctx, gx + bW * 1.15, bW, y0, yPx(t.keAfter, 0, yMax), C.keAfter);

    ctx.fillStyle = C.muted;
    ctx.font = '10px "Helvetica Neue", Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`Trial ${t.trial}`, pL + i * gW + gW / 2, pB + 16);

    ctx.font = '8px "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = '#B45309';
    const lossTxt = t.keLossPct > 0.5 ? `−${t.keLossPct.toFixed(1)}%` : '≈0%';
    ctx.fillText(lossTxt, pL + i * gW + gW / 2, pB + 28);
  }

  drawLegend(ctx, [
    { color: C.keBefore, label: 'KE (before)' },
    { color: C.keAfter, label: 'KE (after)' },
  ], 30);

  return canvas.toDataURL('image/png');
}

// ════════════════════════════════════════════════════════════════════
// Chart 4: KE Loss % vs Coefficient of Restitution (scatter + theory)
// ════════════════════════════════════════════════════════════════════

function keLossChart(trials: Exp7Trial[]): string {
  const [canvas, ctx] = mkCanvas();
  drawFrame(ctx, 'Figure 4: Kinetic Energy Loss vs Coefficient of Restitution', 'Coefficient of Restitution (e)', 'KE Loss (%)', 0, 105);

  const pL = M.l, pR = W - M.r, pT = M.t, pB = H - M.b;

  // Theory curve: for equal-mass head-on, KE_loss = (1−e²)×100%
  // General: KE_loss = μ(v_rel)²(1−e²) / (2 KE_initial) ×100
  // We draw the equal-mass approximation as a reference line.
  ctx.strokeStyle = C.theory;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 3]);
  ctx.beginPath();
  for (let i = 0; i <= 100; i++) {
    const e = i / 100;
    const loss = (1 - e * e) * 100;
    const px = pL + (e / 1.0) * (pR - pL);
    const py = yPx(loss, 0, 105);
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // X-axis ticks
  ctx.font = '9px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = 'center';
  for (let e = 0; e <= 1.0; e += 0.2) {
    const px = pL + (e / 1.0) * (pR - pL);
    ctx.fillStyle = C.muted;
    ctx.fillText(e.toFixed(1), px, pB + 14);
    ctx.strokeStyle = C.grid;
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(px, pT); ctx.lineTo(px, pB); ctx.stroke();
  }

  // Data points
  for (const t of trials) {
    const px = pL + (t.restitution / 1.0) * (pR - pL);
    const py = yPx(t.keLossPct, 0, 105);
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#DC2626';
    ctx.fill();
    ctx.strokeStyle = '#991B1B';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = C.text;
    ctx.font = '8px "Helvetica Neue", Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`T${t.trial}`, px + 9, py + 3);
  }

  drawLegend(ctx, [
    { color: '#DC2626', label: 'Measured (simulation)' },
    { color: C.theory, label: 'Theory: (1−e²)×100% (equal mass)' },
  ], 30);

  return canvas.toDataURL('image/png');
}

// ════════════════════════════════════════════════════════════════════
// Public API
// ════════════════════════════════════════════════════════════════════

export function generateExp7Charts(trials: Exp7Trial[]): Exp7ChartImages {
  return {
    velocityChart: velocityChart(trials),
    momentumChart: momentumChart(trials),
    keChart: keChart(trials),
    keLossChart: keLossChart(trials),
  };
}
