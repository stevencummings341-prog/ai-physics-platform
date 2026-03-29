/**
 * Runtime configuration for the frontend.
 *
 * In development (`npm run dev`) values come from .env or defaults here.
 * In production the Vite build bakes import.meta.env.VITE_* at compile time,
 * or the values fall back to window.location.hostname so the page works
 * when served from the same machine as the Isaac Sim server.
 */

const fallbackHost = typeof window !== "undefined" ? window.location.hostname : "localhost";

export const SERVER_CONFIG = {
  /** WebRTC signaling + camera HTTP API */
  httpUrl: import.meta.env.VITE_HTTP_URL ?? `http://${fallbackHost}:8080`,
  /** WebSocket control + telemetry */
  wsUrl: import.meta.env.VITE_WS_URL ?? `ws://${fallbackHost}:30000`,
} as const;
