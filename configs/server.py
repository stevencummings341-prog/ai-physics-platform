"""
Server configuration for the WebRTC + WebSocket backend.
All runtime-configurable values live here; Python code never hard-codes them.
"""
import os
import socket


def _detect_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMERA_SCRIPT_DIR = os.path.join(PROJECT_ROOT, "camera")

# Detect or override via env
HOST_IP = os.getenv("PHYS_HOST_IP", _detect_lan_ip())

# HTTP server (WebRTC signaling + camera control)
HTTP_HOST = "0.0.0.0"
HTTP_PORT = int(os.getenv("PHYS_HTTP_PORT", "8080"))

# WebSocket server (simulation control + telemetry)
WS_HOST = "0.0.0.0"
WS_PORT = int(os.getenv("PHYS_WS_PORT", "30000"))

# Video capture
VIDEO_WIDTH = int(os.getenv("PHYS_VIDEO_W", "2560"))
VIDEO_HEIGHT = int(os.getenv("PHYS_VIDEO_H", "1440"))
VIDEO_FPS = 30

# Telemetry
TELEMETRY_BROADCAST_INTERVAL = 0.01  # 100 Hz
SIMULATION_CHECK_INTERVAL = 0.1

# USD scene
DEFAULT_USD_PATH = os.getenv(
    "PHYS_USD_PATH",
    os.path.join(PROJECT_ROOT, "Experiment", "exp.usd"),
)

# Experiment 1 — angular momentum
EXP1_DISK_PATH = "/World/exp1/disk"
EXP1_RING_PATH = "/World/exp1/ring"
EXP1_DEFAULT_DISK_MASS = 1.0
EXP1_DEFAULT_RING_MASS = 1.0
EXP1_DEFAULT_INITIAL_VELOCITY = 0.0

# Experiment 2 — large-amplitude pendulum (procedural RK4 visual pendulum)
EXP2_PHYSICS_DT = 1.0 / 240.0
EXP2_RENDER_EVERY_N = 6
EXP2_ROD_LENGTH = 0.35           # m
EXP2_ROD_MASS = 0.028            # kg
EXP2_DEFAULT_BOB_MASS1 = 0.075   # kg (lower bob, red)
EXP2_DEFAULT_BOB_MASS2 = 0.075   # kg (upper bob, blue)
EXP2_DEFAULT_R1 = 0.175          # m (pivot → bob1 distance)
EXP2_DEFAULT_R2 = 0.145          # m (pivot → bob2 distance)
EXP2_DEFAULT_DAMPING = 0.0025    # angular damping coefficient
EXP2_DEFAULT_AMPLITUDE = 0.35    # rad (initial amplitude)
EXP2_PIVOT_POS = (0.0, 0.0, 0.80)
EXP2_ROD_DRAW_WIDTH = 0.018
EXP2_ROD_DRAW_DEPTH = 0.018
EXP2_BOB_DRAW_SIZE = 0.048
EXP2_PIVOT_DRAW_SIZE = 0.05
EXP2_FLOOR_Z = -0.24

# Experiment 7 — momentum conservation (two-cart collision)
EXP7_CART1_PATH = "/World/exp7/cart1"
EXP7_CART2_PATH = "/World/exp7/cart2"
EXP7_GROUND_PATH = "/World/exp7/ground"
EXP7_MATERIAL_PATH = "/World/exp7/PhysicsMaterial"
EXP7_DEFAULT_MASS1 = 0.25   # kg
EXP7_DEFAULT_MASS2 = 0.25   # kg
EXP7_DEFAULT_V1 = 0.40      # m/s (rightward)
EXP7_DEFAULT_V2 = -0.40     # m/s (leftward — head-on)
EXP7_DEFAULT_RESTITUTION = 1.0
EXP7_CART_SIZE = (0.12, 0.08, 0.06)     # metres (l × w × h)
EXP7_CART1_INIT_POS = (-0.50, 0.0, 0.03)
EXP7_CART2_INIT_POS = (0.50, 0.0, 0.03)
EXP7_WARMUP_SECONDS = 0.15
EXP7_SOLVER_POS_ITERS = 64
EXP7_SOLVER_VEL_ITERS = 32

# Replicator
REPLICATOR_INIT_MAX_RETRIES = 3
REPLICATOR_INIT_RETRY_DELAY = 1.0
FRAME_CAPTURE_TIMEOUT = 0.2
