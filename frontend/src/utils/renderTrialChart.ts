/**
 * Renders an angular-velocity-vs-time chart on an offscreen canvas,
 * matching the style of the standard lab report (Figure 5–8).
 *
 * Returns a PNG data-URL string suitable for <Image src={...} /> in @react-pdf/renderer.
 */

interface DataPoint {
  t: number;
  omega: number;
}

interface ChartOptions {
  title: string;
  data: DataPoint[];
  iav: number;
  fav: number;
}

export function renderTrialChart(opts: ChartOptions): string {
  const { title, data, iav, fav } = opts;
  if (data.length < 4) return '';

  const W = 720;
  const H = 440;
  const PAD = { top: 60, right: 40, bottom: 70, left: 75 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);

  const tMin = data[0].t;
  const tMax = data[data.length - 1].t;
  const omegaMax = Math.ceil(Math.max(iav * 1.15, ...data.map(d => d.omega)) / 5) * 5;
  const omegaMin = 0;

  const toX = (t: number) => PAD.left + ((t - tMin) / (tMax - tMin)) * plotW;
  const toY = (o: number) => PAD.top + plotH - ((o - omegaMin) / (omegaMax - omegaMin)) * plotH;

  // --- Grid ---
  ctx.strokeStyle = '#d0d0d0';
  ctx.lineWidth = 0.5;
  const yTicks: number[] = [];
  for (let v = 0; v <= omegaMax; v += 5) yTicks.push(v);
  for (const v of yTicks) {
    const y = toY(v);
    ctx.beginPath();
    ctx.moveTo(PAD.left, y);
    ctx.lineTo(PAD.left + plotW, y);
    ctx.stroke();
  }

  const tRange = tMax - tMin;
  const tStep = tRange > 8 ? 1.0 : tRange > 4 ? 0.5 : 0.2;
  const tTicks: number[] = [];
  for (let t = Math.ceil(tMin / tStep) * tStep; t <= tMax; t += tStep) tTicks.push(+t.toFixed(2));

  // --- Axes ---
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(PAD.left, PAD.top);
  ctx.lineTo(PAD.left, PAD.top + plotH);
  ctx.lineTo(PAD.left + plotW, PAD.top + plotH);
  ctx.stroke();

  // Y-axis labels
  ctx.fillStyle = '#000000';
  ctx.font = '12px Arial';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const v of yTicks) {
    ctx.fillText(v.toString(), PAD.left - 8, toY(v));
  }

  // X-axis labels
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const t of tTicks) {
    const x = toX(t);
    ctx.fillText(t.toFixed(2), x, PAD.top + plotH + 6);
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 0.3;
    ctx.beginPath();
    ctx.moveTo(x, PAD.top);
    ctx.lineTo(x, PAD.top + plotH);
    ctx.stroke();
  }

  // Axis titles
  ctx.fillStyle = '#000000';
  ctx.font = 'bold 13px Arial';
  ctx.textAlign = 'center';
  ctx.fillText('Time (s)', PAD.left + plotW / 2, H - 14);

  ctx.save();
  ctx.translate(16, PAD.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Angular Velocity (rad/s)', 0, 0);
  ctx.restore();

  // Chart title
  ctx.font = 'bold 15px Arial';
  ctx.textAlign = 'center';
  ctx.fillText(title, W / 2, 22);

  // --- Smooth the data (simple moving average) ---
  const windowSize = Math.max(3, Math.floor(data.length / 80));
  const smoothed: DataPoint[] = data.map((d, i) => {
    const start = Math.max(0, i - windowSize);
    const end = Math.min(data.length, i + windowSize + 1);
    let sum = 0;
    for (let j = start; j < end; j++) sum += data[j].omega;
    return { t: d.t, omega: sum / (end - start) };
  });

  // --- Detect collision point (largest single-step drop) ---
  let maxDrop = 0;
  let collisionIdx = -1;
  for (let i = 1; i < smoothed.length; i++) {
    const drop = smoothed[i - 1].omega - smoothed[i].omega;
    if (drop > maxDrop) {
      maxDrop = drop;
      collisionIdx = i;
    }
  }

  // --- Draw the line ---
  ctx.strokeStyle = '#1a5fb4';
  ctx.lineWidth = 2.2;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  for (let i = 0; i < smoothed.length; i++) {
    const x = toX(smoothed[i].t);
    const y = toY(smoothed[i].omega);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // --- Annotate collision point ---
  if (collisionIdx > 0) {
    const before = smoothed[collisionIdx - 1];
    const after = smoothed[Math.min(collisionIdx + Math.floor(windowSize * 2), smoothed.length - 1)];

    const drawAnnotation = (pt: DataPoint, label: string, offsetY: number, align: 'left' | 'right') => {
      const px = toX(pt.t);
      const py = toY(pt.omega);

      // Marker square
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 1.5;
      ctx.fillRect(px - 5, py - 5, 10, 10);
      ctx.strokeRect(px - 5, py - 5, 10, 10);

      // Label box
      ctx.font = 'bold 11px Arial';
      const tw = ctx.measureText(label).width;
      const boxW = tw + 12;
      const boxH = 20;
      const boxX = align === 'right' ? px + 12 : px - boxW - 12;
      const boxY = py + offsetY - boxH / 2;

      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 1;
      ctx.fillRect(boxX, boxY, boxW, boxH);
      ctx.strokeRect(boxX, boxY, boxW, boxH);

      // Line from marker to box
      ctx.beginPath();
      ctx.moveTo(px + (align === 'right' ? 5 : -5), py);
      ctx.lineTo(boxX + (align === 'right' ? 0 : boxW), boxY + boxH / 2);
      ctx.stroke();

      ctx.fillStyle = '#000000';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, boxX + 6, boxY + boxH / 2);
    };

    drawAnnotation(
      before,
      `${before.t.toFixed(2)}s, ${before.omega.toFixed(3)}rad/s`,
      -20,
      'right'
    );
    drawAnnotation(
      after,
      `${after.t.toFixed(2)}s, ${after.omega.toFixed(3)}rad/s`,
      -20,
      'left'
    );
  }

  // --- Legend ---
  const legY = H - 38;
  ctx.strokeStyle = '#1a5fb4';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(W / 2 - 70, legY);
  ctx.lineTo(W / 2 - 40, legY);
  ctx.stroke();
  ctx.fillStyle = '#000000';
  ctx.font = '12px Arial';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('Angular Velocity (rad/s)', W / 2 - 34, legY);

  return canvas.toDataURL('image/png', 0.95);
}
