// isaacService.ts
//
// Resilient WebSocket client for the Isaac Sim physics backend.
//
// Stability features (added 2026-04-27):
//   - Automatic reconnect with exponential backoff (1s → 2s → 4s … capped 30s)
//   - Application-layer heartbeat (ping every 15s) + 30s stale-data watchdog
//   - Tab-visibility aware: forces a fast reconnect when the tab is foregrounded
//   - Status subscribers (`onStatusChange`) so the UI can show reconnect spinners
//   - Replay of last `enter_experiment` after reconnect so simulation state is
//     restored without user intervention
//
import { ConnectionStatus, type TelemetryData } from '../types';
import { SERVER_CONFIG } from '../config';

export interface SimulationState {
  running: boolean;
  paused: boolean;
  time: number;
  step: number;
}

const HEARTBEAT_INTERVAL_MS = 15_000;     // ping every 15s
const STALE_TIMEOUT_MS      = 30_000;     // no message in 30s ⇒ force reconnect
const BASE_BACKOFF_MS       = 1_000;
const MAX_BACKOFF_MS        = 30_000;

class IsaacService {
  private status: ConnectionStatus = ConnectionStatus.DISCONNECTED;
  private subscribers: ((data: TelemetryData) => void)[] = [];
  private sceneInfoSubscribers: ((info: any) => void)[] = [];
  private simStateSubscribers: ((state: SimulationState) => void)[] = [];
  private customMessageSubscribers: ((msg: any) => void)[] = [];
  private statusSubscribers: ((status: ConnectionStatus) => void)[] = [];

  public ws: WebSocket | null = null;
  private useMock: boolean = false;
  private backendUrl: string = SERVER_CONFIG.wsUrl;

  // Mock state
  private activeExperimentId: string | null = null;
  private simulationInterval: any = null;
  private mockTime: number = 0;

  // ── Reconnect state ───────────────────────────────────────────────────
  private autoReconnect = true;             // disabled only on explicit force-disconnect
  private reconnectAttempt = 0;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private staleWatchdog: any = null;
  private lastMessageTime = 0;
  private lastEnteredExperiment: string | null = null;
  private connectingPromise: Promise<boolean> | null = null;
  private visibilityHandlerInstalled = false;
  private connectionAttemptToken = 0;

  constructor() {
    this.installVisibilityHandler();
  }

  // ── Public API ────────────────────────────────────────────────────────

  public connect(experimentId: string): Promise<boolean> {
    console.log(`[isaacService] connect(${experimentId})`);
    this.activeExperimentId = experimentId;
    this.autoReconnect = true;
    this.reconnectAttempt = 0;
    this.setStatus(ConnectionStatus.CONNECTING);

    if (this.useMock) {
      return this.connectMock();
    }
    return this.openSocket();
  }

  public disconnect(force: boolean = false) {
    if (!force) {
      console.log('[isaacService] keep-alive disconnect (no-op)');
      return;
    }
    console.log('[isaacService] force disconnect');
    this.autoReconnect = false;
    this.clearReconnectTimer();
    this.clearHeartbeat();
    this.clearStaleWatchdog();
    if (this.simulationInterval) clearInterval(this.simulationInterval);
    if (this.ws) {
      try { this.ws.close(1000, 'client disconnect'); } catch {}
      this.ws = null;
    }
    this.setStatus(ConnectionStatus.DISCONNECTED);
  }

  // ── Subscriptions ─────────────────────────────────────────────────────

  public onTelemetry(callback: (data: TelemetryData) => void) {
    this.subscribers.push(callback);
    return () => { this.subscribers = this.subscribers.filter(cb => cb !== callback); };
  }

  public onSceneInfo(callback: (info: any) => void) {
    this.sceneInfoSubscribers.push(callback);
    return () => { this.sceneInfoSubscribers = this.sceneInfoSubscribers.filter(cb => cb !== callback); };
  }

  public onSimulationState(callback: (state: SimulationState) => void) {
    this.simStateSubscribers.push(callback);
    return () => { this.simStateSubscribers = this.simStateSubscribers.filter(cb => cb !== callback); };
  }

  public onCustomMessage(callback: (msg: any) => void) {
    this.customMessageSubscribers.push(callback);
    return () => { this.customMessageSubscribers = this.customMessageSubscribers.filter(cb => cb !== callback); };
  }

  public onStatusChange(callback: (status: ConnectionStatus) => void) {
    this.statusSubscribers.push(callback);
    callback(this.status); // initial snapshot
    return () => { this.statusSubscribers = this.statusSubscribers.filter(cb => cb !== callback); };
  }

