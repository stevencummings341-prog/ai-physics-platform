import React, { useEffect, useState, useCallback, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowLeft, Activity, Download, FileText } from 'lucide-react';
import { isaacService, type SimulationState } from '../services/isaacService';
import { ConnectionStatus, type TelemetryData, type ExperimentConfig } from '../types';
import WebRTCIsaacViewer from './WebRTCIsaacViewer';
import { SERVER_CONFIG } from '../config';
import { pdf } from '@react-pdf/renderer';
import LabReportPDF from './LabReportPDF';
import Exp7ReportPDF, { type Exp7Trial } from './Exp7ReportPDF';
import { generateExp7Charts } from '../utils/exp7Charts';
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
  const isExp7 = config.experimentNumber === '7';
  const isConnected = status === ConnectionStatus.CONNECTED;

  // ── Exp1: 4-trial state machine ──
  const [trialNum, setTrialNum] = useState(1);
  const [phase, setPhase] = useState<'idle' | 'spinning' | 'dropped' | 'recorded'>('idle');
  const [omegaI, setOmegaI] = useState(20);
  const [trials, setTrials] = useState<TrialData[]>([]);
  const [currentFAV, setCurrentFAV] = useState(0);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [spinCountdown, setSpinCountdown] = useState(0);
  const [selectedObject, setSelectedObject] = useState<DroppedObject>('Ring');
  const [ringMass, setRingMass] = useState(PHYS.ring.mass);
  const [diskMass, setDiskMass] = useState(PHYS.upperDisk.mass);
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
          setTimeout(() => { isaacService.requestSimulationState(); setLoadingProgress(100); setTimeout(() => setIsLoading(false), 300); }, 500);
        } else { setErrorMessage('Failed to enter experiment.'); }
      } catch { setStatus(ConnectionStatus.ERROR); setErrorMessage('Init error.'); }
    };
    init();

    const unsub1 = isaacService.onTelemetry((data) => {
      latestData.current = data;
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
      if (isExp7 && data.phase === 'settled') {
        setExp7PostV1(data.v1_final ?? data.v1 ?? 0);
        setExp7PostV2(data.v2_final ?? data.v2 ?? 0);
        setExp7Phase(prev => prev === 'running' ? 'settled' : prev);
      }
    });
    const unsub2 = isaacService.onSimulationState(setSimState);
    const poll = setInterval(() => { if (isaacService.isConnected()) isaacService.requestSimulationState(); }, 3000);
    return () => { unsub1(); unsub2(); clearInterval(poll); };
  }, [config.id, config.experimentNumber]);

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
      <LabReportPDF phys={PHYS} iri={IRI} trials={trials} chartImages={chartImages} />
    ).toBlob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Lab_Report_Angular_Momentum.pdf';
    a.click();
    URL.revokeObjectURL(url);
  }, [trials]);

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
    } else {
      isaacService.sendCommand(control.command, value);
    }
  }, [config.controls]);

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
            <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'LIVE' : 'OFF'}
            </div>
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
            <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              {isConnected ? 'LIVE' : 'OFF'}
            </div>
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
        <div className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full border ${isConnected ? 'border-green-400 text-green-700 bg-green-50' : 'border-red-400 text-red-700 bg-red-50'}`}>
          <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          {isConnected ? 'LIVE' : 'OFF'}
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
