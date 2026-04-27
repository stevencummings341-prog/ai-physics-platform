import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Wifi, WifiOff, Activity, RefreshCw } from 'lucide-react';
import { SERVER_CONFIG } from '../config';

interface WebRTCIsaacViewerProps {
  serverUrl?: string;
  usdPath?: string;
  className?: string;
}

interface ConnectionStats {
  fps: number;
  bitrate: number;
  packetsLost: number;
  latency: number;
}

type TransportMode = 'webrtc' | 'ws-jpeg' | 'none';

// ── Tunables (kept here for easy operations review) ─────────────────────
const ICE_GATHER_TIMEOUT_MS    = 8_000;     // initial WebRTC answer wait
const SDP_FETCH_TIMEOUT_MS     = 20_000;    // overall handshake budget
const ICE_RESTART_AFTER_MS     = 2_500;     // disconnected → try restartIce()
const FULL_RECONNECT_AFTER_MS  = 8_000;     // disconnected too long → full reconnect
const STALL_WATCHDOG_MS        = 6_000;     // 0 fps for this long ⇒ reconnect
const STALL_CHECK_INTERVAL_MS  = 2_000;
const FALLBACK_UPGRADE_MS      = 60_000;    // try WebRTC again from WS-JPEG
const FALLBACK_RETRY_BACKOFF_MS = 5_000;    // WS-JPEG dropped → retry quickly