  // ── Status helpers ────────────────────────────────────────────────────

  public getStatus(): ConnectionStatus { return this.status; }

  public isConnected(): boolean {
    return this.status === ConnectionStatus.CONNECTED
      && this.ws !== null
      && this.ws.readyState === WebSocket.OPEN;
  }

  public getBackendUrl(): string { return this.backendUrl; }

  private setStatus(next: ConnectionStatus) {
    if (this.status === next) return;
    this.status = next;
    this.statusSubscribers.forEach(cb => { try { cb(next); } catch {} });
  }

  // ── Internal: socket lifecycle ────────────────────────────────────────

  private openSocket(): Promise<boolean> {
    if (this.connectingPromise) return this.connectingPromise;

    const myToken = ++this.connectionAttemptToken;
    this.connectingPromise = new Promise<boolean>((resolve) => {
      try {
        // Drop any zombie socket without triggering its onclose reconnect.
        if (this.ws) {
          try { this.ws.onopen = null; this.ws.onmessage = null; this.ws.onerror = null; this.ws.onclose = null; this.ws.close(); } catch {}
          this.ws = null;
        }
        const ws = new WebSocket(this.backendUrl);
        this.ws = ws;
        let resolved = false;

        const handshakeTimeout = setTimeout(() => {
          if (!resolved) {
            resolved = true;
            console.warn('[isaacService] handshake timed out');
            try { ws.close(); } catch {}
            this.scheduleReconnect();
            resolve(false);
          }
        }, 10_000);

        ws.onopen = () => {
          if (this.connectionAttemptToken !== myToken) return; // superseded
          clearTimeout(handshakeTimeout);
          console.log('[isaacService] WS open');
          this.reconnectAttempt = 0;
          this.lastMessageTime = Date.now();
          this.setStatus(ConnectionStatus.CONNECTED);
          this.startHeartbeat();
          this.startStaleWatchdog();
          // Send INIT, then replay state if we are reconnecting.
          this.sendRaw({
            type: 'INIT',
            experimentId: this.activeExperimentId,
          });
          if (this.lastEnteredExperiment) {
            this.sendRaw({
              type: 'enter_experiment',
              experiment_id: this.lastEnteredExperiment,
            });
          }
          if (!resolved) {
            resolved = true;
            resolve(true);
          }
        };

        ws.onmessage = (event) => {
          this.lastMessageTime = Date.now();
          try {
            const payload = JSON.parse(event.data);
            this.dispatchMessage(payload);
          } catch (e) {
            console.error('[isaacService] failed to parse message', e);
          }
        };

        ws.onerror = (err) => {
          console.warn('[isaacService] WS error', err);
        };

        ws.onclose = (ev) => {
          if (this.connectionAttemptToken !== myToken) return; // superseded
          clearTimeout(handshakeTimeout);
          this.clearHeartbeat();
          this.clearStaleWatchdog();
          console.log(`[isaacService] WS closed code=${ev.code} reason="${ev.reason}"`);
          this.ws = null;
          if (!resolved) {
            resolved = true;
            resolve(false);
          }
          if (this.autoReconnect) {
            this.scheduleReconnect();
          } else {
            this.setStatus(ConnectionStatus.DISCONNECTED);
          }
        };
      } catch (e) {
        console.error('[isaacService] openSocket threw', e);
        this.scheduleReconnect();
        resolve(false);
      }
    });

    this.connectingPromise.finally(() => {
      this.connectingPromise = null;
    });
    return this.connectingPromise;
  }

  private dispatchMessage(payload: any) {
    if (!payload || typeof payload !== 'object') return;
    switch (payload.type) {
      case 'telemetry':
        this.subscribers.forEach(cb => { try { cb(payload.data); } catch {} });
        return;
      case 'simulation_state':
        this.simStateSubscribers.forEach(cb => { try { cb(payload); } catch {} });
        return;
      case 'scene_info':
      case 'scene_status':
        this.sceneInfoSubscribers.forEach(cb => { try { cb(payload.data); } catch {} });
        return;
      case 'connected':
        console.log('[isaacService] server hello:', payload.message);
        return;
      case 'pong':
        return; // heartbeat reply, tracked by lastMessageTime
      case 'command_result':
        return;
      case 'error':
        console.error('[isaacService] server error:', payload.message);
        // Still notify custom subscribers so UI can react.
        this.customMessageSubscribers.forEach(cb => { try { cb(payload); } catch {} });
        return;
    }
    // Forward any experiment-specific messages (e.g. exp4_progress, exp6_report_ready, …).
    if (/^exp\d+_(report_(progress|ready)|progress|report_ready)$/.test(payload.type)
        || payload.type === 'exp2_progress'
        || payload.type === 'experiment_entered'
        || payload.type === 'camera_switched') {
      this.customMessageSubscribers.forEach(cb => { try { cb(payload); } catch {} });
    }
  }

