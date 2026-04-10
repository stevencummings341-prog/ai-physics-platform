"""UDP receiver for Meta Quest 3S hand tracking data.

Ported from ``vr/visionpro_isaaclab_advanced.py`` with all Isaac Lab
dependencies removed so it can run inside the Isaac Sim WebRTC server.

Protocol
--------
Quest sends UDP JSON packets at ~60 Hz to port ``VR_UDP_PORT`` (default 8888).
Each packet::

    {
      "left_hand":  {"position":[x,y,z], "rotation":[w,x,y,z],
                     "pinch_strength":0.0-1.0, "is_tracking":true/false},
      "right_hand": { ... },
      "timestamp":  <unix float>
    }

Coordinates arrive **already transformed** to Isaac Lab/Sim convention
(Z-up, X-forward) by the Quest C# script.

The receiver sends periodic ACK heartbeats back to the Quest so the
headset UI can confirm the server is alive.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HandSnapshot:
    """Immutable snapshot of one hand's state at a point in time."""
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))
    pinch_strength: float = 0.0
    is_tracking: bool = False
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# EMA position smoother
# ---------------------------------------------------------------------------

class _PositionSmoother:
    """Exponential Moving Average filter for hand position."""

    def __init__(self, alpha: float = 0.3):
        self._alpha = alpha
        self._smoothed: np.ndarray | None = None

    def update(self, pos: np.ndarray) -> np.ndarray:
        if self._smoothed is None:
            self._smoothed = pos.copy()
        else:
            self._smoothed = self._alpha * pos + (1 - self._alpha) * self._smoothed
        return self._smoothed.copy()

    def reset(self) -> None:
        self._smoothed = None


# ---------------------------------------------------------------------------
# VR Hand Receiver
# ---------------------------------------------------------------------------

class VRHandReceiver:
    """Threaded UDP receiver for Meta Quest hand tracking data.

    Parameters
    ----------
    host : str
        Bind address (``0.0.0.0`` to listen on all interfaces).
    port : int
        UDP port to listen on.
    timeout : float
        Socket receive timeout in seconds.
    update_rate : float
        Expected packet rate from the Quest (Hz).  Used for velocity
        estimation fallback and stale-tracking detection.
    smoothing : bool
        Enable EMA position smoothing.
    smoothing_alpha : float
        Smoothing factor (0 = no change, 1 = raw data).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8888,
        timeout: float = 0.1,
        update_rate: float = 60.0,
        smoothing: bool = True,
        smoothing_alpha: float = 0.3,
    ):
        self.host = host
        self.port = port
        self._timeout = timeout

        update_rate = max(update_rate, 1.0)
        self._expected_dt = 1.0 / update_rate
        self._stale_timeout = max(timeout * 2.0, self._expected_dt * 6.0)
        self._ack_interval = max(self._expected_dt, 0.25)

        # Internal mutable hand state (protected by lock)
        self._left = HandSnapshot()
        self._right = HandSnapshot()
        self._lock = threading.Lock()

        self._left_smoother = _PositionSmoother(smoothing_alpha) if smoothing else None
        self._right_smoother = _PositionSmoother(smoothing_alpha) if smoothing else None

        self._running = False
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

        # Monotonic timestamps for stale detection
        self._left_mono = 0.0
        self._right_mono = 0.0
        self._last_ack_mono = 0.0

        # Stats
        self.packets_received = 0
        self.packets_dropped = 0

    # -- public API --------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        log.info("VR hand receiver started on %s:%d", self.host, self.port)

    def stop(self) -> None:
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        log.info(
            "VR hand receiver stopped. packets=%d dropped=%d",
            self.packets_received, self.packets_dropped,
        )

    def get_snapshots(self) -> Tuple[HandSnapshot, HandSnapshot]:
        """Return thread-safe copies of both hands' current state."""
        self._refresh_stale()
        with self._lock:
            return self._copy(self._left), self._copy(self._right)

    @property
    def any_tracking(self) -> bool:
        with self._lock:
            return self._left.is_tracking or self._right.is_tracking

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _copy(h: HandSnapshot) -> HandSnapshot:
        return HandSnapshot(
            position=h.position.copy(),
            rotation=h.rotation.copy(),
            pinch_strength=h.pinch_strength,
            is_tracking=h.is_tracking,
            velocity=h.velocity.copy(),
            timestamp=h.timestamp,
        )

    def _refresh_stale(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self._left.is_tracking and self._left_mono > 0.0 and now - self._left_mono > self._stale_timeout:
                self._left.is_tracking = False
                self._left.velocity = np.zeros(3)
                self._left.pinch_strength = 0.0
            if self._right.is_tracking and self._right_mono > 0.0 and now - self._right_mono > self._stale_timeout:
                self._right.is_tracking = False
                self._right.velocity = np.zeros(3)
                self._right.pinch_strength = 0.0

    def _recv_loop(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(self._timeout)

        while self._running:
            try:
                data, addr = self._socket.recvfrom(4096)
                self._parse(data, addr)
                self.packets_received += 1
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    self.packets_dropped += 1
                break

    def _send_ack(self, addr: tuple) -> None:
        if self._socket is None:
            return
        payload = json.dumps({
            "type": "ack",
            "server_status": "listening",
            "server_time": time.time(),
            "packets_received": self.packets_received,
        }).encode("utf-8")
        try:
            self._socket.sendto(payload, addr)
        except OSError:
            pass

    def _parse(self, data: bytes, addr: tuple) -> None:
        try:
            pkt = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.packets_dropped += 1
            return

        ts = float(pkt.get("timestamp", 0.0))
        now_mono = time.monotonic()
        should_ack = False

        with self._lock:
            if "left_hand" in pkt:
                self._update_hand(self._left, pkt["left_hand"], ts, now_mono, self._left_smoother, "left")
                self._left_mono = now_mono

            if "right_hand" in pkt:
                self._update_hand(self._right, pkt["right_hand"], ts, now_mono, self._right_smoother, "right")
                self._right_mono = now_mono

            if now_mono - self._last_ack_mono >= self._ack_interval:
                self._last_ack_mono = now_mono
                should_ack = True

        if should_ack:
            self._send_ack(addr)

    def _update_hand(
        self,
        hand: HandSnapshot,
        raw: dict,
        ts: float,
        now_mono: float,
        smoother: _PositionSmoother | None,
        side: str,
    ) -> None:
        raw_pos = np.array(raw.get("position", [0, 0, 0]), dtype=np.float64)
        pos = smoother.update(raw_pos) if smoother else raw_pos

        prev_pos = hand.position.copy()
        dt = ts - hand.timestamp if hand.timestamp > 0 else self._expected_dt
        if dt <= 0:
            dt = self._expected_dt

        is_tracking = raw.get("is_tracking", False)

        hand.position = pos
        hand.rotation = np.array(raw.get("rotation", [1, 0, 0, 0]), dtype=np.float64)
        hand.pinch_strength = float(raw.get("pinch_strength", 0.0))
        hand.is_tracking = is_tracking
        hand.velocity = (pos - prev_pos) / dt if is_tracking else np.zeros(3)
        hand.timestamp = ts