const WebRTCIsaacViewer: React.FC<WebRTCIsaacViewerProps> = ({
  serverUrl = SERVER_CONFIG.httpUrl,
  className = ''
}) => {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transport, setTransport] = useState<TransportMode>('none');
  const [stats, setStats] = useState<ConnectionStats>({ fps: 0, bitrate: 0, packetsLost: 0, latency: 0 });

  const videoRef = useRef<HTMLVideoElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const statsIntervalRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const connectionAttemptRef = useRef(false);
  const wsVideoRef = useRef<WebSocket | null>(null);
  const frameBlobUrlRef = useRef<string | null>(null);
  const wsFrameCountRef = useRef(0);
  const wsFrameTimerRef = useRef<number | null>(null);

  // Stability state machine
  const transportRef = useRef<TransportMode>('none');
  const lastFrameStatsTime = useRef(Date.now());
  const lastFpsValue = useRef(0);
  // Monotonic counters from the inbound-rtp report.  framesDecoded only
  // ever increases as long as the receiver is decoding *anything* — it
  // is a much more reliable liveness indicator than framesPerSecond,
  // which can drop to 0 when the encoder produces zero-motion frames
  // (which is exactly what happens when the Isaac viewport is idle and
  // the scene isn't moving).  Tracking this counter avoids a
  // false-positive disconnect every ~6 s during quiet experiment phases.
  const lastFramesDecoded = useRef(0);
  const lastBytesReceived = useRef(0);
  const stallCheckRef = useRef<number | null>(null);
  const iceRestartTimerRef = useRef<number | null>(null);
  const fullReconnectTimerRef = useRef<number | null>(null);
  const fallbackUpgradeTimerRef = useRef<number | null>(null);
  const reconnectInProgressRef = useRef(false);
  const unmountedRef = useRef(false);

  // Camera drag state — refs for synchronous access (avoids React batching delay)
  const isDraggingRef = useRef(false);
  const dragModeRef = useRef<'orbit' | 'pan' | null>(null);
  const lastPosRef = useRef({ x: 0, y: 0 });
  const pendingCmdRef = useRef<{ action: string; params: Record<string, number> } | null>(null);
  const rafRef = useRef<number | null>(null);

  // ── Helpers ──────────────────────────────────────────────────────────

  const setTransportSafe = useCallback((m: TransportMode) => {
    transportRef.current = m;
    setTransport(m);
  }, []);

  const clearTimers = useCallback(() => {
    if (iceRestartTimerRef.current) { window.clearTimeout(iceRestartTimerRef.current); iceRestartTimerRef.current = null; }
    if (fullReconnectTimerRef.current) { window.clearTimeout(fullReconnectTimerRef.current); fullReconnectTimerRef.current = null; }
    if (fallbackUpgradeTimerRef.current) { window.clearTimeout(fallbackUpgradeTimerRef.current); fallbackUpgradeTimerRef.current = null; }
    if (stallCheckRef.current) { window.clearInterval(stallCheckRef.current); stallCheckRef.current = null; }
  }, []);

  const cleanupWsVideo = useCallback(() => {
    if (wsVideoRef.current) {
      try {
        wsVideoRef.current.onopen = null;
        wsVideoRef.current.onmessage = null;
        wsVideoRef.current.onerror = null;
        wsVideoRef.current.onclose = null;
        wsVideoRef.current.close();
      } catch {}
      wsVideoRef.current = null;
    }
    if (frameBlobUrlRef.current) {
      try { URL.revokeObjectURL(frameBlobUrlRef.current); } catch {}
      frameBlobUrlRef.current = null;
    }
    if (wsFrameTimerRef.current) {
      window.clearInterval(wsFrameTimerRef.current);
      wsFrameTimerRef.current = null;
    }
  }, []);

  const closePeer = useCallback(() => {
    if (pcRef.current) {
      try { pcRef.current.close(); } catch {}
      pcRef.current = null;
    }
    if (statsIntervalRef.current) {
      window.clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
    if (abortControllerRef.current) {
      try { abortControllerRef.current.abort(); } catch {}
      abortControllerRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const disconnect = useCallback(() => {
    clearTimers();
    closePeer();
    cleanupWsVideo();
    setConnected(false);
    setConnecting(false);
    setTransportSafe('none');
    connectionAttemptRef.current = false;
    reconnectInProgressRef.current = false;
  }, [clearTimers, closePeer, cleanupWsVideo, setTransportSafe]);

  // ── Camera control (throttled via rAF, fire-and-forget) ──

  const flushCamera = useCallback(() => {
    rafRef.current = null;
    const cmd = pendingCmdRef.current;
    if (!cmd) return;
    pendingCmdRef.current = null;
    fetch(`${serverUrl}/camera`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: cmd.action, ...cmd.params }),
    }).catch(() => {});
  }, [serverUrl]);

  const queueCamera = useCallback((action: string, params: Record<string, number>) => {
    pendingCmdRef.current = { action, params };
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(flushCamera);
    }
  }, [flushCamera]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDraggingRef.current = true;
    lastPosRef.current = { x: e.clientX, y: e.clientY };
    dragModeRef.current = e.button === 0 ? 'orbit' : e.button === 2 ? 'pan' : null;
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingRef.current || !dragModeRef.current) return;
    const dx = (e.clientX - lastPosRef.current.x) * 1.5;
    const dy = (e.clientY - lastPosRef.current.y) * 1.5;
    lastPosRef.current = { x: e.clientX, y: e.clientY };
    if (dragModeRef.current === 'orbit') {
      queueCamera('orbit', { deltaX: dx, deltaY: dy });
    } else {
      queueCamera('pan', { deltaX: -dx, deltaY: dy });
    }
  }, [queueCamera]);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    dragModeRef.current = null;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    queueCamera('zoom', { delta: e.deltaY > 0 ? 3 : -3 });
  }, [queueCamera]);

  // ── WebSocket JPEG fallback ──

  const connectWsJpeg = useCallback(() => {
    if (unmountedRef.current) return;
    cleanupWsVideo();
    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${window.location.host}/video_feed`;

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsVideoRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) { try { ws.close(); } catch {}; return; }
      setConnected(true);
      setConnecting(false);
      setTransportSafe('ws-jpeg');
      setError(null);
      lastFrameStatsTime.current = Date.now();

      wsFrameCountRef.current = 0;
      wsFrameTimerRef.current = window.setInterval(() => {
        const fps = wsFrameCountRef.current;
        wsFrameCountRef.current = 0;
        lastFpsValue.current = fps;
        if (fps > 0) lastFrameStatsTime.current = Date.now();
        setStats(prev => ({ ...prev, fps, bitrate: 0 }));
      }, 1000);

      // Periodically attempt to upgrade back to WebRTC (it has lower latency).
      if (fallbackUpgradeTimerRef.current) window.clearTimeout(fallbackUpgradeTimerRef.current);
      fallbackUpgradeTimerRef.current = window.setTimeout(() => {
        if (transportRef.current === 'ws-jpeg' && !unmountedRef.current) {
          console.log('[viewer] periodic upgrade attempt: WS-JPEG → WebRTC');
          attemptReconnect('upgrade-to-webrtc');
        }
      }, FALLBACK_UPGRADE_MS);
    };

    ws.onmessage = (event) => {
      wsFrameCountRef.current++;
      try {
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        if (frameBlobUrlRef.current) URL.revokeObjectURL(frameBlobUrlRef.current);
        const url = URL.createObjectURL(blob);
        frameBlobUrlRef.current = url;
        if (imgRef.current) imgRef.current.src = url;
      } catch (e) {
        console.warn('[viewer] WS-JPEG decode failed', e);
      }
    };

    ws.onclose = () => {
      console.warn('[viewer] WS-JPEG closed');
      setConnected(false);
      setTransportSafe('none');
      // Fast retry — JPEG fallback is meant to be reliable.
      if (!unmountedRef.current) {
        window.setTimeout(() => {
          if (!unmountedRef.current && transportRef.current !== 'webrtc') {
            connectWsJpeg();
          }
        }, FALLBACK_RETRY_BACKOFF_MS);
      }
    };
    ws.onerror = () => {
      console.warn('[viewer] WS-JPEG error');
      setConnected(false);
      setTransportSafe('none');
      setError('Video stream unavailable');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanupWsVideo, setTransportSafe]);

  // ── Stats and stall watchdog ──

  const startStatsMonitoring = useCallback(() => {
    if (statsIntervalRef.current) return;
    statsIntervalRef.current = window.setInterval(async () => {
      if (!pcRef.current) return;
      try {
        const rtcStats = await pcRef.current.getStats();
        let videoStats: any = null;
        rtcStats.forEach(report => {
          if (report.type === 'inbound-rtp' && report.kind === 'video') videoStats = report;
        });
        if (videoStats) {
          const fps = Math.round(videoStats.framesPerSecond || 0);
          lastFpsValue.current = fps;

          // Liveness: any forward progress on framesDecoded or
          // bytesReceived means the stream is alive, even if fps==0
          // because the encoder is sending zero-motion deltas.
          const framesDecoded = Number(videoStats.framesDecoded || 0);
          const bytesReceived = Number(videoStats.bytesReceived || 0);
          if (framesDecoded > lastFramesDecoded.current
              || bytesReceived > lastBytesReceived.current) {
            lastFrameStatsTime.current = Date.now();
            lastFramesDecoded.current = framesDecoded;
            lastBytesReceived.current = bytesReceived;
          }

          setStats({
            fps,
            bitrate: parseFloat(((bytesReceived * 8) / 1_000_000).toFixed(2)),
            packetsLost: videoStats.packetsLost || 0,
            latency: 0,
          });
        }
      } catch { /* noop */ }
    }, 1000);
  }, []);

  const startStallWatchdog = useCallback(() => {
    if (stallCheckRef.current) window.clearInterval(stallCheckRef.current);
    stallCheckRef.current = window.setInterval(() => {
      if (transportRef.current === 'none') return;
      // `lastFrameStatsTime` is updated whenever framesDecoded OR
      // bytesReceived advances (see startStatsMonitoring above).
      // We deliberately do NOT gate on fps==0: a static viewport
      // (encoder producing zero-motion deltas) routinely shows
      // framesPerSecond=0 even though the stream is healthy.
      const idle = Date.now() - lastFrameStatsTime.current;
      if (idle > STALL_WATCHDOG_MS) {
        console.warn(`[viewer] no frames/bytes for ${idle}ms — reconnecting`);
        attemptReconnect('stall');
      }
    }, STALL_CHECK_INTERVAL_MS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Reconnect flow (defined after connect so it can recurse) ──

  const connect = useCallback(async () => {
    if (unmountedRef.current) return;
    if (connectionAttemptRef.current) return;
    connectionAttemptRef.current = true;
    setConnecting(true);
    setError(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const overallTimeout = window.setTimeout(() => {
      if (abortControllerRef.current === controller) {
        try { controller.abort(); } catch {}
        setError('Connection timed out — falling back to WS video');
      }
    }, SDP_FETCH_TIMEOUT_MS);

    try {
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
          { urls: 'stun:stun.cloudflare.com:3478' },
        ],
      });
      pcRef.current = pc;

      let iceSettled = false;
      const iceTimeout = window.setTimeout(() => {
        if (!iceSettled && pc.connectionState !== 'connected') {
          console.warn('[viewer] ICE didn\'t settle — falling back to WS-JPEG');
          try { pc.close(); } catch {}
          pcRef.current = null;
          connectionAttemptRef.current = false;
          setConnecting(false);
          connectWsJpeg();
        }
      }, ICE_GATHER_TIMEOUT_MS);

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        console.log(`[viewer] pc state: ${s}`);
        if (s === 'connected') {
          iceSettled = true;
          window.clearTimeout(iceTimeout);
          if (iceRestartTimerRef.current) { window.clearTimeout(iceRestartTimerRef.current); iceRestartTimerRef.current = null; }
          if (fullReconnectTimerRef.current) { window.clearTimeout(fullReconnectTimerRef.current); fullReconnectTimerRef.current = null; }
          setConnected(true);
          setConnecting(false);
          setTransportSafe('webrtc');
          setError(null);
          lastFrameStatsTime.current = Date.now();
          // Counters are per-PeerConnection — reset them so the next
          // sample doesn't see a "negative delta" against an old PC.
          lastFramesDecoded.current = 0;
          lastBytesReceived.current = 0;
          startStatsMonitoring();
          startStallWatchdog();
        } else if (s === 'disconnected') {
          // Two-stage recovery: first try ICE restart, then full reconnect.
          if (!iceRestartTimerRef.current) {
            iceRestartTimerRef.current = window.setTimeout(() => {
              iceRestartTimerRef.current = null;
              if (pcRef.current && pcRef.current.connectionState === 'disconnected') {
                console.warn('[viewer] disconnected too long — restarting ICE');
                tryIceRestart();
              }
            }, ICE_RESTART_AFTER_MS);
          }
          if (!fullReconnectTimerRef.current) {
            fullReconnectTimerRef.current = window.setTimeout(() => {
              fullReconnectTimerRef.current = null;
              if (pcRef.current && pcRef.current.connectionState !== 'connected') {
                console.warn('[viewer] disconnected — full reconnect');
                attemptReconnect('disconnected');
              }
            }, FULL_RECONNECT_AFTER_MS);
          }
        } else if (s === 'failed' || s === 'closed') {
          window.clearTimeout(iceTimeout);
          if (!iceSettled) {
            connectionAttemptRef.current = false;
            setConnecting(false);
            connectWsJpeg();
          } else if (s === 'failed') {
            console.warn('[viewer] pc failed — full reconnect');
            attemptReconnect('failed');
          } else {
            // s === 'closed' && iceSettled — the peer was closed after a
            // successful handshake (e.g. backend restarted, ICE pruned).
            // Without this branch the UI would still show "ONLINE" but
            // the video element would be frozen.  Trigger a reconnect.
            console.warn('[viewer] pc closed after handshake — full reconnect');
            attemptReconnect('closed');
          }
        }
      };

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          const stream = event.streams[0];
          if (videoRef.current.srcObject !== stream) {
            videoRef.current.srcObject = stream;
            videoRef.current.play().catch(e => {
              if (e.name !== 'AbortError') console.error('Video play error:', e);
            });
          }
        }
      };

      pc.addTransceiver('video', { direction: 'recvonly' });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const response = await fetch(`${serverUrl}/offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: pc.localDescription?.sdp, type: pc.localDescription?.type }),
        signal: controller.signal,
      });

      window.clearTimeout(overallTimeout);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const answer = await response.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err: any) {
      window.clearTimeout(overallTimeout);
      console.warn('[viewer] WebRTC connect failed:', err?.message ?? err);
      if (pcRef.current) {
        try { pcRef.current.close(); } catch {}
        pcRef.current = null;
      }
      connectionAttemptRef.current = false;
      setConnecting(false);
      connectWsJpeg();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverUrl, connectWsJpeg, startStatsMonitoring, startStallWatchdog, setTransportSafe]);

  const tryIceRestart = useCallback(async () => {
    const pc = pcRef.current;
    if (!pc) return;
    try {
      const offer = await pc.createOffer({ iceRestart: true });
      await pc.setLocalDescription(offer);
      const resp = await fetch(`${serverUrl}/offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: pc.localDescription?.sdp, type: pc.localDescription?.type }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const answer = await resp.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
      console.log('[viewer] ICE restart sent');
    } catch (e) {
      console.warn('[viewer] ICE restart failed — falling back to full reconnect', e);
      attemptReconnect('ice-restart-failed');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverUrl]);

  const attemptReconnect = useCallback((reason: string) => {
    if (unmountedRef.current) return;
    if (reconnectInProgressRef.current) return;
    reconnectInProgressRef.current = true;
    console.log(`[viewer] reconnect (${reason})`);
    clearTimers();
    closePeer();
    cleanupWsVideo();
    setConnected(false);
    setConnecting(true);
    setTransportSafe('none');
    connectionAttemptRef.current = false;
    // Small back-off so we don't hammer the server during a restart.
    window.setTimeout(() => {
      reconnectInProgressRef.current = false;
      if (!unmountedRef.current) connect();
    }, 600);
  }, [clearTimers, closePeer, cleanupWsVideo, connect, setTransportSafe]);

  // ── Mount / unmount ──

  useEffect(() => {
    unmountedRef.current = false;
    const timer = window.setTimeout(() => connect(), 100);
    // Re-establish video when the tab becomes visible again
    const onVis = () => {
      if (document.visibilityState !== 'visible') return;
      if (!connected && !connecting && !unmountedRef.current) {
        console.log('[viewer] tab visible — fast retry');
        attemptReconnect('visibility');
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      unmountedRef.current = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVis);
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const transportLabel = transport === 'webrtc' ? 'WebRTC' : transport === 'ws-jpeg' ? 'WS-JPEG' : '';

  return (
    <div className={`relative flex flex-col w-full h-full bg-black rounded-lg overflow-hidden ${className}`}>
      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800 text-xs font-mono">
        <div className="flex items-center gap-2">
          {connected ? <Wifi size={14} className="text-green-500" /> : <WifiOff size={14} className="text-red-500" />}
          <span className={connected ? 'text-green-500' : 'text-red-500'}>
            {connected ? 'ONLINE' : connecting ? 'CONNECTING...' : 'OFFLINE'}
          </span>
          {transportLabel && <span className="text-gray-500 ml-1">({transportLabel})</span>}
        </div>
        <div className="flex items-center gap-4 text-gray-400">
          <span>{stats.fps} FPS</span>
          {transport === 'webrtc' && <span>{stats.bitrate} Mbps</span>}
          <button
            onClick={() => attemptReconnect('manual')}
            className="hover:text-white" title="Reconnect"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {/* Viewport with camera interaction */}
      <div
        className="flex-1 relative overflow-hidden"
        style={{ cursor: isDraggingRef.current ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        onContextMenu={(e) => e.preventDefault()}
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-contain pointer-events-none"
          style={{ display: transport === 'webrtc' ? 'block' : 'none' }}
        />
        <img
          ref={imgRef}
          alt="Isaac Sim viewport"
          className="w-full h-full object-contain pointer-events-none"
          style={{ display: transport === 'ws-jpeg' ? 'block' : 'none' }}
        />

        {!connected && !connecting && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 text-gray-400 pointer-events-none">
            <Activity size={48} className="mb-4 opacity-50" />
            <p>{error || 'Connection Failed'}</p>
            <button
              onClick={() => attemptReconnect('manual-retry')}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 transition pointer-events-auto"
            >
              Retry Connection
            </button>
          </div>
        )}

        {connecting && (
          <div className="absolute top-2 right-2 text-[10px] font-mono text-yellow-300/90 select-none pointer-events-none bg-black/40 px-2 py-1 rounded">
            Reconnecting…
          </div>
        )}

        {/* Camera hint overlay */}
        {connected && (
          <div className="absolute bottom-2 left-2 text-[10px] font-mono text-white/40 select-none pointer-events-none">
            LMB: Orbit &middot; RMB: Pan &middot; Scroll: Zoom
          </div>
        )}
      </div>
    </div>
  );
};

export default WebRTCIsaacViewer;
