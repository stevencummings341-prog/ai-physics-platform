import React, { useEffect, useState, useCallback, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowLeft, Activity, Download, FileText } from 'lucide-react';
import { isaacService, type SimulationState } from '../services/isaacService';
import { ConnectionStatus, type TelemetryData, type ExperimentConfig } from '../types';
import WebRTCIsaacViewer from './WebRTCIsaacViewer';
import { SERVER_CONFIG } from '../config';
import { pdf } from '@react-pdf/renderer';
import Exp1ReportPDF from './Exp1ReportPDF';
import Exp7ReportPDF, { type Exp7Trial } from './Exp7ReportPDF';
import Exp2ReportPDF, { type Exp2ReportData } from './Exp2ReportPDF';
import Exp5ReportPDF, { type Exp5ReportData } from './Exp5ReportPDF';
import Exp3ReportPDF, { type Exp3Trial } from './Exp3ReportPDF';
import Exp6ReportPDF, { type Exp6ReportData as Exp6PrettyReportData } from './Exp6ReportPDF';
import Exp4ReportPDF, { type Exp4ReportData as Exp4PrettyReportData } from './Exp4ReportPDF';
import Exp8ReportPDF, { type Exp8ReportData } from './Exp8ReportPDF';
import { generateExp7Charts } from '../utils/exp7Charts';
import { generateExp3Charts } from '../utils/exp3Charts';
import { renderTrialChart } from '../utils/renderTrialChart';

// ═══════════════════════════════════════════════════════════════════════
// Module 1 — Hardcoded Physics Constants (g and cm)
// ═══════════════════════════════════════════════════════════════════════

const PHYS = {
  ring:      { mass: 469.05, rIn: 2.575, rOut: 3.725 },
  lowerDisk: { mass: 121.86, r: 4.670 },
  upperDisk: { mass: 121.23, r: 4.690 },
  pulley:    { mass: 7.02,   r: 2.295 },
} as const;

const IRI =
  0.5 * PHYS.lowerDisk.mass * PHYS.lowerDisk.r ** 2 +
  0.5 * PHYS.pulley.mass * PHYS.pulley.r ** 2;

type DroppedObject = 'Ring' | 'Upper Disk';

function calculateFRI(object: DroppedObject, xCm: number, mass: number): number {
  if (object === 'Ring') {
    return IRI + 0.5 * mass * (PHYS.ring.rIn ** 2 + PHYS.ring.rOut ** 2) + mass * xCm ** 2;
  }
  return IRI + 0.5 * mass * PHYS.upperDisk.r ** 2;
}

// ═══════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════

interface TrialData {
  trial: number;
  object: DroppedObject;
  dropMass: number;
  iav: number;
  fav: number;
  x: number;
  iri: number;
  fri: number;
  iam: number;
  fam: number;
  pctDiff: number;
  initK: number;
  finalK: number;
  energyPct: number;
  chartData?: { t: number; omega: number }[];
}

interface ExperimentViewProps {
  config: ExperimentConfig;
  onBack: () => void;
}

interface ServerReportData {
  summary?: Record<string, number | string>;
  pdf_b64?: string;
  csv_b64?: string;
  period_csv_b64?: string;
  report_md?: string;
  zip_b64?: string;
  files?: Record<string, string>;
  plots?: Record<string, string> | Exp6PrettyReportData['plots'];
  period_rows?: Array<Record<string, number>>;
}

type Exp4ReportData = Exp4PrettyReportData;

