/**
 * Runtime configuration for the frontend.
 *
 * All traffic is proxied through the Vite dev server on the same origin,
 * so only port 5173 needs to be reachable from the browser. Vite forwards:
 *   /offer, /camera, /load_usd → http://127.0.0.1:8080 (WebRTC HTTP)
 *   /ws                        → ws://127.0.0.1:30000  (WebSocket)
 */

const origin = typeof window !== "undefined"
  ? `${window.location.protocol}//${window.location.host}`
  : "";

const wsProtocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws";
const wsOrigin = typeof window !== "undefined"
  ? `${wsProtocol}://${window.location.host}`
  : "";

export const SERVER_CONFIG = {
  /** WebRTC signaling + camera HTTP API (proxied through Vite) */
  httpUrl: import.meta.env.VITE_HTTP_URL ?? origin,
  /** WebSocket control + telemetry (proxied through Vite at /ws) */
  wsUrl: import.meta.env.VITE_WS_URL ?? `${wsOrigin}/ws`,
} as const;
