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

const WebRTCIsaacViewer: React.FC<WebRTCIsaacViewerProps> = ({
  serverUrl = SERVER_CONFIG.httpUrl,
  usdPath,
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

  // Camera drag state — refs for synchronous access (avoids React batching delay)
  const isDraggingRef = useRef(false);
  const dragModeRef = useRef<'orbit' | 'pan' | null>(null);
  const lastPosRef = useRef({ x: 0, y: 0 });
  const pendingCmdRef = useRef<{ action: string; params: Record<string, number> } | null>(null);
  const rafRef = useRef<number | null>(null);

  const cleanupWsVideo = useCallback(() => {
    if (wsVideoRef.current) {
      wsVideoRef.current.close();
      wsVideoRef.current = null;
    }
    if (frameBlobUrlRef.current) {
      URL.revokeObjectURL(frameBlobUrlRef.current);
      frameBlobUrlRef.current = null;
    }
    if (wsFrameTimerRef.current) {
      clearInterval(wsFrameTimerRef.current);
      wsFrameTimerRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    cleanupWsVideo();
    setConnected(false);
    setConnecting(false);
    setTransport('none');
    connectionAttemptRef.current = false;
  }, [cleanupWsVideo]);

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
    cleanupWsVideo();
    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${window.location.host}/video_feed`;

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsVideoRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setConnecting(false);
      setTransport('ws-jpeg');
      setError(null);

      wsFrameCountRef.current = 0;
      wsFrameTimerRef.current = window.setInterval(() => {
        setStats(prev => ({ ...prev, fps: wsFrameCountRef.current, bitrate: 0 }));
        wsFrameCountRef.current = 0;
      }, 1000);
    };

    ws.onmessage = (event) => {
      wsFrameCountRef.current++;
      const blob = new Blob([event.data], { type: 'image/jpeg' });
      if (frameBlobUrlRef.current) URL.revokeObjectURL(frameBlobUrlRef.current);
      const url = URL.createObjectURL(blob);
      frameBlobUrlRef.current = url;
      if (imgRef.current) imgRef.current.src = url;
    };

    ws.onclose = () => { setConnected(false); setTransport('none'); };
    ws.onerror = () => { setConnected(false); setTransport('none'); setError('Video stream unavailable'); };
  }, [cleanupWsVideo]);

  // ── WebRTC connect with auto-fallback ──

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
          setStats({
            fps: Math.round(videoStats.framesPerSecond || 0),
            bitrate: parseFloat(((videoStats.bytesReceived * 8) / 1_000_000).toFixed(2)),
            packetsLost: videoStats.packetsLost || 0,
            latency: 0,
          });
        }
      } catch { /* noop */ }
    }, 1000);
  }, []);

  const connect = useCallback(async () => {
    if (connectionAttemptRef.current || connected) return;
    connectionAttemptRef.current = true;
    setConnecting(true);
    setError(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timeoutId = setTimeout(() => {
      if (abortControllerRef.current === controller) {
        controller.abort();
        setError('Connection timed out — falling back to WS video');
      }
    }, 20_000);

    try {
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
      });
      pcRef.current = pc;

      let iceSettled = false;
      const iceTimeout = setTimeout(() => {
        if (!iceSettled && pc.connectionState !== 'connected') {
          pc.close();
          pcRef.current = null;
          connectionAttemptRef.current = false;
          setConnecting(false);
          connectWsJpeg();
        }
      }, 8000);

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'connected') {
          iceSettled = true;
          clearTimeout(iceTimeout);
          setConnected(true);
          setConnecting(false);
          setTransport('webrtc');
          startStatsMonitoring();
        } else if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
          if (!iceSettled) {
            clearTimeout(iceTimeout);
            connectionAttemptRef.current = false;
            setConnecting(false);
            connectWsJpeg();
          } else {
            setConnected(false);
            if (connectionAttemptRef.current) setError('Connection lost');
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

      clearTimeout(timeoutId);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const answer = await response.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      connectionAttemptRef.current = false;
      setConnecting(false);
      connectWsJpeg();
    }
  }, [serverUrl, connected, connectWsJpeg, startStatsMonitoring]);

  useEffect(() => {
    const timer = setTimeout(() => connect(), 100);
    return () => { clearTimeout(timer); disconnect(); };
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
          <button onClick={() => { disconnect(); setTimeout(connect, 500); }} className="hover:text-white" title="Reconnect">
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
              onClick={connect}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 transition pointer-events-auto"
            >
              Retry Connection
            </button>
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