function downloadBase64File(b64: string, filename: string, mimeType: string) {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  const blob = new Blob([arr], { type: mimeType });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ═══════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════

const ExperimentView: React.FC<ExperimentViewProps> = ({ config, onBack }) => {
  // ── Connection ──
  const [status, setStatus] = useState<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [simState, setSimState] = useState<SimulationState>({ running: false, paused: false, time: 0, step: 0 });

  // ── Telemetry ──
  const [dataHistory, setDataHistory] = useState<TelemetryData[]>([]);
  const latestData = useRef<TelemetryData | null>(null);

  const isExp1 = config.experimentNumber === '1';
  const isExp3 = config.experimentNumber === '3';
  const isExp5 = config.experimentNumber === '5';
  const isExp6 = config.experimentNumber === '6';
  const isExp7 = config.experimentNumber === '7';
  const isConnected = status === ConnectionStatus.CONNECTED;
  const isReconnecting = status === ConnectionStatus.RECONNECTING || status === ConnectionStatus.CONNECTING;

  // ── Exp1: 4-trial state machine ──
  const [trialNum, setTrialNum] = useState(1);
  const [phase, setPhase] = useState<'idle' | 'spinning' | 'dropped' | 'recorded'>('idle');
  const [omegaI, setOmegaI] = useState(20);
  const [trials, setTrials] = useState<TrialData[]>([]);
  const [currentFAV, setCurrentFAV] = useState(0);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [spinCountdown, setSpinCountdown] = useState(0);
  const [selectedObject, setSelectedObject] = useState<DroppedObject>('Ring');
  const [ringMass, setRingMass] = useState<number>(PHYS.ring.mass);
  const [diskMass, setDiskMass] = useState<number>(PHYS.upperDisk.mass);
  const [massLocked, setMassLocked] = useState(false);
  const allDone = trials.length >= 4;

  const dropMass = selectedObject === 'Ring' ? ringMass : diskMass;

  // ── Exp7: 4-trial state machine ──
  const [exp7Trial, setExp7Trial] = useState(1);
  const [exp7Phase, setExp7Phase] = useState<'idle' | 'running' | 'settled' | 'recorded'>('idle');
  const [exp7Trials, setExp7Trials] = useState<Exp7Trial[]>([]);
  const [exp7M1, setExp7M1] = useState(0.25);
  const [exp7M2, setExp7M2] = useState(0.25);
  const [exp7V1, setExp7V1] = useState(0.40);
  const [exp7V2, setExp7V2] = useState(-0.40);
  const [exp7Rest, setExp7Rest] = useState(1.0);
  const [exp7PostV1, setExp7PostV1] = useState(0);
  const [exp7PostV2, setExp7PostV2] = useState(0);
  const exp7AllDone = exp7Trials.length >= 4;

  // ── Exp3: 5-trial state machine (Ballistic Pendulum) ──
  const EXP3_TARGET_TRIALS = 5;
  const [exp3Trial, setExp3Trial] = useState(1);
  const [exp3Phase, setExp3Phase] = useState<'idle' | 'firing' | 'swinging' | 'settled' | 'recorded'>('idle');
  const [exp3Trials, setExp3Trials] = useState<Exp3Trial[]>([]);
  const [exp3BallMass, setExp3BallMass] = useState(0.0165);
  const [exp3PendMass, setExp3PendMass] = useState(0.1536);
  const [exp3V0, setExp3V0] = useState(5.0);
  const [exp3L, setExp3L] = useState(0.30);
  const [exp3ImpactT, setExp3ImpactT] = useState<number | null>(null);
  const [exp3ApexT, setExp3ApexT] = useState<number | null>(null);
  const [exp3ThetaSeries, setExp3ThetaSeries] = useState<{ t: number; theta: number }[]>([]);
  const [exp3LiveThetaMax, setExp3LiveThetaMax] = useState(0);
  const [exp3LiveV0Meas, setExp3LiveV0Meas] = useState(0);
  const exp3AllDone = exp3Trials.length >= EXP3_TARGET_TRIALS;

  // ── Exp2: report generation state ──
  const isExp2 = config.experimentNumber === '2';
  const [exp2Progress, setExp2Progress] = useState<string>('');
  const [exp2ReportData, setExp2ReportData] = useState<Exp2ReportData | null>(null);

  // ── Exp6: server-side Python report generation state ──
  const [exp5Progress, setExp5Progress] = useState<string>('');
  const [exp5ReportData, setExp5ReportData] = useState<ServerReportData | null>(null);
  const [exp5ExportStartedAt, setExp5ExportStartedAt] = useState<number | null>(null);
  const [exp6Progress, setExp6Progress] = useState<string>('');
  const [exp6ReportData, setExp6ReportData] = useState<ServerReportData | null>(null);

  // ── Exp4: driven-damped lab-report state (Python plots + Markdown + ZIP) ──
  const isExp4 = config.experimentNumber === '4';
  const [exp4Progress, setExp4Progress] = useState<string>('');
  const [exp4ReportData, setExp4ReportData] = useState<Exp4ReportData | null>(null);
  // Timestamp of the last "Generate Lab Report" click. We use it as a
  // watchdog: if the report hasn't arrived after 90 s we re-poll the
  // backend's cached payload (this rescues the case where the WebSocket
  // dropped during the 10–20 s render and the server's first delivery
  // attempt failed with `Cannot write to closing transport`).
  const [exp4RequestedAt, setExp4RequestedAt] = useState<number | null>(null);

  // ── Exp8: resonance-air-column lab report (Python plots + Markdown + ZIP) ──
  const isExp8 = config.experimentNumber === '8';
  const [exp8Progress, setExp8Progress] = useState<string>('');
  const [exp8ReportData, setExp8ReportData] = useState<any>(null);

  // ── VR hand tracking ──
  const [vrConnected, setVrConnected] = useState(false);

  // ── Generic experiment state ──
  const [controlValues, setControlValues] = useState<Record<string, number>>(() => {
    const v: Record<string, number> = {};
    config.controls?.forEach(c => {
      if (c.type === 'slider' && c.defaultValue !== undefined) v[c.id] = c.defaultValue as number;
    });
    return v;
  });

  // ── Connection & telemetry setup ──
  useEffect(() => {
    setIsLoading(true);
    setLoadingProgress(10);
    const init = async () => {
      try {
        if (!isaacService.isConnected()) {
          const ok = await isaacService.connect(config.id);
          if (!ok) { setStatus(ConnectionStatus.ERROR); setErrorMessage('Connection failed'); return; }
        }
        setStatus(ConnectionStatus.CONNECTED);
        setLoadingProgress(40);
        const entered = await isaacService.enterExperiment(config.experimentNumber);
        if (entered) {
          setLoadingProgress(80);
          if (isExp1) {
            isaacService.sendCommand('set_drop_object', 'ring');
            isaacService.sendCommand('set_initial_velocity', 20);
          }
          if (isExp7) {
            isaacService.sendCommand('set_mass1', exp7M1);
            isaacService.sendCommand('set_mass2', exp7M2);
            isaacService.sendCommand('set_velocity1', exp7V1);
            isaacService.sendCommand('set_velocity2', exp7V2);
            isaacService.sendCommand('set_elasticity', exp7Rest);
          }
          if (config.experimentNumber === '8') {
            const c = config.controls;
            const getDef = (id: string) =>
              (c.find(ct => ct.id === id)?.defaultValue as number | undefined);
            const lengthDef = getDef('length');
            const freqDef = getDef('frequency');
            const ampDef = getDef('amplitude');
            const dampDef = getDef('damping');
            if (lengthDef !== undefined) isaacService.sendCommand('set_length', lengthDef);
            if (freqDef !== undefined) isaacService.sendCommand('set_frequency', freqDef);
            if (ampDef !== undefined) isaacService.sendCommand('set_exp8_amplitude', ampDef);
            if (dampDef !== undefined) isaacService.sendCommand('set_exp8_damping', dampDef);
            isaacService.sendCommand('exp8_closed_tube', true);
          }
          setTimeout(() => { isaacService.requestSimulationState(); setLoadingProgress(100); setTimeout(() => setIsLoading(false), 300); }, 500);
        } else { setErrorMessage('Failed to enter experiment.'); }
      } catch { setStatus(ConnectionStatus.ERROR); setErrorMessage('Init error.'); }
    };
    init();

    const unsub1 = isaacService.onTelemetry((data) => {
      latestData.current = data;
      const vrData = (data as any).vr;
      if (vrData && typeof vrData === 'object') {
        setVrConnected(!!vrData.vr_connected);
      }
      const clamped = { ...data };
      for (const k of Object.keys(clamped)) {
        if (typeof clamped[k] === 'number' && k.includes('velocity') && Math.abs(clamped[k]) < 0.01) {
          clamped[k] = 0;
        }
      }
      setDataHistory(prev => {
        const next = [...prev, clamped];
        return next.length > 300 ? next.slice(-300) : next;
      });
      if (isExp7 && (data as any).phase === 'settled') {
        setExp7PostV1((data as any).v1_final ?? (data as any).v1 ?? 0);
        setExp7PostV2((data as any).v2_final ?? (data as any).v2 ?? 0);
        setExp7Phase(prev => prev === 'running' ? 'settled' : prev);
      }
      if (isExp3) {
        const serverPhase = (data as any).phase as string | undefined;
        const simT = typeof (data as any).sim_time === 'number' ? (data as any).sim_time : 0;
        const thetaDeg = typeof (data as any).theta === 'number' ? (data as any).theta : 0;
        const thetaMaxDeg = typeof (data as any).theta_max === 'number' ? (data as any).theta_max : 0;
        const v0Meas = typeof (data as any).v0_measured === 'number' ? (data as any).v0_measured : 0;

        setExp3LiveThetaMax(prev => Math.max(prev, Math.abs(thetaMaxDeg)));
        if (v0Meas > 0) setExp3LiveV0Meas(v0Meas);

        if (serverPhase === 'firing' || serverPhase === 'swinging') {
          if (simT >= 0 && simT < 30) {
            setExp3ThetaSeries(prev => {
              if (prev.length > 0 && simT - prev[prev.length - 1].t < 0.005) return prev;
              const next = [...prev, { t: +simT.toFixed(3), theta: +thetaDeg.toFixed(4) }];
              return next.length > 800 ? next.slice(-800) : next;
            });
          }
        }
        if (serverPhase === 'swinging' && Math.abs(thetaDeg) > 1.5) {
          setExp3ImpactT(prev => prev === null ? simT : prev);
        }
        if (serverPhase === 'settled') {
          setExp3ApexT(prev => prev === null ? simT : prev);
        }
        // Phase sync rules — order matters and the guards are deliberate.
        //
        // BUG WE'RE GUARDING AGAINST (deterministic, alternating):
        //   Trial N: Fire → settled → Record → click "Next Trial".
        //   The frontend handler for Next Trial sets exp3Phase = 'idle'
        //   *immediately*, then sends `exp3_soft_reset`.  But the backend
        //   is still emitting telemetry at ~30 Hz with phase='settled'
        //   from the PREVIOUS trial during the ~50 ms it takes for the
        //   reset message to be processed.  If we let those stale
        //   packets upgrade 'idle' → 'settled', the user sees Fire
        //   disabled and only Record clickable on the next trial.
        //
        // Rule: only advance the phase forward when the frontend is
        // already in a state that EXPECTS that advance.  'idle' and
        // 'recorded' are user-controlled checkpoints — telemetry must
        // never overwrite them.
        if (serverPhase === 'swinging') {
          setExp3Phase(prev => prev === 'firing' ? 'swinging' : prev);
        } else if (serverPhase === 'settled') {
          setExp3Phase(prev => (prev === 'firing' || prev === 'swinging') ? 'settled' : prev);
        }
        // serverPhase === 'firing' is intentionally unhandled: the local
        // exp3HandleFire already sets exp3Phase='firing' before calling
        // start_simulation, so there is no scenario where the server
        // legitimately transitions us into 'firing' while the frontend
        // is still 'idle'.
      }
    });
    const unsub2 = isaacService.onSimulationState(setSimState);
    const unsub3 = isaacService.onCustomMessage((msg: any) => {
      if (msg.type === 'exp2_progress' && msg.data) {
        setExp2Progress(`${msg.data.phase} (${msg.data.current}/${msg.data.total})`);
      } else if (msg.type === 'exp2_report_ready' && msg.data) {
        setExp2ReportData(msg.data);
        setExp2Progress('Report ready!');
      } else if (msg.type === 'exp8_progress' && msg.data) {
        const total = Number(msg.data.total ?? 0);
        const current = Number(msg.data.current ?? 0);
        const suffix = total > 0 ? ` (${current}/${total})` : '';
        setExp8Progress(`${msg.data.phase}${suffix}`);
      } else if (msg.type === 'exp8_report_ready' && msg.data) {
        setExp8ReportData(msg.data);
        setExp8Progress('Report ready!');
      } else if (msg.type === 'exp5_report_progress' && msg.data) {
        const total = Number(msg.data.total ?? 0);
        const current = Number(msg.data.current ?? 0);
        const suffix = total > 0 ? ` (${current}/${total})` : '';
        setExp5Progress(`${msg.data.phase}${suffix}`);
        if (total === 0 || String(msg.data.phase ?? '').toLowerCase().includes('error')) {
          setExp5ExportStartedAt(null);
        }
      } else if (msg.type === 'exp5_report_ready' && msg.data) {
        const data = msg.data as ServerReportData;
        setExp5ReportData(data);
        setExp5Progress('Rendering PDF in your browser...');
        setExp5ExportStartedAt(null);
        // Render the formal PHY1002 lab report PDF in the browser using
        // @react-pdf/renderer (same toolchain as Exp1) so the layout
        // exactly matches Lab Report 1. The server only provides the
        // summary data and matplotlib PNG figures embedded as base64.
        if (data.summary && data.plots) {
          (async () => {
            try {
              const blob = await pdf(
                <Exp5ReportPDF
                  data={{
                    summary: data.summary as unknown as Exp5ReportData['summary'],
                    period_rows: (data.period_rows ?? []) as unknown as Exp5ReportData['period_rows'],
                    plots: data.plots as unknown as Exp5ReportData['plots'],
                  }}
                />,
              ).toBlob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'Lab_Report_Rotational_Inertia_Physical_Pendulum.pdf';
              a.click();
              URL.revokeObjectURL(url);
              setExp5Progress('Report ready!');
            } catch (err) {
              console.error('Exp5 PDF render failed', err);
              setExp5Progress(`Report ready, but PDF rendering failed: ${(err as Error).message ?? 'unknown error'}. Use Markdown or ZIP downloads below.`);
            }
          })();
        } else {
          setExp5Progress('Report ready!');
        }
      } else if (msg.type === 'exp6_report_progress' && msg.data) {
        const total = Number(msg.data.total ?? 0);
        const current = Number(msg.data.current ?? 0);
        const suffix = total > 0 ? ` (${current}/${total})` : '';
        setExp6Progress(`${msg.data.phase}${suffix}`);
      } else if (msg.type === 'exp6_report_ready' && msg.data) {
        const data = msg.data as ServerReportData;
        setExp6ReportData(data);
        setExp6Progress('Report ready!');
        (async () => {
          const blob = await pdf(<Exp6ReportPDF data={data as Exp6PrettyReportData} />).toBlob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'Lab_Report_Centripetal_Force.pdf';
          a.click();
          URL.revokeObjectURL(url);
        })().catch((err) => {
          console.error('Failed to render styled Exp6 PDF; falling back to backend PDF.', err);
          if (data.pdf_b64) {
            downloadBase64File(
              data.pdf_b64,
              data.files?.pdf || 'Lab_Report_Centripetal_Force_backend.pdf',
              'application/pdf',
            );
          }
        });
      } else if (msg.type === 'exp4_progress' && msg.data) {
        const total = Number(msg.data.total ?? 0);
        const current = Number(msg.data.current ?? 0);
        const suffix = total > 0 ? ` (${current}/${total})` : '';
        setExp4Progress(`${msg.data.phase}${suffix}`);
      } else if (msg.type === 'exp4_report_ready' && msg.data) {
        setExp4ReportData(msg.data as Exp4ReportData);
        setExp4Progress('Report ready!');
        setExp4RequestedAt(null);
      }
    });
    const poll = setInterval(() => { if (isaacService.isConnected()) isaacService.requestSimulationState(); }, 3000);

    // Live status subscription so the UI badge reflects RECONNECTING and we
    // re-apply per-experiment parameter defaults after the socket comes back.
    let lastStatus: ConnectionStatus = isaacService.getStatus();
    const unsub4 = isaacService.onStatusChange((s) => {
      setStatus(s);
      const wasDown = lastStatus !== ConnectionStatus.CONNECTED;
      lastStatus = s;
      if (s === ConnectionStatus.CONNECTED && wasDown) {
        // Reconnected after a drop — re-issue experiment defaults so the
        // backend doesn't drift out of sync with the UI sliders.
        try {
          isaacService.enterExperiment(config.experimentNumber);
          if (config.experimentNumber === '1') {
            isaacService.sendCommand('set_drop_object', 'ring');
          }
          if (config.experimentNumber === '7') {
            isaacService.sendCommand('set_mass1', exp7M1);
            isaacService.sendCommand('set_mass2', exp7M2);
            isaacService.sendCommand('set_velocity1', exp7V1);
            isaacService.sendCommand('set_velocity2', exp7V2);
            isaacService.sendCommand('set_elasticity', exp7Rest);
          }
          // Re-apply current slider values for any experiment.
          Object.entries(controlValues).forEach(([id, value]) => {
            const ctl = config.controls?.find(c => c.id === id);
            const cmd = (ctl as any)?.command;
            if (cmd) isaacService.sendCommand(cmd, value);
          });
          // If we were waiting on an Exp 4 report when the socket dropped,
          // ask the server for the cached payload now that we're back.
          // The backend caches the most recent rendered report on
          // self._exp4_report_cache and replies with `exp4_report_ready`
          // (or an `exp4_progress` status frame).
          if (config.experimentNumber === '4') {
            isaacService.sendCommand('fetch_exp4_report', true);
          }
        } catch (e) {
          console.warn('post-reconnect resync failed', e);
        }
      }
    });

    return () => { unsub1(); unsub2(); unsub3(); unsub4(); clearInterval(poll); };
  }, [config.id, config.experimentNumber]);

  useEffect(() => {
    if (!isExp5 || exp5ExportStartedAt === null || exp5ReportData) return;
    const timer = window.setTimeout(() => {
      setExp5Progress(
        'No response from backend. Restart services with ./launch.sh --all so Isaac Sim reloads the latest report code, then run the pendulum again.',
      );
      setExp5ExportStartedAt(null);
    }, 30000);
    return () => window.clearTimeout(timer);
  }, [isExp5, exp5ExportStartedAt, exp5ReportData]);

  // Exp 4 report watchdog: if we've been waiting > 25 s and still no payload
  // arrived, re-request the cached version from the server. The backend
  // caches every rendered report on self._exp4_report_cache, so this rescues
  // the case where the original WebSocket transport closed during the
  // synchronous CPU-bound render (≈10-20 s) and the first delivery failed
  // silently with `Cannot write to closing transport` server-side.
  useEffect(() => {
    if (!isExp4 || exp4RequestedAt === null || exp4ReportData) return;
    const tick = window.setInterval(() => {
      if (isaacService.isConnected()) {
        isaacService.sendCommand('fetch_exp4_report', true);
      }
    }, 8000);
    const giveUp = window.setTimeout(() => {
      setExp4Progress(prev => prev || 'No response from backend after 2 minutes — please retry.');
    }, 120_000);
    return () => { window.clearInterval(tick); window.clearTimeout(giveUp); };
  }, [isExp4, exp4RequestedAt, exp4ReportData]);

  // ── Spin countdown ──
  useEffect(() => {
    if (phase !== 'spinning') { setSpinCountdown(0); return; }
    setSpinCountdown(3);
    const iv = setInterval(() => setSpinCountdown(p => (p <= 1 ? (clearInterval(iv), 0) : p - 1)), 1000);
    return () => clearInterval(iv);
  }, [phase]);

  // ═══════════════════════════════════════════════════════════════════
  // Module 2 — 4-Trial State Machine Actions
  // ═══════════════════════════════════════════════════════════════════

  const handleSpin = useCallback(() => {
    if (!massLocked) setMassLocked(true);
    const serverObj = selectedObject === 'Ring' ? 'ring' : 'disk';
    isaacService.sendCommand('set_initial_velocity', omegaI);
    isaacService.sendCommand('set_drop_object', serverObj);
    isaacService.sendCommand('spin_disk', {});
    setPhase('spinning');
    setDataHistory([]);
  }, [omegaI, selectedObject, massLocked]);

  const handleDrop = useCallback(() => {
    const x = selectedObject === 'Ring'
      ? +(0.20 + Math.random() * 0.10).toFixed(4)
      : 0;
    setCurrentOffset(x);

    const fri = calculateFRI(selectedObject, x, dropMass);
    const theoreticalFAV = IRI * omegaI / fri;
    const frictionLoss = 0.01 + Math.random() * 0.02;
    const fav = +(theoreticalFAV * (1 - frictionLoss)).toFixed(4);
    setCurrentFAV(fav);

    isaacService.sendCommand('drop_object', {});
    setPhase('dropped');
  }, [selectedObject, omegaI, dropMass]);

  const handleRecord = useCallback(() => {
    const fri = calculateFRI(selectedObject, currentOffset, dropMass);
    const iam = IRI * omegaI;
    const fam = fri * currentFAV;
    const pctDiff = ((fam - iam) / iam) * 100;
    const initK = 0.5 * IRI * omegaI * omegaI;
    const finalK = 0.5 * fri * currentFAV * currentFAV;
    const energyPct = ((finalK - initK) / initK) * 100;

    const t0 = dataHistory.length > 0 ? (dataHistory[0].timestamp ?? 0) : 0;
    const chartSnapshot = dataHistory
      .filter(d => d.disk_angular_velocity !== undefined)
      .map(d => ({
        t: +((((d.timestamp ?? 0) - t0) / 1000)).toFixed(3),
        omega: +(Math.abs(d.disk_angular_velocity as number)).toFixed(4),
      }));

    setTrials(prev => [...prev, {
      trial: trialNum,
      object: selectedObject,
      dropMass,
      iav: omegaI, fav: currentFAV, x: currentOffset,
      iri: IRI, fri, iam, fam, pctDiff,
      initK, finalK, energyPct,
      chartData: chartSnapshot,
    }]);
    setPhase('recorded');
  }, [trialNum, omegaI, currentFAV, currentOffset, selectedObject, dropMass, dataHistory]);

  const handleNextTrial = useCallback(() => {
    isaacService.sendCommand('reset', {});
    setTrialNum(prev => Math.min(prev + 1, 4));
    setPhase('idle');
    setCurrentFAV(0);
    setCurrentOffset(0);
    setDataHistory([]);
  }, []);

  // ═══════════════════════════════════════════════════════════════════
  // Module 2b — Exp7 4-Trial State Machine Actions
  // ═══════════════════════════════════════════════════════════════════

  const exp7HandleRun = useCallback(() => {
    isaacService.sendCommand('set_mass1', exp7M1);
    isaacService.sendCommand('set_mass2', exp7M2);
    isaacService.sendCommand('set_velocity1', exp7V1);
    isaacService.sendCommand('set_velocity2', exp7V2);
    isaacService.sendCommand('set_elasticity', exp7Rest);
    isaacService.startSimulation();
    setExp7Phase('running');
    setDataHistory([]);
  }, [exp7M1, exp7M2, exp7V1, exp7V2, exp7Rest]);

  const exp7HandleRecord = useCallback(() => {
    const pBefore = exp7M1 * exp7V1 + exp7M2 * exp7V2;
    const pAfter = exp7M1 * exp7PostV1 + exp7M2 * exp7PostV2;
    const keBefore = 0.5 * exp7M1 * exp7V1 * exp7V1 + 0.5 * exp7M2 * exp7V2 * exp7V2;
    const keAfter = 0.5 * exp7M1 * exp7PostV1 * exp7PostV1 + 0.5 * exp7M2 * exp7PostV2 * exp7PostV2;
    const pPctDiff = pBefore !== 0 ? ((pAfter - pBefore) / Math.abs(pBefore)) * 100 : 0;
    const keLossPct = keBefore > 0 ? ((keBefore - keAfter) / keBefore) * 100 : 0;
    const collisionType = keLossPct < 5 ? 'elastic' : 'inelastic';

    setExp7Trials(prev => [...prev, {
      trial: exp7Trial,
      m1: exp7M1, m2: exp7M2,
      v1i: exp7V1, v2i: exp7V2,
      restitution: exp7Rest,
      v1f: exp7PostV1, v2f: exp7PostV2,
      pBefore, pAfter, pPctDiff,
      keBefore, keAfter, keLossPct,
      collisionType,
    }]);
    setExp7Phase('recorded');
  }, [exp7Trial, exp7M1, exp7M2, exp7V1, exp7V2, exp7Rest, exp7PostV1, exp7PostV2]);

  const exp7HandleNext = useCallback(() => {
    isaacService.sendCommand('reset', {});
    setExp7Trial(prev => Math.min(prev + 1, 4));
    setExp7Phase('idle');
    setExp7PostV1(0);
    setExp7PostV2(0);
    setDataHistory([]);
  }, []);

  const exp7ExportCSV = useCallback(() => {
    if (exp7Trials.length === 0) return;
    const hdr = 'Trial,m1(kg),m2(kg),v1_i(m/s),v2_i(m/s),Restitution,v1_f(m/s),v2_f(m/s),p_before,p_after,%diff,KE_before,KE_after,KE_loss%,Type';
    const rows = exp7Trials.map(t =>
      [t.trial, t.m1.toFixed(2), t.m2.toFixed(2), t.v1i.toFixed(3), t.v2i.toFixed(3),
       t.restitution.toFixed(2), t.v1f.toFixed(3), t.v2f.toFixed(3),
       t.pBefore.toFixed(4), t.pAfter.toFixed(4), t.pPctDiff.toFixed(2),
       t.keBefore.toFixed(4), t.keAfter.toFixed(4), t.keLossPct.toFixed(2), t.collisionType
      ].join(',')
    );
    const blob = new Blob([[hdr, ...rows].join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `momentum_conservation_trials_${Date.now()}.csv`;
    a.click();
  }, [exp7Trials]);

  const exp7GeneratePDF = useCallback(async () => {
    if (exp7Trials.length === 0) { alert('Complete at least one trial first.'); return; }
    const charts = generateExp7Charts(exp7Trials);
    const blob = await pdf(<Exp7ReportPDF trials={exp7Trials} charts={charts} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Conservation_of_Momentum.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp7Trials]);

  // ═══════════════════════════════════════════════════════════════════
  // Module 2c — Exp3 5-Trial State Machine Actions (Ballistic Pendulum)
  // ═══════════════════════════════════════════════════════════════════

  const exp3HandleFire = useCallback(() => {
    isaacService.sendCommand('set_ball_mass', exp3BallMass);
    isaacService.sendCommand('set_pend_mass', exp3PendMass);
    isaacService.sendCommand('set_exp3_v0', exp3V0);
    isaacService.sendCommand('set_exp3_L', exp3L);
    setExp3ThetaSeries([]);
    setExp3ImpactT(null);
    setExp3ApexT(null);
    setExp3LiveThetaMax(0);
    setExp3LiveV0Meas(0);
    setDataHistory([]);
    setExp3Phase('firing');
    // Small delay so server applies parameter updates before play begins.
    setTimeout(() => isaacService.startSimulation(), 80);
  }, [exp3BallMass, exp3PendMass, exp3V0, exp3L]);

  const exp3HandleRecord = useCallback(() => {
    const latest = latestData.current as any;
    const G = 9.80665;
    const ball_mass = exp3BallMass;
    const pend_mass = exp3PendMass;
    const M = ball_mass + pend_mass;
    const L = exp3L;

    // Prefer fresh server values; fall back to live tracker.
    const theta_max_deg = typeof latest?.theta_max === 'number' && latest.theta_max > 0
      ? latest.theta_max : exp3LiveThetaMax;
    const v_after_ideal = (ball_mass * exp3V0) / (M > 1e-9 ? M : 1);
    const theta_max_rad = (theta_max_deg * Math.PI) / 180;
    const h_max = L * (1 - Math.cos(theta_max_rad));
    const v0_measured = ball_mass > 1e-9
      ? (M / ball_mass) * Math.sqrt(2 * G * Math.max(h_max, 0))
      : 0;
    const v0_error_pct = exp3V0 > 1e-9 ? ((v0_measured - exp3V0) / exp3V0) * 100 : 0;
    const ke_input = 0.5 * ball_mass * exp3V0 * exp3V0;
    const ke_after_ideal = 0.5 * M * v_after_ideal * v_after_ideal;
    const ke_loss_percent = ke_input > 1e-12 ? ((ke_input - ke_after_ideal) / ke_input) * 100 : 0;

    const trial: Exp3Trial = {
      trial: exp3Trial,
      ball_mass, pend_mass, L,
      v0_input: exp3V0,
      theta_max_deg: +theta_max_deg.toFixed(4),
      h_max: +h_max.toFixed(6),
      v_after_ideal: +v_after_ideal.toFixed(6),
      v0_measured: +v0_measured.toFixed(4),
      v0_error_pct: +v0_error_pct.toFixed(3),
      ke_input: +ke_input.toFixed(6),
      ke_after_ideal: +ke_after_ideal.toFixed(6),
      ke_loss_percent: +ke_loss_percent.toFixed(3),
      apex_time: exp3ApexT ?? undefined,
      impact_time: exp3ImpactT ?? undefined,
      thetaSeries: exp3ThetaSeries.slice(),
    };

    setExp3Trials(prev => [...prev, trial]);
    setExp3Phase('recorded');
  }, [exp3Trial, exp3BallMass, exp3PendMass, exp3V0, exp3L,
      exp3LiveThetaMax, exp3ApexT, exp3ImpactT, exp3ThetaSeries]);

  const exp3HandleNext = useCallback(() => {
    // Use the lightweight `exp3_soft_reset` instead of the global `reset`.
    // The global path stops the timeline four times in rapid succession
    // (each call briefly tears down Hydra), which starves the WebRTC ICE
    // keepalive and causes the browser to flag the video as disconnected.
    // The next `Fire` performs its own full reset (stop + pose + play)
    // anyway, so we only need to clear UI / measurement state here.
    isaacService.sendCommand('exp3_soft_reset', {});
    setExp3Trial(prev => Math.min(prev + 1, EXP3_TARGET_TRIALS));
    setExp3Phase('idle');
    setExp3ThetaSeries([]);
    setExp3ImpactT(null);
    setExp3ApexT(null);
    setExp3LiveThetaMax(0);
    setExp3LiveV0Meas(0);
    setDataHistory([]);
  }, []);

  const exp3ExportCSV = useCallback(() => {
    if (exp3Trials.length === 0) return;
    const hdr = 'Trial,m_ball(kg),m_pend(kg),L(m),v0_set(m/s),theta_max(deg),h_max(m),v_after(m/s),v0_measured(m/s),%diff,KE_in(J),KE_after(J),KE_loss(%),t_impact(s),t_apex(s)';
    const rows = exp3Trials.map(t =>
      [t.trial,
       t.ball_mass.toFixed(4), t.pend_mass.toFixed(4), t.L.toFixed(3), t.v0_input.toFixed(3),
       t.theta_max_deg.toFixed(3), t.h_max.toFixed(5),
       t.v_after_ideal.toFixed(4), t.v0_measured.toFixed(4),
       t.v0_error_pct.toFixed(3),
       t.ke_input.toFixed(5), t.ke_after_ideal.toFixed(5), t.ke_loss_percent.toFixed(3),
       (t.impact_time ?? '').toString(), (t.apex_time ?? '').toString()
      ].join(',')
    );
    const blob = new Blob([[hdr, ...rows].join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ballistic_pendulum_trials_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [exp3Trials]);

  const exp3GeneratePDF = useCallback(async () => {
    if (exp3Trials.length === 0) {
      alert('Complete at least one trial before exporting the report.');
      return;
    }
    const charts = generateExp3Charts(exp3Trials);
    const blob = await pdf(<Exp3ReportPDF trials={exp3Trials} charts={charts} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Ballistic_Pendulum.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp3Trials]);

  // ═══════════════════════════════════════════════════════════════════
  // Module 3 — CSV Export
  // ═══════════════════════════════════════════════════════════════════

  const exportCSV = useCallback(() => {
    if (trials.length === 0) return;
    const hdr = 'Trial,Object,IAV(rad/s),FAV(rad/s),x(cm),IRI(g*cm2),FRI(g*cm2),IAM(g*cm2/s),FAM(g*cm2/s),%diff,InitK(g*cm2/s2),FinalK(g*cm2/s2),Energy%';
    const rows = trials.map(t =>
      [t.trial, t.object, t.iav.toFixed(2), t.fav.toFixed(4), t.x.toFixed(4),
       t.iri.toFixed(2), t.fri.toFixed(2), t.iam.toFixed(2), t.fam.toFixed(2),
       t.pctDiff.toFixed(2), t.initK.toFixed(2), t.finalK.toFixed(2), t.energyPct.toFixed(2)
      ].join(',')
    );
    const blob = new Blob([[hdr, ...rows].join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `angular_momentum_trials_${Date.now()}.csv`;
    a.click();
  }, [trials]);

  // ═══════════════════════════════════════════════════════════════════
  // Module 3 — PDF Generation (@react-pdf/renderer)
  // ═══════════════════════════════════════════════════════════════════

  const generatePDF = useCallback(async () => {
    if (trials.length === 0) { alert('Complete at least one trial first.'); return; }

    const chartImages: string[] = trials.map(t => {
      if (!t.chartData || t.chartData.length < 4) return '';
      const objLabel = t.object === 'Ring' ? 'Ring' : 'Disk';
      const runLabel = t.object === 'Ring' ? ` (Run ${t.trial})` : '';
      return renderTrialChart({
        title: `Angular Speed Change After ${objLabel} Collision${runLabel}`,
        data: t.chartData,
        iav: t.iav,
        fav: t.fav,
      });
    });

    const blob = await pdf(
      <Exp1ReportPDF phys={PHYS} iri={IRI} trials={trials} chartImages={chartImages} />
    ).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Angular_Momentum.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [trials]);

  const exp2GeneratePDF = useCallback(async () => {
    if (!exp2ReportData) {
      alert('Run "Generate Full Report" first, then export the PDF after the report data is ready.');
      return;
    }

    const blob = await pdf(<Exp2ReportPDF data={exp2ReportData} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Large_Amplitude_Pendulum.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp2ReportData]);

  const exp6GeneratePrettyPDF = useCallback(async () => {
    if (!exp6ReportData) {
      alert('Run "Export Lab Report (PDF)" first, then download the report after it is ready.');
      return;
    }
    const blob = await pdf(<Exp6ReportPDF data={exp6ReportData as Exp6PrettyReportData} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Centripetal_Force.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp6ReportData]);

  const exp4GeneratePrettyPDF = useCallback(async () => {
    if (!exp4ReportData) {
      alert('Click "Generate Lab Report" first, then download the PDF after the report data is ready.');
      return;
    }
    const blob = await pdf(<Exp4ReportPDF data={exp4ReportData as Exp4PrettyReportData} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Driven_Damped_Oscillator.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp4ReportData]);

  const exp8GeneratePDF = useCallback(async () => {
    if (!exp8ReportData) {
      alert('Click "Generate Full Report" first, then download the PDF after the report data is ready.');
      return;
    }
    const blob = await pdf(<Exp8ReportPDF data={exp8ReportData as Exp8ReportData} />).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Resonance_Air_Column.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [exp8ReportData]);

  // ═══════════════════════════════════════════════════════════════════
  // Generic experiment handler (non-exp1)
  // ═══════════════════════════════════════════════════════════════════

  const handleGenericControl = useCallback((controlId: string, value: number | boolean | string) => {
    if (typeof value === 'number') setControlValues(prev => ({ ...prev, [controlId]: value }));
    const control = config.controls.find(c => c.id === controlId);
    if (!control) return;
    if (control.command === 'start_simulation') {
      setDataHistory([]);
      isaacService.startSimulation();
    } else if (control.command === 'reset_env' || control.command === 'reset') {
      isaacService.sendCommand('reset', {});
      if (isExp4) {
        setExp4Progress('');
        setExp4ReportData(null);
        setExp4RequestedAt(null);
      }
      if (isExp5) {
        setExp5Progress('');
        setExp5ReportData(null);
        setExp5ExportStartedAt(null);
      }
      if (isExp6) {
        setExp6Progress('');
        setExp6ReportData(null);
      }
      if (isExp8) {
        setExp8Progress('');
        setExp8ReportData(null);
      }
    } else if (control.command === 'run_exp2_full_experiment') {
      setExp2ReportData(null);
      setExp2Progress('Starting report generation...');
      isaacService.sendCommand(control.command, value);
    } else if (control.command === 'run_exp8_full_experiment') {
      setExp8ReportData(null);
      setExp8Progress('Starting Python report pipeline (~2 min)...');
      isaacService.sendCommand(control.command, true);
    } else if (control.command === 'run_exp4_full_experiment') {
      setExp4ReportData(null);
      setExp4Progress('Starting Python report pipeline...');
      setExp4RequestedAt(Date.now());
      isaacService.sendCommand(control.command, true);
    } else if (control.command === 'export_exp5_report' || control.command === 'run_exp5_report') {
      setExp5ReportData(null);
      setExp5Progress('Starting Python report generation...');
      setExp5ExportStartedAt(Date.now());
      isaacService.sendCommand(control.command, true);
    } else if (control.command === 'export_exp6_report') {
      setExp6ReportData(null);
      setExp6Progress('Starting Python report generation...');
      isaacService.sendCommand(control.command, true);
    } else {
      isaacService.sendCommand(control.command, value);
    }
  }, [config.controls, isExp4, isExp5, isExp6]);

  // ═══════════════════════════════════════════════════════════════════
  // Loading screen
  // ═══════════════════════════════════════════════════════════════════

  if (isLoading) {
    return (
      <div className="h-screen w-full bg-gradient-to-br from-white via-blue-50/30 to-purple-50/30 text-gray-900 flex flex-col items-center justify-center font-sans">
        <button onClick={onBack} className="absolute top-6 left-6 text-gray-600 hover:text-blue-600 flex items-center gap-2 text-sm font-mono border-2 border-gray-200 px-3 py-1.5 rounded-lg">
          <ArrowLeft size={14} /> BACK
        </button>
        <div className="flex flex-col items-center gap-6">
          <div className="p-6 bg-white/80 rounded-2xl border-2 border-gray-200 shadow-lg">
            <Activity size={48} className="text-blue-600 animate-pulse" />
          </div>
          <h2 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-gray-700 via-blue-600 to-purple-600">
            {config.title}
          </h2>
          {!errorMessage && (
            <div className="w-80">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-500" style={{ width: `${loadingProgress}%` }} />
              </div>
            </div>
          )}
          {errorMessage && (
            <div className="w-96 space-y-3">
              <div className="p-4 bg-red-50 border-2 border-red-200 rounded-xl text-sm text-red-700 font-mono text-center">{errorMessage}</div>
              <button onClick={() => window.location.reload()} className="w-full px-4 py-2 bg-blue-600 text-white text-sm font-mono rounded-lg">Retry</button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Experiment 1: Angular Momentum — specialised layout
  // ═══════════════════════════════════════════════════════════════════

  if (isExp1) {
    return (
      <div className="h-screen w-full bg-gray-50 text-gray-900 flex flex-col font-sans overflow-hidden">
        {/* ── Top Bar ── */}
        <div className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white/90 backdrop-blur-sm z-20 shadow-sm shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="text-gray-700 hover:text-blue-600 flex items-center gap-1.5 text-xs font-mono border border-gray-300 px-2.5 py-1 rounded-lg">
              <ArrowLeft size={12} /> BACK
            </button>
            <div className="h-5 w-px bg-gray-300" />
            <span className="font-bold text-xs tracking-widest text-blue-600 uppercase">{config.title}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded-lg border">
              Trial {Math.min(trialNum, 4)} / 4
            </span>
            <button onClick={exportCSV} disabled={trials.length === 0}
              className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-mono rounded-lg flex items-center gap-1 border border-gray-300 disabled:opacity-40">
              <Download size={11} /> CSV
            </button>
            <button onClick={generatePDF} disabled={trials.length === 0}
              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-mono rounded-lg flex items-center gap-1 disabled:opacity-40">
              <FileText size={11} /> PDF Report
            </button>
            <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : isReconnecting ? 'border-yellow-400 text-yellow-700 bg-yellow-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : isReconnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'LIVE' : isReconnecting ? 'REC...' : 'OFF'}
            </div>
            {vrConnected && (
              <div className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border border-purple-400 text-purple-700 bg-purple-50">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                VR
              </div>
            )}
          </div>
        </div>

        {/* ── Main Content ── */}
        <div className="flex-1 flex overflow-hidden">

          {/* ── Left Panel (Module 1) ── */}
          <div className="w-[280px] bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">

            {/* Physical Constants */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Physical Constants</div>
              <table className="w-full text-[10px] font-mono border-collapse">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-1.5 py-1 text-left text-gray-600">Object</th>
                    <th className="border border-gray-200 px-1.5 py-1 text-right text-gray-600">Mass (g)</th>
                    <th className="border border-gray-200 px-1.5 py-1 text-right text-gray-600">R (cm)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="border border-gray-200 px-1.5 py-1">Ring</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.ring.mass}</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right text-[9px]">
                      {PHYS.ring.rIn} / {PHYS.ring.rOut}
                    </td>
                  </tr>
                  <tr className="bg-gray-50/50">
                    <td className="border border-gray-200 px-1.5 py-1">Lower Disk</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.lowerDisk.mass}</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.lowerDisk.r}</td>
                  </tr>
                  <tr>
                    <td className="border border-gray-200 px-1.5 py-1">Upper Disk</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.upperDisk.mass}</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.upperDisk.r}</td>
                  </tr>
                  <tr className="bg-gray-50/50">
                    <td className="border border-gray-200 px-1.5 py-1">Pulley</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.pulley.mass}</td>
                    <td className="border border-gray-200 px-1.5 py-1 text-right">{PHYS.pulley.r}</td>
                  </tr>
                </tbody>
              </table>
              <div className="mt-2 px-2 py-1.5 bg-blue-50 border border-blue-200 rounded text-[9px] font-mono text-blue-700">
                IRI = {IRI.toFixed(2)} g&middot;cm&sup2;
              </div>
            </div>

            {/* Angular Velocity Control */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                Initial Angular Velocity
              </div>
              <div className="flex items-center gap-2 mb-1.5">
                <input
                  type="range" min={15} max={30} step={0.5} value={omegaI}
                  onChange={e => setOmegaI(parseFloat(e.target.value))}
                  disabled={phase !== 'idle'}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 disabled:opacity-50"
                />
                <input
                  type="number" min={15} max={30} step={0.5} value={omegaI}
                  onChange={e => { const v = parseFloat(e.target.value); if (v >= 15 && v <= 30) setOmegaI(v); }}
                  disabled={phase !== 'idle'}
                  className="w-16 text-center text-sm font-mono font-bold border border-gray-300 rounded-lg py-1 disabled:opacity-50 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="text-[9px] text-gray-400 font-mono text-center">
                Range: 15 &ndash; 30 rad/s
              </div>
            </div>

            {/* Dropped Object Selector */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                Dropped Object
              </div>
              <select
                value={selectedObject}
                onChange={e => setSelectedObject(e.target.value as DroppedObject)}
                disabled={phase !== 'idle'}
                className="w-full px-2 py-1.5 text-sm font-mono font-bold border border-gray-300 rounded-lg bg-white disabled:opacity-50 focus:border-blue-500 focus:outline-none"
              >
                <option value="Ring">Ring</option>
                <option value="Upper Disk">Upper Disk</option>
              </select>
              <div className="text-[9px] text-gray-400 font-mono mt-1">
                Ring: x = random offset &middot; Upper Disk: x = 0
              </div>
            </div>

            {/* Mass Sliders (locked after first trial) */}
            <div className={`p-3 border-b border-gray-200 ${massLocked ? 'opacity-60' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Object Masses</div>
                {massLocked && <span className="text-[8px] font-mono text-red-500 bg-red-50 px-1.5 py-0.5 rounded border border-red-200">LOCKED</span>}
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Ring Mass</span>
                    <span className="font-bold text-blue-600">{ringMass.toFixed(1)} g</span>
                  </div>
                  <input type="range" min={100} max={1000} step={0.5} value={ringMass}
                    onChange={e => setRingMass(parseFloat(e.target.value))}
                    disabled={massLocked}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 disabled:cursor-not-allowed" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Upper Disk Mass</span>
                    <span className="font-bold text-purple-600">{diskMass.toFixed(1)} g</span>
                  </div>
                  <input type="range" min={50} max={500} step={0.5} value={diskMass}
                    onChange={e => setDiskMass(parseFloat(e.target.value))}
                    disabled={massLocked}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600 disabled:cursor-not-allowed" />
                </div>
              </div>
              {!massLocked && <div className="text-[8px] text-amber-600 font-mono mt-1.5">Masses lock after first Spin</div>}
            </div>

            {/* Current Trial Info */}
            <div className="p-3 border-b border-gray-200 bg-gradient-to-b from-indigo-50/50 to-white">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                Current Trial
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                <InfoCard label="Trial" value={`${Math.min(trialNum, 4)} / 4`} accent="blue" />
                <InfoCard label="Object" value={selectedObject} accent={selectedObject === 'Ring' ? 'purple' : 'amber'} />
                <InfoCard label="Phase" value={phase.toUpperCase()} accent="green" />
                <InfoCard label="IRI" value={`${IRI.toFixed(1)}`} accent="gray" />
                {phase === 'dropped' && (
                  <>
                    <InfoCard label="FAV" value={currentFAV.toFixed(4)} accent="cyan" />
                    <InfoCard label="Offset x" value={`${currentOffset.toFixed(4)} cm`} accent="red" />
                  </>
                )}
              </div>
            </div>

            {/* Live Chart */}
            <div className="flex-1 p-2 flex flex-col min-h-[160px]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1 flex items-center gap-1">
                <Activity size={10} /> Angular Velocity
              </div>
              <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis stroke="#6b7280" fontSize={9} tickFormatter={v => v.toFixed(1)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', fontSize: '10px', borderRadius: '6px' }}
                      labelStyle={{ display: 'none' }}
                      formatter={(v: number) => v.toFixed(4)}
                    />
                    <Line type="monotone" dataKey="disk_angular_velocity" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Disk ω" />
                    <Line type="monotone" dataKey="ring_angular_velocity" stroke="#10b981" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Object ω" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── Center: Viewport + Bottom Panel ── */}
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* WebRTC Viewport */}
            <div className="flex-1 relative bg-gray-900 min-h-0">
              <div className="absolute inset-0">
                <WebRTCIsaacViewer serverUrl={SERVER_CONFIG.httpUrl} usdPath={config.usdPath} className="w-full h-full" />
              </div>
            </div>

            {/* ── Bottom Panel (Module 2) ── */}
            <div className="h-auto max-h-[45%] bg-white border-t-2 border-gray-200 flex flex-col shrink-0">

              {/* Action Bar */}
              <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
                {/* Step Indicators */}
                <div className="flex items-center gap-1">
                  {(['idle', 'spinning', 'dropped', 'recorded'] as const).map((step, i) => (
                    <React.Fragment key={step}>
                      {i > 0 && <div className={`w-4 h-0.5 rounded ${
                        (['idle', 'spinning', 'dropped', 'recorded'].indexOf(phase) >= i) ? 'bg-blue-500' : 'bg-gray-300'
                      }`} />}
                      <div className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold ${
                        phase === step ? 'bg-blue-600 text-white' :
                        (['idle', 'spinning', 'dropped', 'recorded'].indexOf(phase) > i) ? 'bg-blue-100 text-blue-600' :
                        'bg-gray-200 text-gray-400'
                      }`}>
                        {step === 'idle' ? 'Setup' : step === 'spinning' ? 'Spinning' : step === 'dropped' ? 'Dropped' : 'Recorded'}
                      </div>
                    </React.Fragment>
                  ))}
                </div>

                <div className="h-5 w-px bg-gray-300" />

                <span className="text-[10px] font-mono text-gray-600">
                  Object: <span className="font-bold text-gray-900">{selectedObject}</span>
                </span>

                {phase === 'spinning' && spinCountdown > 0 && (
                  <span className="text-[10px] font-mono text-amber-600 animate-pulse">
                    Wait {spinCountdown}s...
                  </span>
                )}

                <div className="flex-1" />

                {/* Action Buttons */}
                <button onClick={handleSpin} disabled={phase !== 'idle' || allDone}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  1. Spin
                </button>
                <button onClick={handleDrop} disabled={phase !== 'spinning' || spinCountdown > 0}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  2. Drop
                </button>
                <button onClick={handleRecord} disabled={phase !== 'dropped'}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  3. Record
                </button>
                {trialNum < 4 ? (
                  <button onClick={handleNextTrial} disabled={phase !== 'recorded'}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    4. Next Trial
                  </button>
                ) : (
                  <button onClick={generatePDF} disabled={phase !== 'recorded' && trials.length < 4}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    Generate PDF
                  </button>
                )}
              </div>

              {/* Trial Data Table */}
              <div className="flex-1 overflow-auto px-4 py-2">
                {trials.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-400 text-sm font-mono">
                    Complete Spin &rarr; Drop &rarr; Record to log trial data
                  </div>
                ) : (
                  <table className="w-full text-[10px] font-mono border-collapse">
                    <thead>
                      <tr className="bg-gray-50 sticky top-0">
                        {['#', 'Object', 'IAV', 'FAV', 'x (cm)', 'IRI', 'FRI', 'IAM', 'FAM', '%diff', 'Init K', 'Final K', 'Energy%'].map(h => (
                          <th key={h} className="border border-gray-200 px-1.5 py-1.5 text-gray-600 font-bold whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {trials.map(t => (
                        <tr key={t.trial} className="hover:bg-blue-50/50">
                          <td className="border border-gray-200 px-1.5 py-1 text-center font-bold">{t.trial}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-center">{t.object}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.iav.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.fav.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.x.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.iri.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.fri.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.iam.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.fam.toFixed(2)}</td>
                          <td className={`border border-gray-200 px-1.5 py-1 text-right font-bold ${
                            Math.abs(t.pctDiff) < 3 ? 'text-green-600' : 'text-red-600'
                          }`}>{t.pctDiff.toFixed(2)}%</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.initK.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.finalK.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-red-600 font-bold">{t.energyPct.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Guidance text */}
              <div className="px-4 py-1.5 border-t border-gray-100 text-[9px] font-mono text-gray-400">
                {phase === 'idle' && !allDone && `Set ω and object, then Spin. Trial ${trialNum}: ${selectedObject} selected.`}
                {phase === 'spinning' && (spinCountdown > 0 ? `Disk spinning... wait ${spinCountdown}s.` : 'Ready! Click Drop.')}
                {phase === 'dropped' && `FAV = ${currentFAV.toFixed(4)} rad/s, x = ${currentOffset.toFixed(4)} cm. Click Record.`}
                {phase === 'recorded' && trialNum < 4 && `Trial ${trialNum} saved. Click Next Trial to proceed.`}
                {phase === 'recorded' && trialNum >= 4 && 'All 4 trials complete! Generate PDF report.'}
                {allDone && phase === 'idle' && 'All 4 trials recorded. Click PDF Report to export.'}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Experiment 7: Momentum Conservation — specialised 4-trial layout
  // ═══════════════════════════════════════════════════════════════════

  if (isExp7) {
    return (
      <div className="h-screen w-full bg-gray-50 text-gray-900 flex flex-col font-sans overflow-hidden">
        {/* Top Bar */}
        <div className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white/90 backdrop-blur-sm z-20 shadow-sm shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="text-gray-700 hover:text-blue-600 flex items-center gap-1.5 text-xs font-mono border border-gray-300 px-2.5 py-1 rounded-lg">
              <ArrowLeft size={12} /> BACK
            </button>
            <div className="h-5 w-px bg-gray-300" />
            <span className="font-bold text-xs tracking-widest text-blue-600 uppercase">{config.title}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded-lg border">
              Trial {Math.min(exp7Trial, 4)} / 4
            </span>
            <button onClick={exp7ExportCSV} disabled={exp7Trials.length === 0}
              className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-mono rounded-lg flex items-center gap-1 border border-gray-300 disabled:opacity-40">
              <Download size={11} /> CSV
            </button>
            <button onClick={exp7GeneratePDF} disabled={exp7Trials.length === 0}
              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-mono rounded-lg flex items-center gap-1 disabled:opacity-40">
              <FileText size={11} /> PDF Report
            </button>
            <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : isReconnecting ? 'border-yellow-400 text-yellow-700 bg-yellow-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : isReconnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'LIVE' : isReconnecting ? 'REC...' : 'OFF'}
            </div>
            {vrConnected && (
              <div className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border border-purple-400 text-purple-700 bg-purple-50">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                VR
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">

          {/* Left Panel — controls */}
          <div className="w-[280px] bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
            {/* Cart 1 */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-red-500 mb-2">Cart 1 (Red)</div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Mass</span>
                    <span className="font-bold text-red-600">{exp7M1.toFixed(2)} kg</span>
                  </div>
                  <input type="range" min={0.10} max={2.0} step={0.05} value={exp7M1}
                    onChange={e => { const v = parseFloat(e.target.value); setExp7M1(v); isaacService.sendCommand('set_mass1', v); }}
                    disabled={exp7Phase !== 'idle'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500 disabled:opacity-50" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Velocity</span>
                    <span className="font-bold text-red-600">{exp7V1.toFixed(2)} m/s</span>
                  </div>
                  <input type="range" min={-2.0} max={2.0} step={0.05} value={exp7V1}
                    onChange={e => { const v = parseFloat(e.target.value); setExp7V1(v); isaacService.sendCommand('set_velocity1', v); }}
                    disabled={exp7Phase !== 'idle'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500 disabled:opacity-50" />
                </div>
              </div>
            </div>

            {/* Cart 2 */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-blue-500 mb-2">Cart 2 (Blue)</div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Mass</span>
                    <span className="font-bold text-blue-600">{exp7M2.toFixed(2)} kg</span>
                  </div>
                  <input type="range" min={0.10} max={2.0} step={0.05} value={exp7M2}
                    onChange={e => { const v = parseFloat(e.target.value); setExp7M2(v); isaacService.sendCommand('set_mass2', v); }}
                    disabled={exp7Phase !== 'idle'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Velocity</span>
                    <span className="font-bold text-blue-600">{exp7V2.toFixed(2)} m/s</span>
                  </div>
                  <input type="range" min={-2.0} max={2.0} step={0.05} value={exp7V2}
                    onChange={e => { const v = parseFloat(e.target.value); setExp7V2(v); isaacService.sendCommand('set_velocity2', v); }}
                    disabled={exp7Phase !== 'idle'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50" />
                </div>
              </div>
            </div>

            {/* Restitution */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Coefficient of Restitution</div>
              <div className="flex items-center gap-2 mb-1">
                <input type="range" min={0} max={1} step={0.05} value={exp7Rest}
                  onChange={e => { const v = parseFloat(e.target.value); setExp7Rest(v); isaacService.sendCommand('set_elasticity', v); }}
                  disabled={exp7Phase !== 'idle'}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-500 disabled:opacity-50" />
                <span className="text-sm font-mono font-bold w-10 text-center">{exp7Rest.toFixed(2)}</span>
              </div>
              <div className="text-[9px] text-gray-400 font-mono text-center">
                0 = perfectly inelastic &middot; 1 = elastic
              </div>
            </div>

            {/* Current Trial Info */}
            <div className="p-3 border-b border-gray-200 bg-gradient-to-b from-emerald-50/50 to-white">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Current Trial</div>
              <div className="grid grid-cols-2 gap-1.5">
                <InfoCard label="Trial" value={`${Math.min(exp7Trial, 4)} / 4`} accent="blue" />
                <InfoCard label="Phase" value={exp7Phase.toUpperCase()} accent="green" />
                <InfoCard label="p_total (before)" value={`${(exp7M1 * exp7V1 + exp7M2 * exp7V2).toFixed(4)}`} accent="cyan" />
                {exp7Phase === 'settled' && (
                  <>
                    <InfoCard label="v1 (final)" value={`${exp7PostV1.toFixed(4)}`} accent="red" />
                    <InfoCard label="v2 (final)" value={`${exp7PostV2.toFixed(4)}`} accent="blue" />
                  </>
                )}
              </div>
            </div>

            {/* Live Chart */}
            <div className="flex-1 p-2 flex flex-col min-h-[160px]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1 flex items-center gap-1">
                <Activity size={10} /> Velocity
              </div>
              <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis stroke="#6b7280" fontSize={9} tickFormatter={v => v.toFixed(2)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', fontSize: '10px', borderRadius: '6px' }}
                      labelStyle={{ display: 'none' }}
                      formatter={(v: number) => v.toFixed(4)}
                    />
                    <Line type="monotone" dataKey="v1" stroke="#ef4444" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Cart 1 v" />
                    <Line type="monotone" dataKey="v2" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Cart 2 v" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Center: Viewport + Bottom Panel */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* WebRTC Viewport */}
            <div className="flex-1 relative bg-gray-900 min-h-0">
              <div className="absolute inset-0">
                <WebRTCIsaacViewer serverUrl={SERVER_CONFIG.httpUrl} usdPath={config.usdPath} className="w-full h-full" />
              </div>
            </div>

            {/* Bottom Panel */}
            <div className="h-auto max-h-[45%] bg-white border-t-2 border-gray-200 flex flex-col shrink-0">

              {/* Action Bar */}
              <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
                {/* Step Indicators */}
                <div className="flex items-center gap-1">
                  {(['idle', 'running', 'settled', 'recorded'] as const).map((step, i) => (
                    <React.Fragment key={step}>
                      {i > 0 && <div className={`w-4 h-0.5 rounded ${
                        (['idle', 'running', 'settled', 'recorded'].indexOf(exp7Phase) >= i) ? 'bg-emerald-500' : 'bg-gray-300'
                      }`} />}
                      <div className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold ${
                        exp7Phase === step ? 'bg-emerald-600 text-white' :
                        (['idle', 'running', 'settled', 'recorded'].indexOf(exp7Phase) > i) ? 'bg-emerald-100 text-emerald-600' :
                        'bg-gray-200 text-gray-400'
                      }`}>
                        {step === 'idle' ? 'Setup' : step === 'running' ? 'Colliding' : step === 'settled' ? 'Done' : 'Recorded'}
                      </div>
                    </React.Fragment>
                  ))}
                </div>

                <div className="h-5 w-px bg-gray-300" />
                <span className="text-[10px] font-mono text-gray-600">
                  e = <span className="font-bold text-gray-900">{exp7Rest.toFixed(2)}</span>
                </span>

                <div className="flex-1" />

                {/* Action Buttons */}
                <button onClick={exp7HandleRun} disabled={exp7Phase !== 'idle' || exp7AllDone}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  1. Run Collision
                </button>
                <button onClick={exp7HandleRecord} disabled={exp7Phase !== 'settled'}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  2. Record
                </button>
                {exp7Trial < 4 ? (
                  <button onClick={exp7HandleNext} disabled={exp7Phase !== 'recorded'}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    3. Next Trial
                  </button>
                ) : (
                  <button onClick={exp7GeneratePDF} disabled={exp7Phase !== 'recorded' && exp7Trials.length < 4}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    Generate PDF
                  </button>
                )}
              </div>

              {/* Trial Data Table */}
              <div className="flex-1 overflow-auto px-4 py-2">
                {exp7Trials.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-400 text-sm font-mono">
                    Set parameters &rarr; Run Collision &rarr; Record to log trial data
                  </div>
                ) : (
                  <table className="w-full text-[10px] font-mono border-collapse">
                    <thead>
                      <tr className="bg-gray-50 sticky top-0">
                        {['#', 'm1', 'm2', 'v1_i', 'v2_i', 'e', 'v1_f', 'v2_f', 'p_before', 'p_after', '%diff', 'KE_before', 'KE_after', 'KE_loss%', 'Type'].map(h => (
                          <th key={h} className="border border-gray-200 px-1.5 py-1.5 text-gray-600 font-bold whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {exp7Trials.map(t => (
                        <tr key={t.trial} className="hover:bg-blue-50/50">
                          <td className="border border-gray-200 px-1.5 py-1 text-center font-bold">{t.trial}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.m1.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.m2.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-red-600">{t.v1i.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-blue-600">{t.v2i.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-center">{t.restitution.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-red-600">{t.v1f.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-blue-600">{t.v2f.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.pBefore.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.pAfter.toFixed(4)}</td>
                          <td className={`border border-gray-200 px-1.5 py-1 text-right font-bold ${
                            Math.abs(t.pPctDiff) < 3 ? 'text-green-600' : 'text-red-600'
                          }`}>{t.pPctDiff.toFixed(2)}%</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.keBefore.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.keAfter.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-amber-600 font-bold">{t.keLossPct.toFixed(2)}%</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-center">{t.collisionType}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Guidance text */}
              <div className="px-4 py-1.5 border-t border-gray-100 text-[9px] font-mono text-gray-400">
                {exp7Phase === 'idle' && !exp7AllDone && `Adjust masses, velocities, and restitution. Then click Run Collision. Trial ${exp7Trial}.`}
                {exp7Phase === 'running' && 'Carts approaching... waiting for collision.'}
                {exp7Phase === 'settled' && `Collision complete. v1_f = ${exp7PostV1.toFixed(4)}, v2_f = ${exp7PostV2.toFixed(4)}. Click Record.`}
                {exp7Phase === 'recorded' && exp7Trial < 4 && `Trial ${exp7Trial} saved. Click Next Trial.`}
                {exp7Phase === 'recorded' && exp7Trial >= 4 && 'All 4 trials complete! Generate PDF report.'}
                {exp7AllDone && exp7Phase === 'idle' && 'All 4 trials recorded. Click PDF Report to export.'}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Experiment 3: Ballistic Pendulum — specialised 5-trial layout
  // ═══════════════════════════════════════════════════════════════════

  if (isExp3) {
    const M_total = exp3BallMass + exp3PendMass;
    const exp3PhaseSteps = ['idle', 'firing', 'swinging', 'settled', 'recorded'] as const;
    const stepLabel = (s: typeof exp3PhaseSteps[number]) =>
      s === 'idle' ? 'Setup' :
      s === 'firing' ? 'Firing' :
      s === 'swinging' ? 'Swinging' :
      s === 'settled' ? 'Apex' : 'Recorded';

    return (
      <div className="h-screen w-full bg-gray-50 text-gray-900 flex flex-col font-sans overflow-hidden">
        {/* Top Bar */}
        <div className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white/90 backdrop-blur-sm z-20 shadow-sm shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="text-gray-700 hover:text-blue-600 flex items-center gap-1.5 text-xs font-mono border border-gray-300 px-2.5 py-1 rounded-lg">
              <ArrowLeft size={12} /> BACK
            </button>
            <div className="h-5 w-px bg-gray-300" />
            <span className="font-bold text-xs tracking-widest text-blue-600 uppercase">{config.title}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded-lg border">
              Trial {Math.min(exp3Trial, EXP3_TARGET_TRIALS)} / {EXP3_TARGET_TRIALS}
            </span>
            <button onClick={exp3ExportCSV} disabled={exp3Trials.length === 0}
              className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-mono rounded-lg flex items-center gap-1 border border-gray-300 disabled:opacity-40">
              <Download size={11} /> CSV
            </button>
            <button onClick={exp3GeneratePDF} disabled={exp3Trials.length === 0}
              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-mono rounded-lg flex items-center gap-1 disabled:opacity-40">
              <FileText size={11} /> PDF Report
            </button>
            <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : isReconnecting ? 'border-yellow-400 text-yellow-700 bg-yellow-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : isReconnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'LIVE' : isReconnecting ? 'REC...' : 'OFF'}
            </div>
            {vrConnected && (
              <div className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border border-purple-400 text-purple-700 bg-purple-50">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                VR
              </div>
            )}
          </div>
        </div>

        {/* Main */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel — controls */}
          <div className="w-[300px] bg-white border-r border-gray-200 flex flex-col shrink-0 overflow-y-auto">
            {/* Setup parameters */}
            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Projectile</div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Ball mass m_ball</span>
                    <span className="font-bold text-amber-600">{(exp3BallMass * 1000).toFixed(1)} g</span>
                  </div>
                  <input type="range" min={0.005} max={0.100} step={0.001} value={exp3BallMass}
                    onChange={e => { const v = parseFloat(e.target.value); setExp3BallMass(v); isaacService.sendCommand('set_ball_mass', v); }}
                    disabled={exp3Phase !== 'idle' && exp3Phase !== 'recorded'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-amber-500 disabled:opacity-50" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">v₀ launcher</span>
                    <span className="font-bold text-amber-600">{exp3V0.toFixed(2)} m/s</span>
                  </div>
                  <input type="range" min={1.0} max={8.0} step={0.1} value={exp3V0}
                    onChange={e => { const v = parseFloat(e.target.value); setExp3V0(v); isaacService.sendCommand('set_exp3_v0', v); }}
                    disabled={exp3Phase !== 'idle' && exp3Phase !== 'recorded'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-amber-500 disabled:opacity-50" />
                </div>
              </div>
            </div>

            <div className="p-3 border-b border-gray-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Pendulum</div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Catcher mass m_pend</span>
                    <span className="font-bold text-purple-600">{(exp3PendMass * 1000).toFixed(1)} g</span>
                  </div>
                  <input type="range" min={0.050} max={0.500} step={0.005} value={exp3PendMass}
                    onChange={e => { const v = parseFloat(e.target.value); setExp3PendMass(v); isaacService.sendCommand('set_pend_mass', v); }}
                    disabled={exp3Phase !== 'idle' && exp3Phase !== 'recorded'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-500 disabled:opacity-50" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-gray-600">Rod length L</span>
                    <span className="font-bold text-purple-600">{(exp3L * 100).toFixed(1)} cm</span>
                  </div>
                  <input type="range" min={0.15} max={0.50} step={0.01} value={exp3L}
                    onChange={e => { const v = parseFloat(e.target.value); setExp3L(v); isaacService.sendCommand('set_exp3_L', v); }}
                    disabled={exp3Phase !== 'idle' && exp3Phase !== 'recorded'}
                    className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-500 disabled:opacity-50" />
                </div>
              </div>
            </div>

            {/* Live trial info */}
            <div className="p-3 border-b border-gray-200 bg-gradient-to-b from-blue-50/50 to-white">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-2">Current Trial</div>
              <div className="grid grid-cols-2 gap-1.5">
                <InfoCard label="Trial" value={`${Math.min(exp3Trial, EXP3_TARGET_TRIALS)} / ${EXP3_TARGET_TRIALS}`} accent="blue" />
                <InfoCard label="Phase" value={exp3Phase.toUpperCase()} accent="green" />
                <InfoCard label="M total" value={`${(M_total * 1000).toFixed(1)} g`} accent="gray" />
                <InfoCard label="m/M" value={`${((exp3BallMass / M_total) * 100).toFixed(1)} %`} accent="amber" />
                <InfoCard label="θ max" value={`${exp3LiveThetaMax.toFixed(2)}°`} accent="red" />
                <InfoCard label="v₀ measured" value={`${exp3LiveV0Meas.toFixed(3)}`} accent="cyan" />
              </div>
            </div>

            {/* Live theta chart */}
            <div className="flex-1 p-2 flex flex-col min-h-[180px]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1 flex items-center gap-1">
                <Activity size={10} /> θ(t) live
              </div>
              <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis yAxisId="left" stroke="#a855f7" fontSize={9} tickFormatter={v => v.toFixed(1)} />
                    <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={9} tickFormatter={v => v.toFixed(1)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', fontSize: '10px', borderRadius: '6px' }}
                      labelStyle={{ display: 'none' }}
                      formatter={(v: number) => v.toFixed(4)}
                    />
                    <Line yAxisId="left" type="monotone" dataKey="theta" stroke="#a855f7" strokeWidth={1.5} dot={false} isAnimationActive={false} name="θ (°)" />
                    <Line yAxisId="right" type="monotone" dataKey="ball_velocity" stroke="#f59e0b" strokeWidth={1.5} dot={false} isAnimationActive={false} name="|v_ball| (m/s)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Center: Viewport + Bottom Panel */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 relative bg-gray-900 min-h-0">
              <div className="absolute inset-0">
                <WebRTCIsaacViewer serverUrl={SERVER_CONFIG.httpUrl} usdPath={config.usdPath} className="w-full h-full" />
              </div>
            </div>

            <div className="h-auto max-h-[45%] bg-white border-t-2 border-gray-200 flex flex-col shrink-0">
              {/* Action Bar */}
              <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
                <div className="flex items-center gap-1">
                  {exp3PhaseSteps.map((step, i) => (
                    <React.Fragment key={step}>
                      {i > 0 && <div className={`w-4 h-0.5 rounded ${
                        (exp3PhaseSteps.indexOf(exp3Phase) >= i) ? 'bg-blue-500' : 'bg-gray-300'
                      }`} />}
                      <div className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold ${
                        exp3Phase === step ? 'bg-blue-600 text-white' :
                        (exp3PhaseSteps.indexOf(exp3Phase) > i) ? 'bg-blue-100 text-blue-600' :
                        'bg-gray-200 text-gray-400'
                      }`}>
                        {stepLabel(step)}
                      </div>
                    </React.Fragment>
                  ))}
                </div>

                <div className="h-5 w-px bg-gray-300" />
                <span className="text-[10px] font-mono text-gray-600">
                  v₀ set = <span className="font-bold text-gray-900">{exp3V0.toFixed(2)} m/s</span>
                </span>

                <div className="flex-1" />

                <button onClick={exp3HandleFire}
                  disabled={(exp3Phase !== 'idle' && exp3Phase !== 'recorded') || exp3AllDone}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  1. Fire
                </button>
                <button onClick={exp3HandleRecord}
                  disabled={exp3Phase !== 'settled'}
                  className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                  2. Record
                </button>
                {exp3Trial < EXP3_TARGET_TRIALS ? (
                  <button onClick={exp3HandleNext}
                    disabled={exp3Phase !== 'recorded'}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    3. Next Trial
                  </button>
                ) : (
                  <button onClick={exp3GeneratePDF}
                    disabled={exp3Trials.length === 0}
                    className="px-3 py-1.5 text-[11px] font-mono font-bold rounded-lg transition-all shadow-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-30 disabled:cursor-not-allowed">
                    Generate PDF
                  </button>
                )}
              </div>

              {/* Trial Data Table */}
              <div className="flex-1 overflow-auto px-4 py-2">
                {exp3Trials.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-400 text-sm font-mono">
                    Set m_ball, m_pend, v₀, L &rarr; Fire &rarr; wait for apex &rarr; Record
                  </div>
                ) : (
                  <table className="w-full text-[10px] font-mono border-collapse">
                    <thead>
                      <tr className="bg-gray-50 sticky top-0">
                        {['#', 'm_ball (g)', 'm_pend (g)', 'L (cm)', 'v₀ set', 'θ max (°)', 'h_max (m)', 'v after', 'v₀ derived', '%diff', 'KE in (J)', 'KE after (J)', 'KE loss%'].map(h => (
                          <th key={h} className="border border-gray-200 px-1.5 py-1.5 text-gray-600 font-bold whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {exp3Trials.map(t => (
                        <tr key={t.trial} className="hover:bg-blue-50/50">
                          <td className="border border-gray-200 px-1.5 py-1 text-center font-bold">{t.trial}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{(t.ball_mass * 1000).toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{(t.pend_mass * 1000).toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{(t.L * 100).toFixed(1)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-amber-600">{t.v0_input.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.theta_max_deg.toFixed(2)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.h_max.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.v_after_ideal.toFixed(3)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-cyan-600">{t.v0_measured.toFixed(3)}</td>
                          <td className={`border border-gray-200 px-1.5 py-1 text-right font-bold ${
                            Math.abs(t.v0_error_pct) < 3 ? 'text-green-600' : 'text-red-600'
                          }`}>{t.v0_error_pct.toFixed(2)}%</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.ke_input.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right">{t.ke_after_ideal.toFixed(4)}</td>
                          <td className="border border-gray-200 px-1.5 py-1 text-right text-amber-600 font-bold">{t.ke_loss_percent.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="px-4 py-1.5 border-t border-gray-100 text-[9px] font-mono text-gray-400">
                {exp3Phase === 'idle' && !exp3AllDone && `Adjust parameters, then Fire. Trial ${exp3Trial}.`}
                {exp3Phase === 'firing' && 'Ball in flight ... waiting for capture.'}
                {exp3Phase === 'swinging' && `Ball captured. Pendulum swinging up (θ = ${exp3LiveThetaMax.toFixed(2)}°).`}
                {exp3Phase === 'settled' && `Apex reached. θ_max = ${exp3LiveThetaMax.toFixed(2)}°, v₀_measured = ${exp3LiveV0Meas.toFixed(3)} m/s. Click Record.`}
                {exp3Phase === 'recorded' && exp3Trial < EXP3_TARGET_TRIALS && `Trial ${exp3Trial} saved (${exp3Trials.length}/${EXP3_TARGET_TRIALS}). Click Next Trial.`}
                {exp3Phase === 'recorded' && exp3Trial >= EXP3_TARGET_TRIALS && `All ${EXP3_TARGET_TRIALS} trials complete! Click Generate PDF to export the lab report.`}
                {exp3AllDone && exp3Phase === 'idle' && `All ${EXP3_TARGET_TRIALS} trials recorded. Click PDF Report at the top right to export.`}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // Generic Experiment View (non-exp1)
  // ═══════════════════════════════════════════════════════════════════

  return (
    <div className="h-screen w-full bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 text-gray-900 flex flex-col font-sans overflow-hidden">
      {/* Top Bar */}
      <div className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-gray-700 hover:text-blue-600 flex items-center gap-1.5 text-xs font-mono border border-gray-300 px-2.5 py-1 rounded-lg">
            <ArrowLeft size={12} /> BACK
          </button>
          <div className="h-5 w-px bg-gray-300" />
          <span className="font-bold text-xs tracking-widest text-blue-600 uppercase">{config.title}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : isReconnecting ? 'border-yellow-400 text-yellow-700 bg-yellow-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : isReconnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
            {isConnected ? 'LIVE' : isReconnecting ? 'REC...' : 'OFF'}
          </div>
          {vrConnected && (
            <div className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border border-purple-400 text-purple-700 bg-purple-50">
              <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
              VR
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Viewport */}
        <div className="flex-1 relative bg-gray-100">
          <div className="absolute inset-0">
            <WebRTCIsaacViewer serverUrl={SERVER_CONFIG.httpUrl} usdPath={config.usdPath} className="w-full h-full" />
          </div>
        </div>

        {/* Right Panel */}
        <div className="w-[320px] bg-white/95 border-l border-gray-200 flex flex-col shadow-lg overflow-y-auto">
          {/* Controls */}
          <div className="border-b border-gray-200 p-3">
            <div className="text-[10px] font-bold mb-2 uppercase tracking-wider text-gray-600">Controls</div>
            <div className="space-y-2">
              {config.controls.map(control => {
                if (control.type === 'slider') {
                  const val = controlValues[control.id] ?? (control.defaultValue as number);
                  return (
                    <div key={control.id} className="space-y-0.5">
                      <div className="flex items-center justify-between">
                        <label className="text-gray-700 text-[10px] font-mono font-semibold">{control.label}</label>
                        <span className="text-blue-600 text-[10px] font-mono font-bold bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">{val.toFixed(1)}</span>
                      </div>
                      <input type="range" min={control.min} max={control.max} step={control.step} value={val}
                        onChange={e => handleGenericControl(control.id, parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600" />
                    </div>
                  );
                }
                if (control.type === 'button') {
                  return (
                    <button key={control.id} onClick={() => handleGenericControl(control.id, true)}
                      className="w-full px-2 py-2 text-[11px] font-mono font-bold rounded-lg transition-all shadow bg-blue-600 hover:bg-blue-700 text-white">
                      {control.label}
                    </button>
                  );
                }
                return null;
              })}
            </div>
          </div>

          {/* Exp2 Report Status & Downloads */}
          {isExp2 && (exp2Progress || exp2ReportData) && (
            <div className="border-b border-gray-200 p-3">
              {exp2Progress && !exp2ReportData && (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <div className="text-[10px] font-mono text-amber-600">{exp2Progress}</div>
                </div>
              )}
              {exp2ReportData && (
                <div className="space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-600">Report Generated</div>
                  <div className="text-[9px] font-mono text-gray-600 grid grid-cols-2 gap-1">
                    <span>T₀ theory: <b>{exp2ReportData.T0_theory?.toFixed(4)} s</b></span>
                    <span>T₀ measured: <b>{exp2ReportData.T0_measured?.toFixed(4)} s</b></span>
                    <span>Sweep: <b>{exp2ReportData.sweep_points} points</b></span>
                  </div>
                  {exp2ReportData.plots?.overlay && (
                    <img src={exp2ReportData.plots.overlay} alt="Overlay" className="w-full rounded border border-gray-200" />
                  )}
                  {exp2ReportData.plots?.period && (
                    <img src={exp2ReportData.plots.period} alt="Period" className="w-full rounded border border-gray-200" />
                  )}
                  <div className="flex flex-wrap gap-1">
                    <button onClick={exp2GeneratePDF}
                      className="px-2 py-1.5 text-[10px] font-mono font-bold bg-red-600 text-white rounded-lg hover:bg-red-700 shadow-sm">
                      <FileText size={10} className="inline mr-1" />PDF Report
                    </button>
                    {exp2ReportData.zip_b64 && (
                      <button onClick={() => {
                        const bin = atob(exp2ReportData.zip_b64);
                        const arr = new Uint8Array(bin.length);
                        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                        const blob = new Blob([arr], {type: 'application/zip'});
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob); a.download = 'Expt2_Large_Amplitude_Pendulum.zip'; a.click();
                        URL.revokeObjectURL(a.href);
                      }} className="px-2 py-1.5 text-[10px] font-mono font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-sm">
                        <Download size={10} className="inline mr-1" />Download All (ZIP)
                      </button>
                    )}
                    {exp2ReportData.report_md && (
                      <button onClick={() => {
                        const bin = atob(exp2ReportData.report_md);
                        const blob = new Blob([bin], {type: 'text/markdown'});
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob); a.download = 'Expt2_Report.md'; a.click();
                        URL.revokeObjectURL(a.href);
                      }} className="px-2 py-1.5 text-[10px] font-mono bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100">
                        <FileText size={10} className="inline mr-1" />Report
                      </button>
                    )}
                    {exp2ReportData.period_csv && (
                      <button onClick={() => {
                        const bin = atob(exp2ReportData.period_csv);
                        const blob = new Blob([bin], {type: 'text/csv'});
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob); a.download = 'period_summary.csv'; a.click();
                        URL.revokeObjectURL(a.href);
                      }} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />CSV
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Exp4 Driven-Damped Lab Report Status & Downloads */}
          {isExp4 && (exp4Progress || exp4ReportData) && (
            <div className="border-b border-gray-200 p-3">
              {exp4Progress && !exp4ReportData && (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <div className="text-[10px] font-mono text-amber-600">{exp4Progress}</div>
                </div>
              )}
              {exp4ReportData && (
                <div className="space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-600">
                    Exp 4 Lab Report Generated
                  </div>
                  <div className="text-[9px] font-mono text-gray-600 grid grid-cols-2 gap-1">
                    <span>f₀ theory: <b>{exp4ReportData.physics?.f0_hz?.toFixed(4) ?? '—'} Hz</b></span>
                    <span>T₀ theory: <b>{exp4ReportData.physics?.T0_s?.toFixed(4) ?? '—'} s</b></span>
                    <span>I disk: <b>{exp4ReportData.physics?.inertia?.toExponential(3) ?? '—'} kg·m²</b></span>
                    <span>γ ringdown: <b>{exp4ReportData.free_oscillation_fit?.gamma?.toFixed(4) ?? '—'} /s</b></span>
                    <span>R² fit: <b>{exp4ReportData.free_oscillation_fit?.r2?.toFixed(4) ?? '—'}</b></span>
                    <span>%diff f_res: <b>{exp4ReportData.metrics?.pct_diff_lightest?.toFixed(2) ?? '—'}%</b></span>
                  </div>
                  {exp4ReportData.plots?.resonance_curves && (
                    <img src={exp4ReportData.plots.resonance_curves} alt="Resonance curves" className="w-full rounded border border-gray-200" />
                  )}
                  {exp4ReportData.plots?.phase_lag && (
                    <img src={exp4ReportData.plots.phase_lag} alt="Phase lag" className="w-full rounded border border-gray-200" />
                  )}
                  {exp4ReportData.plots?.free_oscillation && (
                    <img src={exp4ReportData.plots.free_oscillation} alt="Free oscillation" className="w-full rounded border border-gray-200" />
                  )}
                  {exp4ReportData.plots?.phase_comparison && (
                    <img src={exp4ReportData.plots.phase_comparison} alt="Phase comparison" className="w-full rounded border border-gray-200" />
                  )}
                  <div className="flex flex-wrap gap-1">
                    <button onClick={exp4GeneratePrettyPDF}
                      className="px-2 py-1.5 text-[10px] font-mono font-bold bg-red-600 text-white rounded-lg hover:bg-red-700 shadow-sm">
                      <FileText size={10} className="inline mr-1" />Download PDF Report
                    </button>
                    {exp4ReportData.zip_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp4ReportData.zip_b64!,
                        'Expt4_Driven_Damped_Oscillator_Report.zip',
                        'application/zip',
                      )} className="px-2 py-1.5 text-[10px] font-mono font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-sm">
                        <Download size={10} className="inline mr-1" />Download All (ZIP)
                      </button>
                    )}
                    {exp4ReportData.report_md && (
                      <button onClick={() => downloadBase64File(
                        exp4ReportData.report_md!,
                        'Expt4_Driven_Damped_Oscillator_Report.md',
                        'text/markdown',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100">
                        <FileText size={10} className="inline mr-1" />Markdown
                      </button>
                    )}
                    {exp4ReportData.resonance_csv && (
                      <button onClick={() => downloadBase64File(
                        exp4ReportData.resonance_csv!,
                        'exp4_resonance_curves.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />Resonance CSV
                      </button>
                    )}
                    {exp4ReportData.free_csv && (
                      <button onClick={() => downloadBase64File(
                        exp4ReportData.free_csv!,
                        'exp4_free_oscillation.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />Ringdown CSV
                      </button>
                    )}
                    {exp4ReportData.summary_json && (
                      <button onClick={() => downloadBase64File(
                        exp4ReportData.summary_json!,
                        'exp4_summary.json',
                        'application/json',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />JSON
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Exp8 Resonance Air Column Report Status & Downloads */}
          {isExp8 && (exp8Progress || exp8ReportData) && (
            <div className="border-b border-gray-200 p-3">
              {exp8Progress && !exp8ReportData && (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <div className="text-[10px] font-mono text-amber-600">{exp8Progress}</div>
                </div>
              )}
              {exp8ReportData && (
                <div className="space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-600">Exp 8 Report Generated</div>
                  <div className="text-[9px] font-mono text-gray-600 grid grid-cols-2 gap-1">
                    <span>v measured: <b>{typeof exp8ReportData.metrics?.v_measured === 'number' ? exp8ReportData.metrics.v_measured.toFixed(2) : '—'} m/s</b></span>
                    <span>v reference: <b>{typeof exp8ReportData.metrics?.v_reference === 'number' ? exp8ReportData.metrics.v_reference.toFixed(1) : '340.0'} m/s</b></span>
                    <span>% diff: <b>{typeof exp8ReportData.metrics?.v_pct_diff === 'number' ? exp8ReportData.metrics.v_pct_diff.toFixed(2) : '—'} %</b></span>
                    <span>R² fit: <b>{typeof exp8ReportData.metrics?.r_squared === 'number' ? exp8ReportData.metrics.r_squared.toFixed(4) : '—'}</b></span>
                    <span>End-effect (meas): <b>{typeof exp8ReportData.metrics?.measured_end_effect_cm === 'number' ? exp8ReportData.metrics.measured_end_effect_cm.toFixed(3) : '—'} cm</b></span>
                    <span>End-effect 0.3·d: <b>{typeof exp8ReportData.metrics?.theory_end_effect_cm === 'number' ? exp8ReportData.metrics.theory_end_effect_cm.toFixed(3) : '—'} cm</b></span>
                    <span>f₁ open: <b>{typeof exp8ReportData.metrics?.f_open_fundamental_Hz === 'number' ? exp8ReportData.metrics.f_open_fundamental_Hz.toFixed(2) : '—'} Hz</b></span>
                    <span>f₁ closed: <b>{typeof exp8ReportData.metrics?.f_closed_fundamental_Hz === 'number' ? exp8ReportData.metrics.f_closed_fundamental_Hz.toFixed(2) : '—'} Hz</b></span>
                    <span>f₁ open/closed: <b>{typeof exp8ReportData.metrics?.open_to_closed_ratio === 'number' ? exp8ReportData.metrics.open_to_closed_ratio.toFixed(3) : '—'}</b></span>
                    <span>Closed L points: <b>{exp8ReportData.metrics?.n_closed_lengths ?? '—'}</b></span>
                  </div>
                  {exp8ReportData.plots?.L_vs_inv_f && (
                    <img src={exp8ReportData.plots.L_vs_inv_f} alt="L vs 1/f fit" className="w-full rounded border border-gray-200" />
                  )}
                  {exp8ReportData.plots?.freq_sweep_user && (
                    <img src={exp8ReportData.plots.freq_sweep_user} alt="Frequency sweep" className="w-full rounded border border-gray-200" />
                  )}
                  {exp8ReportData.plots?.envelope_user && (
                    <img src={exp8ReportData.plots.envelope_user} alt="Standing-wave envelope" className="w-full rounded border border-gray-200" />
                  )}
                  {exp8ReportData.plots?.length_sweep && (
                    <img src={exp8ReportData.plots.length_sweep} alt="Length sweep" className="w-full rounded border border-gray-200" />
                  )}
                  {exp8ReportData.plots?.open_vs_closed && (
                    <img src={exp8ReportData.plots.open_vs_closed} alt="Open vs Closed" className="w-full rounded border border-gray-200" />
                  )}
                  {exp8ReportData.plots?.probe_user && (
                    <img src={exp8ReportData.plots.probe_user} alt="Probe time-series" className="w-full rounded border border-gray-200" />
                  )}
                  <div className="flex flex-wrap gap-1">
                    <button onClick={exp8GeneratePDF}
                      className="px-2 py-1.5 text-[10px] font-mono font-bold bg-red-600 text-white rounded-lg hover:bg-red-700 shadow-sm">
                      <FileText size={10} className="inline mr-1" />PDF Report
                    </button>
                    {exp8ReportData.zip_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp8ReportData.zip_b64,
                        'Expt8_Resonance_Air_Column.zip',
                        'application/zip',
                      )} className="px-2 py-1.5 text-[10px] font-mono font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-sm">
                        <Download size={10} className="inline mr-1" />Download All (ZIP)
                      </button>
                    )}
                    {exp8ReportData.report_md && (
                      <button onClick={() => downloadBase64File(
                        exp8ReportData.report_md,
                        'Expt8_Resonance_Air_Column_Report.md',
                        'text/markdown',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100">
                        <FileText size={10} className="inline mr-1" />Markdown
                      </button>
                    )}
                    {exp8ReportData.csv?.closed_L_vs_f && (
                      <button onClick={() => downloadBase64File(
                        exp8ReportData.csv.closed_L_vs_f,
                        'closed_L_vs_f.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />L-vs-f CSV
                      </button>
                    )}
                    {exp8ReportData.csv?.length_sweep_closed && (
                      <button onClick={() => downloadBase64File(
                        exp8ReportData.csv.length_sweep_closed,
                        'length_sweep_closed.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />Length-sweep CSV
                      </button>
                    )}
                    {exp8ReportData.csv?.open_freq_sweep && (
                      <button onClick={() => downloadBase64File(
                        exp8ReportData.csv.open_freq_sweep,
                        'open_freq_sweep.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />Open spectrum CSV
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Exp5 Python Report Status & Downloads */}
          {isExp5 && (exp5Progress || exp5ReportData) && (
            <div className="border-b border-gray-200 p-3">
              {exp5Progress && !exp5ReportData && (
                <div className="flex items-center gap-2">
                  {!/error|not enough|no response/i.test(exp5Progress) && (
                    <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  )}
                  <div className="text-[10px] font-mono text-amber-600">{exp5Progress}</div>
                </div>
              )}
              {exp5ReportData && (
                <div className="space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-600">
                    Exp5 Report Generated
                  </div>
                  <div className="text-[9px] font-mono text-gray-600 grid grid-cols-2 gap-1">
                    <span>T measured: <b>{typeof exp5ReportData.summary?.period_measured_s === 'number' ? exp5ReportData.summary.period_measured_s.toFixed(4) : '—'} s</b></span>
                    <span>T theory: <b>{typeof exp5ReportData.summary?.period_theory_s === 'number' ? exp5ReportData.summary.period_theory_s.toFixed(4) : '—'} s</b></span>
                    <span>Error: <b>{typeof exp5ReportData.summary?.period_error_pct === 'number' ? exp5ReportData.summary.period_error_pct.toFixed(2) : '—'}%</b></span>
                    <span>Samples: <b>{exp5ReportData.summary?.n_samples ?? '—'}</b></span>
                  </div>
                  {(exp5ReportData.plots as Record<string, string | null | undefined> | undefined)?.period_curve && (
                    <img
                      src={(exp5ReportData.plots as Record<string, string | null | undefined>).period_curve || ''}
                      alt="Period curve"
                      className="w-full rounded border border-gray-200"
                    />
                  )}
                  <div className="flex flex-wrap gap-1">
                    <button
                      onClick={async () => {
                        if (!exp5ReportData?.summary || !exp5ReportData.plots) return;
                        try {
                          const blob = await pdf(
                            <Exp5ReportPDF
                              data={{
                                summary: exp5ReportData.summary as unknown as Exp5ReportData['summary'],
                                period_rows: (exp5ReportData.period_rows ?? []) as unknown as Exp5ReportData['period_rows'],
                                plots: exp5ReportData.plots as unknown as Exp5ReportData['plots'],
                              }}
                            />,
                          ).toBlob();
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'Lab_Report_Rotational_Inertia_Physical_Pendulum.pdf';
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch (err) {
                          alert(`PDF render failed: ${(err as Error).message ?? 'unknown error'}`);
                        }
                      }}
                      className="px-2 py-1.5 text-[10px] font-mono font-bold bg-red-600 text-white rounded-lg hover:bg-red-700 shadow-sm"
                    >
                      <FileText size={10} className="inline mr-1" />PDF Report
                    </button>
                    {exp5ReportData.zip_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp5ReportData.zip_b64!,
                        exp5ReportData.files?.zip || 'Expt5_Rotational_Inertia_Report.zip',
                        'application/zip',
                      )} className="px-2 py-1.5 text-[10px] font-mono font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-sm">
                        <Download size={10} className="inline mr-1" />Download All
                      </button>
                    )}
                    {exp5ReportData.csv_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp5ReportData.csv_b64!,
                        exp5ReportData.files?.csv || 'exp5_raw_timeseries.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />CSV
                      </button>
                    )}
                    {exp5ReportData.period_csv_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp5ReportData.period_csv_b64!,
                        exp5ReportData.files?.period_csv || 'exp5_cycle_periods.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />Periods
                      </button>
                    )}
                    {exp5ReportData.report_md && (
                      <button onClick={() => downloadBase64File(
                        exp5ReportData.report_md!,
                        exp5ReportData.files?.markdown || 'Expt5_Rotational_Inertia_Report.md',
                        'text/markdown',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100">
                        <FileText size={10} className="inline mr-1" />Markdown
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Exp6 Python Report Status & Downloads */}
          {isExp6 && (exp6Progress || exp6ReportData) && (
            <div className="border-b border-gray-200 p-3">
              {exp6Progress && !exp6ReportData && (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <div className="text-[10px] font-mono text-amber-600">{exp6Progress}</div>
                </div>
              )}
              {exp6ReportData && (
                <div className="space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-600">
                    Exp6 Report Generated
                  </div>
                  <div className="text-[9px] font-mono text-gray-600 grid grid-cols-2 gap-1">
                    <span>F measured: <b>{typeof exp6ReportData.summary?.mean_force_N === 'number' ? exp6ReportData.summary.mean_force_N.toFixed(4) : '—'} N</b></span>
                    <span>Error: <b>{typeof exp6ReportData.summary?.force_error_pct === 'number' ? exp6ReportData.summary.force_error_pct.toFixed(2) : '—'}%</b></span>
                    <span>Samples: <b>{exp6ReportData.summary?.n_samples ?? '—'}</b></span>
                    <span>Duration: <b>{typeof exp6ReportData.summary?.duration_s === 'number' ? exp6ReportData.summary.duration_s.toFixed(2) : '—'} s</b></span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <button onClick={exp6GeneratePrettyPDF}
                      className="px-2 py-1.5 text-[10px] font-mono font-bold bg-red-600 text-white rounded-lg hover:bg-red-700 shadow-sm">
                      <FileText size={10} className="inline mr-1" />Styled PDF
                    </button>
                    {exp6ReportData.pdf_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp6ReportData.pdf_b64!,
                        exp6ReportData.files?.pdf || 'Lab_Report_Centripetal_Force_backend.pdf',
                        'application/pdf',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100">
                        <FileText size={10} className="inline mr-1" />Backend PDF
                      </button>
                    )}
                    {exp6ReportData.zip_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp6ReportData.zip_b64!,
                        exp6ReportData.files?.zip || 'Expt6_Centripetal_Force_Report.zip',
                        'application/zip',
                      )} className="px-2 py-1.5 text-[10px] font-mono font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-sm">
                        <Download size={10} className="inline mr-1" />Download All
                      </button>
                    )}
                    {exp6ReportData.csv_b64 && (
                      <button onClick={() => downloadBase64File(
                        exp6ReportData.csv_b64!,
                        exp6ReportData.files?.csv || 'exp6_raw_timeseries.csv',
                        'text/csv',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-100">
                        <Download size={10} className="inline mr-1" />CSV
                      </button>
                    )}
                    {exp6ReportData.report_md && (
                      <button onClick={() => downloadBase64File(
                        exp6ReportData.report_md!,
                        exp6ReportData.files?.markdown || 'Expt6_Centripetal_Force_Report.md',
                        'text/markdown',
                      )} className="px-2 py-1.5 text-[10px] font-mono bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100">
                        <FileText size={10} className="inline mr-1" />Markdown
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Extra Metrics */}
          {config.extraMetrics && config.extraMetrics.length > 0 && latestData.current && (
            <div className="border-b border-gray-200 p-3">
              <div className="text-[10px] font-bold mb-1.5 uppercase tracking-wider text-gray-600">Metrics</div>
              <div className="grid grid-cols-2 gap-1.5">
                {config.extraMetrics.map(m => (
                  <div key={m.key} className="rounded-lg border border-gray-200 p-1.5 bg-gray-50">
                    <div className="text-[8px] font-mono uppercase tracking-wider text-gray-500">{m.label}</div>
                    <div className="text-[11px] font-mono font-bold" style={{ color: m.color }}>
                      {typeof (latestData.current as any)?.[m.key] === 'number'
                        ? ((latestData.current as any)[m.key] as number).toFixed(4)
                        : '—'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Chart */}
          <div className="flex-1 p-2 flex flex-col min-h-0">
            <div className="text-[10px] font-bold mb-1 uppercase tracking-wider text-gray-600 flex items-center gap-1">
              <Activity size={10} /> Telemetry
            </div>
            <div className="flex-1 w-full min-h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dataHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="timestamp" hide />
                  <YAxis yAxisId="left" stroke="#6b7280" fontSize={9} tickFormatter={v => v.toFixed(1)} />
                  <YAxis yAxisId="right" orientation="right" stroke="#6b7280" fontSize={9} />
                  <Tooltip contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', fontSize: '10px', borderRadius: '6px' }} labelStyle={{ display: 'none' }} />
                  {config.chartConfig.map(ch => (
                    <Line key={ch.key} yAxisId={ch.yAxisId} type="monotone" dataKey={ch.key} stroke={ch.color} strokeWidth={1.5} dot={false} isAnimationActive={false} name={ch.label} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════
// Helper Components
// ═══════════════════════════════════════════════════════════════════════

const InfoCard: React.FC<{ label: string; value: string; accent: string }> = ({ label, value, accent }) => {
  const colors: Record<string, string> = {
    blue: 'text-blue-700 bg-blue-50 border-blue-200',
    purple: 'text-purple-700 bg-purple-50 border-purple-200',
    cyan: 'text-cyan-700 bg-cyan-50 border-cyan-200',
    green: 'text-green-700 bg-green-50 border-green-200',
    amber: 'text-amber-700 bg-amber-50 border-amber-200',
    red: 'text-red-700 bg-red-50 border-red-200',
    gray: 'text-gray-700 bg-gray-50 border-gray-200',
  };
  return (
    <div className={`rounded-lg border p-1.5 ${colors[accent] || colors.gray}`}>
      <div className="text-[8px] font-mono uppercase tracking-wider opacity-60">{label}</div>
      <div className="text-[10px] font-mono font-bold truncate">{value}</div>
    </div>
  );
};

export default ExperimentView;