  private scheduleReconnect() {
    if (!this.autoReconnect) return;
    if (this.reconnectTimer) return;
    const delay = Math.min(
      MAX_BACKOFF_MS,
      BASE_BACKOFF_MS * Math.pow(2, this.reconnectAttempt),
    ) + Math.floor(Math.random() * 250); // small jitter to avoid thundering herd
    this.reconnectAttempt++;
    this.setStatus(ConnectionStatus.RECONNECTING);
    console.log(`[isaacService] reconnect attempt ${this.reconnectAttempt} in ${delay}ms`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.openSocket();
    }, delay);
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeat() {
    this.clearHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
        } catch (e) {
          console.warn('[isaacService] ping failed', e);
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private clearHeartbeat() {
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
  }

  private startStaleWatchdog() {
    this.clearStaleWatchdog();
    this.staleWatchdog = setInterval(() => {
      if (!this.ws) return;
      if (this.ws.readyState !== WebSocket.OPEN) return;
      const idle = Date.now() - this.lastMessageTime;
      if (idle > STALE_TIMEOUT_MS) {
        console.warn(`[isaacService] no messages for ${idle}ms — forcing reconnect`);
        try { this.ws.close(4000, 'stale'); } catch {}
      }
    }, 5_000);
  }

  private clearStaleWatchdog() {
    if (this.staleWatchdog) { clearInterval(this.staleWatchdog); this.staleWatchdog = null; }
  }

  private installVisibilityHandler() {
    if (this.visibilityHandlerInstalled) return;
    if (typeof document === 'undefined') return;
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Tab came back: if we are not connected, kick a fast retry.
        if (this.status !== ConnectionStatus.CONNECTED && this.autoReconnect) {
          console.log('[isaacService] tab visible — fast reconnect');
          this.reconnectAttempt = 0;
          this.clearReconnectTimer();
          this.openSocket();
        } else if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          // Send a fresh ping so the stale-watchdog clock resets immediately.
          try { this.ws.send(JSON.stringify({ type: 'ping', ts: Date.now() })); } catch {}
        }
      }
    });
    this.visibilityHandlerInstalled = true;
  }

  // ── Mock connection ──────────────────────────────────────────────────

  private connectMock(): Promise<boolean> {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.setStatus(ConnectionStatus.CONNECTED);
        this.startMockDataStream();
        resolve(true);
      }, 800);
    });
  }

  // ── Send helpers ─────────────────────────────────────────────────────

  private sendRaw(msg: any): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try { this.ws.send(JSON.stringify(msg)); return true; } catch (e) {
        console.warn('[isaacService] send failed', e);
        return false;
      }
    }
    return false;
  }

  // ── USD scene operations ─────────────────────────────────────────────

  public async loadUSDScene(experimentNumber: string): Promise<boolean> {
    if (!this.isConnected()) {
      console.error('WebSocket not connected');
      return false;
    }
    return new Promise((resolve) => {
      const message = { type: 'load_usd', experiment_id: experimentNumber };
      console.log('[isaacService] sending load_usd', message);
      this.sendRaw(message);
      setTimeout(() => resolve(true), 2000);
    });
  }

  public async enterExperiment(experimentNumber: string): Promise<boolean> {
    if (!this.isConnected()) {
      console.error('WebSocket not connected');
      return false;
    }
    return new Promise((resolve) => {
      const message = { type: 'enter_experiment', experiment_id: experimentNumber };
      console.log('[isaacService] entering experiment', experimentNumber);
      // Remember so we can replay after reconnect.
      this.lastEnteredExperiment = experimentNumber;

      const responseHandler = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'experiment_entered' && payload.experiment_id === experimentNumber) {
            this.ws?.removeEventListener('message', responseHandler);
            resolve(true);
          } else if (payload.type === 'error') {
            console.error('[isaacService] enter_experiment failed:', payload.message);
            this.ws?.removeEventListener('message', responseHandler);
            resolve(false);
          }
        } catch {}
      };
      this.ws?.addEventListener('message', responseHandler);
      this.sendRaw(message);
      setTimeout(() => {
        this.ws?.removeEventListener('message', responseHandler);
        resolve(true);
      }, 2000);
    });
  }

  public async switchCamera(experimentNumber: string): Promise<boolean> {
    if (!this.isConnected()) {
      console.error('WebSocket not connected');
      return false;
    }
    return new Promise((resolve) => {
      const message = { type: 'switch_camera', experiment_id: experimentNumber };
      const responseHandler = (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'camera_switched' && payload.experiment_id === experimentNumber) {
            this.ws?.removeEventListener('message', responseHandler);
            resolve(true);
          } else if (payload.type === 'error') {
            this.ws?.removeEventListener('message', responseHandler);
            resolve(false);
          }
        } catch {}
      };
      this.ws?.addEventListener('message', responseHandler);
      this.sendRaw(message);
      setTimeout(() => {
        this.ws?.removeEventListener('message', responseHandler);
        resolve(true);
      }, 2000);
    });
  }

  public async getSceneInfo(): Promise<any> {
    if (!this.isConnected()) return null;
    return new Promise((resolve) => {
      this.sendRaw({ command: 'get_scene_info' });
      setTimeout(() => resolve({ stage: 'unknown', root_prims_count: 0 }), 1000);
    });
  }

  // ── Simulation control ──────────────────────────────────────────────

  public async startSimulation(): Promise<void> {
    this.sendRaw({ type: 'start_simulation' });
  }

  public async pauseSimulation(): Promise<void> {
    this.sendRaw({ type: 'stop_simulation' });
  }

  public async resetSimulation(): Promise<void> {
    this.sendRaw({ type: 'reset' });
  }

  public async stopSimulation(): Promise<void> {
    this.sendRaw({ type: 'stop_simulation' });
  }

  public setRunning(running: boolean): void {
    if (running) this.startSimulation(); else this.pauseSimulation();
  }

  public resetExperiment(): void { this.resetSimulation(); }

  public sendCommand(command: string, payload?: any) {
    if (!this.ws || this.status !== ConnectionStatus.CONNECTED) {
      console.warn(`[CMD] dropped (not connected): ${command}`);
      return;
    }
    let message: any;
    if (payload === undefined || payload === null) {
      message = { type: command };
    } else if (typeof payload === 'number' || typeof payload === 'boolean') {
      message = { type: command, value: payload };
    } else if (typeof payload === 'object') {
      message = { type: command, ...payload };
    } else {
      message = { type: command, value: payload };
    }
    this.sendRaw(message);
  }

  public requestSimulationState(): void {
    this.sendRaw({ type: 'get_simulation_state' });
  }

  // ── Mock data generator ──────────────────────────────────────────────

  private startMockDataStream() {
    this.mockTime = 0;
    this.simulationInterval = setInterval(() => {
      this.mockTime += 0.016;
      const t = this.mockTime;
      let data: TelemetryData = { timestamp: Date.now(), fps: 60 + Math.random() * 5 };
      switch (this.activeExperimentId) {
        case 'exp-01-cartpole':
          data.pole_angle = Math.sin(t) * 0.1 + (Math.random() - 0.5) * 0.02;
          data.cart_velocity = Math.cos(t) * 0.5;
          break;
        case 'exp-02-franka':
          data.end_effector_vel = Math.abs(Math.sin(t * 2));
          data.gripper_force = t % 5 > 2.5 ? 20 : 0;
          break;
        case 'exp-03-quadcopter':
          data.altitude = 5 + Math.sin(t * 0.5) * 2;
          data.battery = Math.max(0, 100 - t * 0.5);
          break;
        case 'exp-04-anymal':
          data.body_velocity = 0.5 + (Math.random() - 0.5) * 0.1;
          data.slip_ratio = Math.abs(Math.random() * 0.1);
          break;
        case 'exp-05-humanoid':
          data.com_height = 0.9 + Math.cos(t * 10) * 0.02;
          data.energy = 200 + Math.random() * 50;
          break;
        case 'exp-06-softbody':
          data.deformation = Math.abs(Math.sin(t * 5)) * 10;
          data.stress = data.deformation * 500;
          break;
        case 'exp-07-amr':
          data.lidar_points = 15000 + Math.random() * 1000;
          data.path_error = Math.abs(Math.sin(t * 0.1)) * 0.2;
          break;
        case 'exp-08-shadow':
          data.cube_rot_vel = 1.5 + Math.random() * 0.2;
          data.finger_contacts = Math.floor(3 + Math.random() * 2);
          break;
        default:
          data.value = Math.random();
      }
      this.subscribers.forEach(cb => { try { cb(data); } catch {} });
    }, 50);
  }
}

export const isaacService = new IsaacService();
