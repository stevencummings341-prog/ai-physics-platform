"""
Isaac Sim WebRTC + WebSocket server.

Adapted from physical-lab/isaac_webrtc_server.py and integrated into the
ai-physics-platform project structure.  The monolithic original has been
refactored to import from configs/server.py instead of a bespoke config.py.

This module is designed to run **inside** an Isaac Sim session (Script Editor
or an extension).  It requires the omni.* / pxr.* stack that only the Kit
runtime provides.
"""
from __future__ import annotations

import asyncio
import fractions
import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, Optional, Set

import io
import random

import numpy as np
from PIL import Image

# Isaac Sim core — must already be initialised before this module loads
import carb
import omni.ext
import omni.kit.viewport.utility as vp_util
import omni.usd
import omni.timeline
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdPhysics, UsdShade, PhysxSchema

# ---------------------------------------------------------------------------
# Locate project root and import our unified config
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from configs.server import (
    HOST_IP, HTTP_HOST, HTTP_PORT, WS_HOST, WS_PORT,
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    DEFAULT_USD_PATH, TELEMETRY_BROADCAST_INTERVAL,
    EXP1_DISK_PATH, EXP1_RING_PATH,
    EXP1_DEFAULT_DISK_MASS, EXP1_DEFAULT_RING_MASS,
    EXP1_DEFAULT_INITIAL_VELOCITY,
    EXP2_PHYSICS_DT, EXP2_RENDER_EVERY_N,
    EXP2_ROD_LENGTH, EXP2_ROD_MASS,
    EXP2_DEFAULT_BOB_MASS1, EXP2_DEFAULT_BOB_MASS2,
    EXP2_DEFAULT_R1, EXP2_DEFAULT_R2,
    EXP2_DEFAULT_DAMPING, EXP2_DEFAULT_AMPLITUDE,
    EXP2_PIVOT_POS, EXP2_ROD_DRAW_WIDTH, EXP2_ROD_DRAW_DEPTH,
    EXP2_BOB_DRAW_SIZE, EXP2_PIVOT_DRAW_SIZE, EXP2_FLOOR_Z,
    REPLICATOR_INIT_MAX_RETRIES, CAMERA_SCRIPT_DIR,
    EXP3_PIVOT_PATH, EXP3_PENDULUM_PATH, EXP3_BALL_PATH, EXP3_LAUNCHER_PATH,
    EXP3_MATERIAL_BALL_PATH, EXP3_MATERIAL_CATCHER_PATH, EXP3_JOINT_PATH,
    EXP3_DEFAULT_BALL_MASS, EXP3_DEFAULT_PEND_MASS,
    EXP3_DEFAULT_V0, EXP3_DEFAULT_L,
    EXP3_PIVOT_HEIGHT, EXP3_GROUND_Z,
    EXP3_BALL_SIZE, EXP3_ROD_THICKNESS,
    EXP3_CATCHER_W, EXP3_CATCHER_H, EXP3_CATCHER_WALL_T,
    EXP3_LAUNCHER_GAP, EXP3_BALL_SPAWN_OFFSET,
    EXP3_SOLVER_POS_ITERS, EXP3_SOLVER_VEL_ITERS,
    EXP3_WARMUP_SECONDS, EXP3_AUTO_SETTLE_SECONDS,
    EXP4_PIVOT_PATH, EXP4_DISK_PATH, EXP4_DRIVER_ARM_PATH,
    EXP4_MATERIAL_PATH, EXP4_JOINT_PATH,
    EXP4_DEFAULT_SPRING_K, EXP4_DEFAULT_DAMPING_GAMMA,
    EXP4_DEFAULT_DRIVE_AMP, EXP4_DEFAULT_DRIVE_FREQ,
    EXP4_DISK_MASS, EXP4_DISK_RADIUS, EXP4_DISK_THICKNESS,
    EXP4_PIVOT_HEIGHT, EXP4_GROUND_Z,
    EXP4_SOLVER_POS_ITERS, EXP4_SOLVER_VEL_ITERS,
    EXP4_DRIVER_UPDATE_HZ,
    EXP5_PIVOT_PATH, EXP5_BAR_PATH, EXP5_MATERIAL_PATH, EXP5_JOINT_PATH,
    EXP5_DEFAULT_M, EXP5_DEFAULT_L, EXP5_DEFAULT_X, EXP5_DEFAULT_THETA0_DEG,
    EXP5_BAR_THICKNESS, EXP5_PIVOT_HEIGHT, EXP5_GROUND_Z,
    EXP5_SOLVER_POS_ITERS, EXP5_SOLVER_VEL_ITERS,
    EXP7_CART1_PATH, EXP7_CART2_PATH, EXP7_GROUND_PATH, EXP7_MATERIAL_PATH,
    EXP7_DEFAULT_MASS1, EXP7_DEFAULT_MASS2,
    EXP7_DEFAULT_V1, EXP7_DEFAULT_V2, EXP7_DEFAULT_RESTITUTION,
    EXP7_CART_SIZE, EXP7_CART1_INIT_POS, EXP7_CART2_INIT_POS,
    EXP7_WARMUP_SECONDS, EXP7_SOLVER_POS_ITERS, EXP7_SOLVER_VEL_ITERS,
    EXP8_ROOT_PATH, EXP8_TUBE_PATH, EXP8_SPEAKER_PATH, EXP8_DIAPHRAGM_PATH,
    EXP8_PISTON_PATH, EXP8_SLICE_ROOT, EXP8_SLICE_PATH_TEMPLATE,
    EXP8_MARKER_ROOT, EXP8_MARKER_PATH_TEMPLATE,
    EXP8_N_SLICES, EXP8_TUBE_TOTAL_LENGTH, EXP8_TUBE_DIAMETER, EXP8_TUBE_WALL,
    EXP8_TUBE_BASE_X, EXP8_TUBE_Y, EXP8_TUBE_Z, EXP8_GROUND_Z,
    EXP8_SLICE_DRAW_RADIUS, EXP8_AMP_SCALE,
    EXP8_C_SIM, EXP8_C_REAL, EXP8_FREQ_SCALE,
    EXP8_DEFAULT_LENGTH_CM, EXP8_DEFAULT_FREQUENCY, EXP8_DEFAULT_AMPLITUDE_MM,
    EXP8_DEFAULT_DAMPING, EXP8_DEFAULT_MODE,
    EXP8_PHYS_SUBSTEPS, EXP8_WAVE_TICK_HZ,
    EXP8_TELEMETRY_HISTORY, EXP8_RESONANCE_THRESHOLD,
    VR_ENABLED, VR_UDP_HOST, VR_UDP_PORT, VR_UDP_TIMEOUT,
    VR_UPDATE_RATE, VR_SMOOTHING, VR_SMOOTHING_ALPHA,
    VR_POSITION_SCALE, VR_POSITION_OFFSET,
    VR_PINCH_THRESHOLD, VR_GRASP_DISTANCE, VR_RELEASE_DELAY,
    VR_HAND_SIZE, VR_LEFT_HAND_PATH, VR_RIGHT_HAND_PATH,
)

from core.vr import VRBridge

# WebRTC dependencies (optional — graceful degradation)
try:
    from aiohttp import web
    from aiortc import (
        RTCConfiguration, RTCIceServer,
        RTCPeerConnection, RTCSessionDescription, VideoStreamTrack,
    )
    from av import VideoFrame
    HAS_WEBRTC = True
except ImportError:
    HAS_WEBRTC = False
    carb.log_error("WebRTC unavailable — pip install aiortc aiohttp av")
    # Keep module importable so the error can be surfaced cleanly later.
    class VideoStreamTrack:  # type: ignore[override]
        pass

try:
    import omni.replicator.core as rep
    HAS_REPLICATOR = True
except ImportError:
    HAS_REPLICATOR = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc")


# ===================================================================
# Video track
# ===================================================================
class IsaacSimVideoTrack(VideoStreamTrack):
    """Captures Isaac Sim viewport frames and exposes them as a WebRTC track."""

    def __init__(self, width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT, fps: int = VIDEO_FPS):
        super().__init__()
        self.width = width - (width % 2)
        self.height = height - (height % 2)
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.last_frame_time = 0.0
        self.frame_count = 0
        self.warmup_frames = 30
        self.use_replicator = HAS_REPLICATOR
        self.render_product = None
        self.rgb_annotator = None
        self._replicator_initialized = False
        self._init_retry_count = 0
        self._max_init_retries = 5

    # --- Replicator init ---------------------------------------------------
    async def _init_replicator_async(self):
        try:
            import omni.replicator.core as rep_mod
            carb_settings = carb.settings.get_settings()
            carb_settings.set_bool("/isaaclab/cameras_enabled", True)
            carb_settings.set_bool("/isaaclab/render/rtx_sensors", True)
            app = omni.kit.app.get_app()
            for _ in range(10):
                await app.next_update_async()
            viewport = vp_util.get_active_viewport()
            if not viewport:
                return False
            camera_path = viewport.get_active_camera()
            if not camera_path:
                return False
            if self.render_product:
                try:
                    rep_mod.destroy.render_product(self.render_product)
                except Exception:
                    pass
                self.render_product = None
                self.rgb_annotator = None
            self.render_product = rep_mod.create.render_product(str(camera_path), (self.width, self.height))
            self.rgb_annotator = rep_mod.AnnotatorRegistry.get_annotator("rgb", device="cpu")
            self.rgb_annotator.attach([self.render_product])
            for _ in range(20):
                await app.next_update_async()
            self._replicator_initialized = True
            self._init_retry_count = 0
            return True
        except Exception as exc:
            carb.log_error(f"Replicator init failed: {exc}")
            self._replicator_initialized = False
            return False

    # --- Frame capture -----------------------------------------------------
    async def recv(self):
        if self.frame_count < self.warmup_frames:
            self.frame_count += 1
            await asyncio.sleep(0.1)
            return VideoFrame.from_ndarray(self._blank(), format="rgb24")

        elapsed = time.time() - self.last_frame_time
        if elapsed < self.frame_interval:
            await asyncio.sleep(self.frame_interval - elapsed)
        self.last_frame_time = time.time()
        self.frame_count += 1

        arr = await self._capture()
        if arr is None or arr.size == 0:
            arr = self._blank()
        else:
            if arr.shape[0] != self.height or arr.shape[1] != self.width:
                from PIL import Image
                img = Image.fromarray(arr[:, :, :3] if arr.shape[2] == 4 else arr)
                img = img.resize((self.width, self.height), Image.LANCZOS)
                arr = np.array(img)
            if not (arr.dtype == np.uint8 and arr.flags["C_CONTIGUOUS"]):
                arr = self._fix(arr)
        try:
            frame = VideoFrame.from_ndarray(arr, format="rgb24")
            frame.pts = self.frame_count
            frame.time_base = fractions.Fraction(1, self.fps)
            return frame
        except Exception:
            return VideoFrame.from_ndarray(self._blank(), format="rgb24")

    async def _capture(self):
        frame = await self._capture_viewport()
        if frame is not None:
            return frame
        return await self._capture_replicator()

    async def _capture_viewport(self):
        try:
            from omni.isaac.sensor import Camera
            viewport = vp_util.get_active_viewport()
            if viewport is None:
                return None
            camera_path = viewport.get_active_camera()
            if not camera_path:
                return None
            if not hasattr(self, "_cam") or self._cam_path != str(camera_path):
                self._cam = Camera(prim_path=str(camera_path), resolution=(self.width, self.height))
                self._cam.initialize()
                self._cam_path = str(camera_path)
            rgba = self._cam.get_rgba()
            if rgba is not None and rgba.size > 0:
                return np.ascontiguousarray(rgba[:, :, :3])
        except Exception:
            if hasattr(self, "_cam"):
                del self._cam
        return None

    async def _capture_replicator(self):
        try:
            import omni.replicator.core as rep_mod
            if not self._replicator_initialized or self.rgb_annotator is None:
                self._init_retry_count += 1
                ok = await self._init_replicator_async()
                if not ok:
                    if self._init_retry_count >= self._max_init_retries:
                        self._init_retry_count = 0
                    return None
            try:
                await rep_mod.orchestrator.step_async()
            except Exception:
                pass
            try:
                data = self.rgb_annotator.get_data()
            except KeyError:
                self._replicator_initialized = False
                self.rgb_annotator = None
                return None
            if data is None or data.size == 0:
                return None
            if hasattr(data, "shape") and data.size > 0:
                data = np.frombuffer(data, dtype=np.uint8).reshape(*data.shape)
            if len(data.shape) != 3 or data.shape[2] not in (3, 4):
                return None
            if data.shape[2] == 4:
                data = data[:, :, :3]
            return data
        except Exception:
            self._replicator_initialized = False
            return None

    def _blank(self):
        f = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        f[:, :, 1] = 128
        return f

    def _fix(self, arr):
        if arr.dtype != np.uint8:
            if arr.dtype in (np.float32, np.float64):
                arr = (arr.clip(0, 1) * 255).astype(np.uint8)
            else:
                arr = arr.astype(np.uint8)
        if len(arr.shape) == 3 and arr.shape[2] == 4:
            arr = arr[:, :, :3]
        return np.ascontiguousarray(arr)


# ===================================================================
# Camera controller (orbit / pan / zoom around a target via lookAt)
# ===================================================================
class CameraController:
    def __init__(self):
        self.distance = 0.5
        self.azimuth = -45.0
        self.elevation = 40.0
        self.target = Gf.Vec3d(0, 0, 0)

    def set_from_eye_target(self, eye: Gf.Vec3d, target: Gf.Vec3d):
        d = eye - target
        self.target = target
        self.distance = d.GetLength()
        horiz = math.sqrt(d[0]**2 + d[1]**2)
        self.elevation = math.degrees(math.atan2(d[2], horiz)) if horiz > 0.001 else 90.0
        self.azimuth = math.degrees(math.atan2(d[1], d[0]))

    def orbit(self, dx, dy):
        self.azimuth = (self.azimuth + dx * 0.4) % 360
        self.elevation = max(5, min(85, self.elevation + dy * 0.4))
        self._apply()

    def zoom(self, delta):
        self.distance = max(0.15, self.distance + delta * 0.05)
        self._apply()

    def pan(self, dx, dy):
        scale = self.distance * 0.001
        az = math.radians(self.azimuth)
        right = Gf.Vec3d(-math.sin(az), math.cos(az), 0)
        up = Gf.Vec3d(0, 0, 1)
        self.target += right * (dx * scale) + up * (dy * scale)
        self._apply()

    def reset(self):
        self.distance, self.azimuth, self.elevation = 0.5, -45.0, 40.0
        self._apply()

    def _apply(self):
        try:
            viewport = vp_util.get_active_viewport()
            if not viewport:
                return
            cam_path = viewport.get_active_camera()
            if not cam_path:
                return
            az = math.radians(self.azimuth)
            el = math.radians(self.elevation)
            eye = self.target + Gf.Vec3d(
                self.distance * math.cos(el) * math.cos(az),
                self.distance * math.cos(el) * math.sin(az),
                self.distance * math.sin(el),
            )
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            prim = stage.GetPrimAtPath(cam_path)
            if not prim or not prim.IsValid():
                return
            backward = (eye - self.target).GetNormalized()
            world_up = Gf.Vec3d(0, 0, 1)
            right = (world_up ^ backward).GetNormalized()
            cam_up = (backward ^ right).GetNormalized()
            m = Gf.Matrix4d(1)
            m[0, 0], m[0, 1], m[0, 2] = right[0], right[1], right[2]
            m[1, 0], m[1, 1], m[1, 2] = cam_up[0], cam_up[1], cam_up[2]
            m[2, 0], m[2, 1], m[2, 2] = backward[0], backward[1], backward[2]
            m[3, 0], m[3, 1], m[3, 2] = eye[0], eye[1], eye[2]
            xform = UsdGeom.Xformable(prim)
            xform.ClearXformOpOrder()
            xform.AddTransformOp().Set(m)
        except Exception:
            pass


# ===================================================================
# Shared frame capture (used by both WebRTC track and WS fallback)
# ===================================================================
class _SharedFrameCapture:
    """Singleton that grabs viewport frames and encodes to JPEG."""
    _inst: Optional["_SharedFrameCapture"] = None

    @classmethod
    def instance(cls) -> "_SharedFrameCapture":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self._replicator_ok = False
        self._render_product = None
        self._rgb_ann = None

    async def grab_jpeg(
        self, width: int = 1280, height: int = 720, quality: int = 65
    ) -> Optional[bytes]:
        arr = await self._capture_viewport()
        if arr is None:
            arr = await self._capture_replicator()
        if arr is None:
            return None
        try:
            if arr.shape[2] == 4:
                arr = arr[:, :, :3]
            img = Image.fromarray(arr)
            if img.size != (width, height):
                img = img.resize((width, height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return buf.getvalue()
        except Exception:
            return None

    async def _capture_viewport(self):
        try:
            from omni.isaac.sensor import Camera
            viewport = vp_util.get_active_viewport()
            if viewport is None:
                return None
            camera_path = viewport.get_active_camera()
            if not camera_path:
                return None
            if not hasattr(self, "_cam") or self._cam_path != str(camera_path):
                self._cam = Camera(
                    prim_path=str(camera_path), resolution=(1280, 720)
                )
                self._cam.initialize()
                self._cam_path = str(camera_path)
            rgba = self._cam.get_rgba()
            if rgba is not None and rgba.size > 0:
                return np.ascontiguousarray(rgba)
            return None
        except Exception:
            if hasattr(self, "_cam"):
                del self._cam
            return None

    async def _capture_replicator(self):
        if not HAS_REPLICATOR:
            return None
        try:
            import omni.replicator.core as rep_mod
            if not self._replicator_ok or self._rgb_ann is None:
                viewport = vp_util.get_active_viewport()
                if not viewport:
                    return None
                cam = viewport.get_active_camera()
                if not cam:
                    return None
                if self._render_product:
                    try:
                        rep_mod.destroy.render_product(self._render_product)
                    except Exception:
                        pass
                self._render_product = rep_mod.create.render_product(
                    str(cam), (1280, 720)
                )
                self._rgb_ann = rep_mod.AnnotatorRegistry.get_annotator(
                    "rgb", device="cpu"
                )
                self._rgb_ann.attach([self._render_product])
                app = omni.kit.app.get_app()
                for _ in range(20):
                    await app.next_update_async()
                self._replicator_ok = True
            try:
                await rep_mod.orchestrator.step_async()
            except Exception:
                pass
            data = self._rgb_ann.get_data()
            if data is None or data.size == 0:
                return None
            data = np.frombuffer(data, dtype=np.uint8).reshape(*data.shape)
            return data
        except Exception:
            self._replicator_ok = False
            return None


# ===================================================================
# Main WebRTC / WebSocket server
# ===================================================================
class WebRTCServer:
    """Combined HTTP (WebRTC signaling) + WebSocket (control/telemetry) server."""

    def __init__(
        self,
        host: str = HTTP_HOST,
        http_port: int = HTTP_PORT,
        ws_port: int = WS_PORT,
    ):
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.pcs: Set[RTCPeerConnection] = set()
        self.camera_controller = CameraController()
        self.video_track: Optional[IsaacSimVideoTrack] = None
        self.ws_clients: Set[web.WebSocketResponse] = set()

        self.simulation_control_enabled = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Experiment 1 — angular momentum
        self.exp1_disk_mass = EXP1_DEFAULT_DISK_MASS
        self.exp1_ring_mass = EXP1_DEFAULT_RING_MASS
        self.exp1_initial_vel = EXP1_DEFAULT_INITIAL_VELOCITY
        self.exp1_drop_object = "ring"   # "ring" or "disk"
        self.exp1_phase = "idle"         # idle → spinning → dropped
        self.exp1_disk_radius = 0.0467   # 4.67 cm in meters
        self.exp1_ring_inner_r = 0.02575
        self.exp1_ring_outer_r = 0.03725
        self.exp1_omega_before_drop = 0.0
        self.exp1_omega_after_drop = 0.0
        self.exp1_initial_am = 0.0
        self.exp1_final_am = 0.0
        self.exp1_ke_initial = 0.0
        self.exp1_ke_final = 0.0
        self.exp1_drop_offset = 0.0
        self.exp1_I_final_actual = 0.0

        # Experiment 2 — large-amplitude pendulum (procedural RK4)
        self.exp2_amplitude = EXP2_DEFAULT_AMPLITUDE
        self.exp2_damping = EXP2_DEFAULT_DAMPING
        self.exp2_bob_mass1 = EXP2_DEFAULT_BOB_MASS1
        self.exp2_bob_mass2 = EXP2_DEFAULT_BOB_MASS2
        self.exp2_r1 = EXP2_DEFAULT_R1
        self.exp2_r2 = EXP2_DEFAULT_R2
        self.exp2_theta = 0.0
        self.exp2_omega = 0.0
        self.exp2_alpha = 0.0
        self.exp2_sim_time = 0.0
        self.exp2_phase = "idle"            # idle → running → stopped
        self.exp2_measured_period = 0.0
        self.exp2_period_samples: list = []
        self.exp2_pos_zero_crossings: list = []
        self.exp2_prev_theta_sign = 1
        self.exp2_scene_built = False
        self.exp2_rotate_op = None          # USD RotateXYZOp handle
        self.exp2_world = None              # isaacsim World for rendering
        self.exp2_sim_task: Optional[asyncio.Task] = None
        self._exp2_props: Dict[str, float] = {}
        self._exp2_T0: float = 0.0
        self._exp2_recompute_props()

        # Experiment 3 — ballistic pendulum (PhysX compound rigid body + revolute joint)
        self.exp3_ball_mass = EXP3_DEFAULT_BALL_MASS
        self.exp3_pend_mass = EXP3_DEFAULT_PEND_MASS
        self.exp3_v0 = EXP3_DEFAULT_V0
        self.exp3_L = EXP3_DEFAULT_L                # pivot → catcher CM (rod length)
        self.exp3_phase = "idle"                    # idle → firing → swinging → settled
        self.exp3_scene_built = False
        self.exp3_theta = 0.0                       # rad, live pendulum angle (around Y)
        self.exp3_omega = 0.0                       # rad/s
        self.exp3_theta_max = 0.0                   # rad, running max |θ|
        self.exp3_v0_measured = 0.0                 # m/s, computed from θmax via Eq. 4
        self.exp3_ball_velocity = 0.0               # m/s (live |v| of ball)
        self.exp3_fire_time = 0.0                   # wall-clock at fire
        self.exp3_collision_time = 0.0
        self.exp3_collision_detected = False
        self.exp3_prev_omega_sign = 0
        self.exp3_settle_deadline = 0.0

        # Experiment 3 — legacy aliases (kept so old websocket messages still work)
        self.exp3_projectile_mass = self.exp3_ball_mass
        self.exp3_pendulum_mass = self.exp3_pend_mass

        # Experiment 4 — driven damped torsional oscillator (PhysX-native)
        self.exp4_spring_k = EXP4_DEFAULT_SPRING_K             # κ (N·m/rad)
        self.exp4_damping_gamma = EXP4_DEFAULT_DAMPING_GAMMA   # γ = b/I (1/s)
        self.exp4_drive_amp = EXP4_DEFAULT_DRIVE_AMP           # A (rad)
        self.exp4_frequency = EXP4_DEFAULT_DRIVE_FREQ          # f_d (Hz)
        self.exp4_disk_mass = EXP4_DISK_MASS
        self.exp4_disk_radius = EXP4_DISK_RADIUS
        self.exp4_phase = "idle"            # idle → running → free → stopped
        self.exp4_scene_built = False
        self.exp4_theta = 0.0               # rad   (live disk angle)
        self.exp4_omega = 0.0               # rad/s (live disk ang. vel.)
        self.exp4_theta_drive = 0.0         # rad   (driver arm angle)
        self.exp4_sim_start_time = 0.0
        self.exp4_peak_amp = 0.0            # rad   (running peak |θ|)
        self.exp4_peak_decay = 0.995        # exponential decay of peak hold
        self.exp4_drive_task: Optional[asyncio.Task] = None
        self._exp4_drive_target_attr = None  # cached USD attr handle
        self._exp4_drive_arm_op = None       # cached RotateZOp on driver arm
        # Legacy alias (old message type "set_damping" still needs a bucket)
        self.exp4_damping = self.exp4_damping_gamma

        # Experiment 5 — physical pendulum (rotational inertia)
        self.exp5_m = EXP5_DEFAULT_M
        self.exp5_L = EXP5_DEFAULT_L
        self.exp5_x = EXP5_DEFAULT_X
        self.exp5_theta0_deg = EXP5_DEFAULT_THETA0_DEG
        self.exp5_phase = "idle"          # idle → running → stopped
        self.exp5_scene_built = False
        self.exp5_theta = 0.0             # rad (live, from USD pose)
        self.exp5_omega = 0.0             # rad/s (live, from dynamic_control)
        self.exp5_sim_start_time = 0.0    # wall-clock ref for sim_time
        self.exp5_measured_period = 0.0   # rolling average period (s)
        self.exp5_period_samples: list = []
        self.exp5_pos_zero_crossings: list = []
        self.exp5_prev_theta_sign = 1

        # Experiment 6 — centripetal force
        self.exp6_mass = 0.5
        self.exp6_radius = 0.3
        self.exp6_angular_velocity = 5.0

        # Experiment 7 — momentum conservation (two-cart collision)
        self.exp7_mass1 = EXP7_DEFAULT_MASS1
        self.exp7_mass2 = EXP7_DEFAULT_MASS2
        self.exp7_v1 = EXP7_DEFAULT_V1
        self.exp7_v2 = EXP7_DEFAULT_V2
        self.exp7_restitution = EXP7_DEFAULT_RESTITUTION
        self.exp7_phase = "idle"           # idle → warmup → running → settled
        self.exp7_scene_built = False
        self.exp7_pre_v1 = 0.0
        self.exp7_pre_v2 = 0.0
        self.exp7_post_v1 = 0.0
        self.exp7_post_v2 = 0.0
        self.exp7_prev_v1: Optional[float] = None
        self.exp7_prev_v2: Optional[float] = None
        self.exp7_collision_time = 0.0
        self.exp7_collision_detected = False
        self.exp7_deadline = 0.0           # auto-settle timestamp

        # Experiment 8 — resonance in air column (driven 1-D wave equation
        # with PhysX-rendered air slices)
        self.exp8_length_m = EXP8_DEFAULT_LENGTH_CM / 100.0
        self.exp8_frequency = EXP8_DEFAULT_FREQUENCY        # Hz, real-world
        self.exp8_amplitude_mm = EXP8_DEFAULT_AMPLITUDE_MM  # mm, speaker excursion
        self.exp8_damping = EXP8_DEFAULT_DAMPING            # γ (1/s)
        self.exp8_mode = EXP8_DEFAULT_MODE                  # "closed" | "open"
        self.exp8_phase = "idle"                            # idle → running → stopped
        self.exp8_scene_built = False
        self.exp8_driver_running = False
        self.exp8_sim_start_time = 0.0
        # FDM wave-equation state (allocated in _exp8_reset_fields)
        self._exp8_u_prev = np.zeros(EXP8_N_SLICES + 1, dtype=np.float64)
        self._exp8_u_curr = np.zeros(EXP8_N_SLICES + 1, dtype=np.float64)
        self._exp8_u_next = np.zeros(EXP8_N_SLICES + 1, dtype=np.float64)
        self._exp8_probe_history: list = []          # RMS probe trace
        self._exp8_amp_history: list = []            # max |u| over last second
        self._exp8_update_task: Optional[asyncio.Task] = None
        self._exp8_last_rms = 0.0
        self._exp8_last_peak = 0.0
        self._exp8_resonance_ratio = 0.0
        self._exp8_nearest_mode = 1

        # Generic per-experiment parameter store for telemetry
        self._exp_params: Dict[str, Dict[str, float]] = {}

        self.current_experiment = "1"

        self._dc_interface = None

        # VR hand tracking bridge
        self.vr_bridge = VRBridge(
            enabled=VR_ENABLED,
            host=VR_UDP_HOST,
            port=VR_UDP_PORT,
            timeout=VR_UDP_TIMEOUT,
            update_rate=VR_UPDATE_RATE,
            smoothing=VR_SMOOTHING,
            smoothing_alpha=VR_SMOOTHING_ALPHA,
            position_scale=VR_POSITION_SCALE,
            position_offset=VR_POSITION_OFFSET,
            pinch_threshold=VR_PINCH_THRESHOLD,
            grasp_distance=VR_GRASP_DISTANCE,
            release_delay=VR_RELEASE_DELAY,
            hand_size=VR_HAND_SIZE,
            left_hand_path=VR_LEFT_HAND_PATH,
            right_hand_path=VR_RIGHT_HAND_PATH,
        )

    # --- HTTP endpoints ----------------------------------------------------

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        pc = RTCPeerConnection(
            configuration=RTCConfiguration(
                iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
            )
        )
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def _on_state():
            if pc.connectionState in ("failed", "closed"):
                self.pcs.discard(pc)
                await pc.close()

        if self.video_track is None:
            self.video_track = IsaacSimVideoTrack()
        pc.addTrack(self.video_track)
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        sdp_text = pc.localDescription.sdp
        patched_lines = []
        for line in sdp_text.splitlines():
            if "c=IN IP4" in line:
                patched_lines.append(f"c=IN IP4 {HOST_IP}")
            elif line.startswith("o="):
                patched_lines.append(line.replace("0.0.0.0", HOST_IP).replace("127.0.0.1", HOST_IP))
            elif "a=candidate" in line:
                patched_lines.append(line.replace("0.0.0.0", HOST_IP).replace("127.0.0.1", HOST_IP).replace(".local", ""))
            else:
                patched_lines.append(line)
        patched_sdp = "\r\n".join(patched_lines) + "\r\n"

        return web.Response(
            content_type="application/json",
            text=json.dumps({"sdp": patched_sdp, "type": pc.localDescription.type}),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def camera_control(self, request):
        p = await request.json()
        action = p.get("action")
        if action == "orbit":
            self.camera_controller.orbit(p.get("deltaX", 0), p.get("deltaY", 0))
        elif action == "pan":
            self.camera_controller.pan(p.get("deltaX", 0), p.get("deltaY", 0))
        elif action == "zoom":
            self.camera_controller.zoom(p.get("delta", 0))
        elif action == "reset":
            self.camera_controller.reset()
        return web.Response(
            text=json.dumps({"status": "ok"}),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def load_usd(self, request):
        p = await request.json()
        experiment_id = str(p.get("experiment_id", "")).strip()
        if experiment_id == "7":
            await self._setup_exp7_scene()
            return web.Response(text=json.dumps({"status": "ok"}))
        if experiment_id == "2":
            await self._setup_exp2_scene()
            return web.Response(text=json.dumps({"status": "ok"}))
        if experiment_id == "3":
            await self._setup_exp3_scene()
            return web.Response(text=json.dumps({"status": "ok"}))
        if experiment_id == "4":
            await self._setup_exp4_scene()
            return web.Response(text=json.dumps({"status": "ok"}))
        usd_path = p.get("usd_path")
        if not usd_path:
            project_root = _PROJECT_ROOT
            experiment_stage_paths = {
                "1": os.path.join(project_root, "Experiment", "exp1", "exp1.usd"),
            }
            usd_path = experiment_stage_paths.get(experiment_id, DEFAULT_USD_PATH)
        ok = omni.usd.get_context().open_stage(usd_path)
        if ok:
            self.simulation_control_enabled = False
            omni.timeline.get_timeline_interface().stop()
            await self._apply_exp1_params()
            return web.Response(text=json.dumps({"status": "ok"}))
        return web.Response(status=500, text="Failed to load USD")

    # --- WebSocket handler --------------------------------------------------

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
        await ws.prepare(request)
        self.ws_clients.add(ws)
        await ws.send_json({"type": "connected", "message": "WebSocket connected to Isaac Sim"})
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(ws, data)
        finally:
            self.ws_clients.discard(ws)
        return ws

    async def _handle_ws_message(self, ws, data: dict):
        mtype = data.get("type", "")
        tl = omni.timeline.get_timeline_interface()

        if mtype == "start_simulation":
            if self.current_experiment == "7":
                await self._start_exp7_collision()
            elif self.current_experiment == "2":
                await self._start_exp2_sim()
            elif self.current_experiment == "4":
                await self._start_exp4_sim()
            elif self.current_experiment == "5":
                await self._start_exp5_sim()
            elif self.current_experiment == "3":
                await self._fire_exp3_ball()
            elif self.current_experiment == "8":
                await self._start_exp8_drive()
            else:
                if not getattr(self, "_has_started", False):
                    if self.current_experiment == "1":
                        await self._set_initial_angular_velocity()
                    self._has_started = True
                self.simulation_control_enabled = True
                tl.play()

        elif mtype == "stop_simulation":
            if self.current_experiment == "2":
                self.exp2_phase = "stopped"
            elif self.current_experiment == "4":
                self.exp4_phase = "stopped"
                if self.exp4_drive_task and not self.exp4_drive_task.done():
                    self.exp4_drive_task.cancel()
                    self.exp4_drive_task = None
            elif self.current_experiment == "5":
                self.exp5_phase = "stopped"
            elif self.current_experiment == "3":
                self.exp3_phase = "settled"
            elif self.current_experiment == "8":
                await self._stop_exp8_drive()
            self.simulation_control_enabled = False
            tl.stop()

        elif mtype == "reset":
            self.simulation_control_enabled = False
            self._has_started = False
            if self.current_experiment == "1":
                self.exp1_phase = "idle"
                self.exp1_omega_before_drop = 0.0
                self.exp1_omega_after_drop = 0.0
                self.exp1_initial_am = 0.0
                self.exp1_final_am = 0.0
                self.exp1_ke_initial = 0.0
                self.exp1_ke_final = 0.0
                self.exp1_drop_offset = 0.0
            elif self.current_experiment == "2":
                self._reset_exp2_state()
                self._exp2_update_pose(0.0)
            elif self.current_experiment == "3":
                await self._reset_exp3()
            elif self.current_experiment == "4":
                await self._reset_exp4()
            elif self.current_experiment == "5":
                await self._reset_exp5()
            elif self.current_experiment == "7":
                await self._reset_exp7()
            elif self.current_experiment == "8":
                await self._reset_exp8()
            tl.stop()
            tl.set_current_time(0.0)
            tl.stop()
            await asyncio.sleep(0.1)
            tl.stop()

        elif mtype == "set_drop_object":
            self.exp1_drop_object = str(data.get("value", "ring"))

        elif mtype == "spin_disk":
            if self.current_experiment == "1":
                self.exp1_phase = "spinning"
                self._has_started = True
                await self._set_initial_angular_velocity()
                self.simulation_control_enabled = True
                tl.play()

        elif mtype == "drop_object":
            if self.current_experiment == "1" and self.exp1_phase == "spinning":
                dv, _ = self._get_angular_velocities()
                # If live readback fails, use the configured velocity
                if abs(dv) < 0.01:
                    dv = self.exp1_initial_vel
                self.exp1_omega_before_drop = dv
                I_disk = 0.5 * self.exp1_disk_mass * (self.exp1_disk_radius ** 2)
                self.exp1_initial_am = I_disk * dv
                self.exp1_ke_initial = 0.5 * I_disk * dv * dv
                await self._drop_ring_or_disk()
                self.exp1_phase = "dropped"

        elif mtype == "load_usd":
            exp_id = str(data.get("experiment_id", "1")).strip()
            if exp_id == "7":
                await self._setup_exp7_scene()
                await ws.send_json({"type": "usd_loaded", "success": True, "path": "procedural"})
            elif exp_id == "2":
                await self._setup_exp2_scene()
                await ws.send_json({"type": "usd_loaded", "success": True, "path": "procedural"})
            elif exp_id == "3":
                await self._setup_exp3_scene()
                await ws.send_json({"type": "usd_loaded", "success": True, "path": "procedural"})
            elif exp_id == "4":
                await self._setup_exp4_scene()
                await ws.send_json({"type": "usd_loaded", "success": True, "path": "procedural"})
            else:
                usd_path = data.get("usd_path")
                if not usd_path:
                    exp_stage = {
                        "1": os.path.join(_PROJECT_ROOT, "Experiment", "exp1", "exp1.usd"),
                    }
                    usd_path = exp_stage.get(exp_id, DEFAULT_USD_PATH)
                carb.log_warn(f"Loading USD: {usd_path}")
                ok = omni.usd.get_context().open_stage(usd_path)
                if ok:
                    self.simulation_control_enabled = False
                    tl.stop()
                await ws.send_json({"type": "usd_loaded", "success": ok, "path": usd_path})

        elif mtype == "enter_experiment":
            exp_id = data.get("experiment_id", "1")
            self.current_experiment = exp_id
            self._cam_deferred_done = False
            if exp_id == "2":
                self._reset_exp2_state()
                await self._setup_exp2_scene()
            elif exp_id == "3":
                await self._setup_exp3_scene()
            elif exp_id == "4":
                await self._setup_exp4_scene()
            elif exp_id == "5":
                await self._setup_exp5_scene()
            elif exp_id == "7":
                await self._setup_exp7_scene()
            elif exp_id == "8":
                await self._setup_exp8_scene()
            await self._switch_camera(exp_id)
            if exp_id == "1":
                await self._apply_exp1_params()
                asyncio.ensure_future(self._deferred_camera_readjust())
            elif exp_id == "2":
                asyncio.ensure_future(self._deferred_exp2_camera())
            elif exp_id == "3":
                asyncio.ensure_future(self._deferred_exp3_camera())
            elif exp_id == "4":
                asyncio.ensure_future(self._deferred_exp4_camera())
            elif exp_id == "5":
                asyncio.ensure_future(self._deferred_exp5_camera())
            elif exp_id == "8":
                asyncio.ensure_future(self._deferred_exp8_camera())
            if self.vr_bridge.enabled:
                self.vr_bridge.ensure_hand_prims()
            await ws.send_json({"type": "experiment_entered", "experiment_id": exp_id})

        elif mtype == "switch_camera":
            exp_id = data.get("experiment_id", "2")
            await self._switch_camera(exp_id)
            await ws.send_json({"type": "camera_switched", "experiment_id": exp_id})

        elif mtype == "get_simulation_state":
            await ws.send_json({
                "type": "simulation_state",
                "running": tl.is_playing(),
                "paused": not tl.is_playing(),
                "time": tl.get_current_time(),
                "step": 0,
            })

        elif mtype in ("set_disk_mass", "set_mass"):
            self.exp1_disk_mass = float(data.get("value", 1.0))
            await self._apply_exp1_params()
        elif mtype == "set_ring_mass":
            self.exp1_ring_mass = float(data.get("value", 1.0))
            await self._apply_exp1_params()
        elif mtype == "set_initial_velocity":
            self.exp1_initial_vel = float(data.get("value", 5.0))

        elif mtype == "set_exp2_amplitude":
            self.exp2_amplitude = float(data.get("value", EXP2_DEFAULT_AMPLITUDE))
        elif mtype == "set_exp2_damping":
            self.exp2_damping = float(data.get("value", EXP2_DEFAULT_DAMPING))
        elif mtype == "run_exp2_full_experiment":
            asyncio.ensure_future(self._run_exp2_full_experiment(ws))

        # Experiment 3 — ballistic pendulum
        elif mtype in ("set_ball_mass", "set_projectile_mass"):
            self.exp3_ball_mass = float(data.get("value", EXP3_DEFAULT_BALL_MASS))
            self.exp3_projectile_mass = self.exp3_ball_mass  # legacy alias
            if self.exp3_scene_built:
                await self._apply_mass_at(EXP3_BALL_PATH, self.exp3_ball_mass)
        elif mtype in ("set_pend_mass", "set_pendulum_mass"):
            self.exp3_pend_mass = float(data.get("value", EXP3_DEFAULT_PEND_MASS))
            self.exp3_pendulum_mass = self.exp3_pend_mass  # legacy alias
            if self.exp3_scene_built:
                await self._apply_mass_at(EXP3_PENDULUM_PATH, self.exp3_pend_mass)
        elif mtype == "set_exp3_v0":
            self.exp3_v0 = float(data.get("value", EXP3_DEFAULT_V0))
        elif mtype == "set_exp3_L":
            # Pivot-to-CM distance — changing L requires a scene rebuild
            self.exp3_L = max(0.10, float(data.get("value", EXP3_DEFAULT_L)))
            if self.exp3_scene_built:
                await self._setup_exp3_scene()

        # Experiment 4 — driven damped torsional oscillator (PhysX-native)
        elif mtype in ("set_exp4_frequency", "set_frequency"):
            val = float(data.get("value", EXP4_DEFAULT_DRIVE_FREQ))
            # `set_frequency` is shared with Exp 8; route by current experiment
            if mtype == "set_frequency" and self.current_experiment == "8":
                self.exp8_frequency = val
            else:
                self.exp4_frequency = max(0.01, val)
        elif mtype in ("set_exp4_damping", "set_damping"):
            val = float(data.get("value", EXP4_DEFAULT_DAMPING_GAMMA))
            # `set_damping` is shared with Exp 8; route by current experiment
            if mtype == "set_damping" and self.current_experiment == "8":
                self.exp8_damping = max(0.0, min(20.0, val))
            else:
                self.exp4_damping_gamma = max(0.0, val)
                self.exp4_damping = self.exp4_damping_gamma  # legacy alias
                self._apply_exp4_drive_params()
        elif mtype == "set_exp4_spring":
            self.exp4_spring_k = max(1e-6, float(data.get("value", EXP4_DEFAULT_SPRING_K)))
            self._apply_exp4_drive_params()
        elif mtype == "set_exp4_drive_amplitude":
            self.exp4_drive_amp = max(0.0, float(data.get("value", EXP4_DEFAULT_DRIVE_AMP)))
        elif mtype == "exp4_free_oscillation":
            await self._start_exp4_free_oscillation()

        # Experiment 5 — physical pendulum (rotational inertia)
        elif mtype == "set_exp5_m":
            self.exp5_m = float(data.get("value", EXP5_DEFAULT_M))
            if self.exp5_scene_built:
                await self._apply_mass_at(EXP5_BAR_PATH, self.exp5_m)
        elif mtype == "set_exp5_L":
            self.exp5_L = float(data.get("value", EXP5_DEFAULT_L))
            # Geometry change requires rebuild to adjust bar scale + joint offset
            if self.exp5_scene_built:
                await self._setup_exp5_scene()
        elif mtype == "set_exp5_x":
            new_x = float(data.get("value", EXP5_DEFAULT_X))
            # Clamp to [0.01, L/2] to stay physically meaningful
            self.exp5_x = max(0.01, min(new_x, self.exp5_L / 2.0))
            if self.exp5_scene_built:
                await self._setup_exp5_scene()
        elif mtype == "set_exp5_theta0":
            self.exp5_theta0_deg = float(data.get("value", EXP5_DEFAULT_THETA0_DEG))

        # Experiment 6 — centripetal force
        elif mtype == "set_radius":
            self.exp6_radius = float(data.get("value", 0.3))
        elif mtype == "set_angular_velocity":
            self.exp6_angular_velocity = float(data.get("value", 5.0))

        # Experiment 7 — momentum conservation
        elif mtype == "set_mass1":
            self.exp7_mass1 = float(data.get("value", EXP7_DEFAULT_MASS1))
            if self.exp7_scene_built:
                await self._apply_mass_at(EXP7_CART1_PATH, self.exp7_mass1)
        elif mtype == "set_mass2":
            self.exp7_mass2 = float(data.get("value", EXP7_DEFAULT_MASS2))
            if self.exp7_scene_built:
                await self._apply_mass_at(EXP7_CART2_PATH, self.exp7_mass2)
        elif mtype == "set_velocity1":
            self.exp7_v1 = float(data.get("value", EXP7_DEFAULT_V1))
        elif mtype == "set_velocity2":
            self.exp7_v2 = float(data.get("value", EXP7_DEFAULT_V2))
        elif mtype == "set_elasticity":
            self.exp7_restitution = float(data.get("value", EXP7_DEFAULT_RESTITUTION))
            if self.exp7_scene_built:
                await self._update_exp7_restitution()

        # Experiment 8 — resonance in air column
        elif mtype == "set_length":
            length_cm = float(data.get("value", EXP8_DEFAULT_LENGTH_CM))
            length_cm = max(5.0, min(EXP8_TUBE_TOTAL_LENGTH * 100.0, length_cm))
            self.exp8_length_m = length_cm / 100.0
            if self.current_experiment == "8" and self.exp8_scene_built:
                await self._exp8_apply_piston_position()
                self._exp8_reset_fields()
        elif mtype == "set_exp8_amplitude":
            amp_mm = float(data.get("value", EXP8_DEFAULT_AMPLITUDE_MM))
            self.exp8_amplitude_mm = max(0.0, min(10.0, amp_mm))
        elif mtype == "set_exp8_damping":
            gamma = float(data.get("value", EXP8_DEFAULT_DAMPING))
            self.exp8_damping = max(0.0, min(20.0, gamma))
        elif mtype in ("set_exp8_mode", "exp8_open_tube", "exp8_closed_tube"):
            if mtype == "exp8_open_tube":
                self.exp8_mode = "open"
            elif mtype == "exp8_closed_tube":
                self.exp8_mode = "closed"
            else:
                mode = str(data.get("value", EXP8_DEFAULT_MODE)).lower()
                self.exp8_mode = "open" if mode == "open" else "closed"
            if self.current_experiment == "8" and self.exp8_scene_built:
                await self._exp8_apply_piston_position()
                self._exp8_reset_fields()

        # VR hand tracking commands
        elif mtype == "vr_enable":
            if not self.vr_bridge.enabled:
                self.vr_bridge.enabled = True
                self.vr_bridge.start()
                self.vr_bridge.ensure_hand_prims()
            await ws.send_json({"type": "vr_status", "enabled": True})

        elif mtype == "vr_disable":
            if self.vr_bridge.enabled:
                self.vr_bridge.remove_hand_prims()
                self.vr_bridge.stop()
                self.vr_bridge.enabled = False
            await ws.send_json({"type": "vr_status", "enabled": False})

        elif mtype == "get_vr_status":
            await ws.send_json({
                "type": "vr_status",
                "enabled": self.vr_bridge.enabled,
                "connected": self.vr_bridge.any_tracking,
                "packets": self.vr_bridge.packets_received,
            })

    # --- VR helpers --------------------------------------------------------

    def _vr_graspable_paths(self) -> list:
        """Return USD prim paths that VR hands may grab in the current experiment."""
        exp = self.current_experiment
        if exp == "1":
            return [EXP1_RING_PATH]
        if exp == "7":
            return [EXP7_CART1_PATH, EXP7_CART2_PATH]
        return []

    # --- Helpers -----------------------------------------------------------

    def _reset_exp2_state(self):
        if self.exp2_sim_task and not self.exp2_sim_task.done():
            self.exp2_sim_task.cancel()
            self.exp2_sim_task = None
        self.exp2_theta = 0.0
        self.exp2_omega = 0.0
        self.exp2_alpha = 0.0
        self.exp2_sim_time = 0.0
        self.exp2_phase = "idle"
        self.exp2_measured_period = 0.0
        self.exp2_period_samples = []
        self.exp2_pos_zero_crossings = []
        self.exp2_prev_theta_sign = 1

    # --- Experiment 2 RK4 pendulum physics -----------------------------------

    def _exp2_recompute_props(self):
        """Compute physical pendulum properties from current mass/geometry."""
        m_rod = EXP2_ROD_MASS
        L = EXP2_ROD_LENGTH
        m1 = self.exp2_bob_mass1
        m2 = self.exp2_bob_mass2
        r1 = self.exp2_r1
        r2 = self.exp2_r2
        m_total = m_rod + m1 + m2
        d = (m1 * r1 - m2 * r2) / m_total
        I_rod = (1.0 / 12.0) * m_rod * L ** 2
        I = I_rod + m1 * r1 ** 2 + m2 * r2 ** 2
        self._exp2_props = {"m_total": m_total, "d": d, "I": I}
        self._exp2_T0 = 2.0 * np.pi * np.sqrt(I / (m_total * 9.81 * d)) if d > 0 else 0.0

    def _exp2_period_series(self, amplitude_rad: float, n_terms: int = 5) -> float:
        """Large-amplitude period via elliptic integral series expansion."""
        k2 = np.sin(amplitude_rad / 2.0) ** 2
        coeffs = [1.0, 1.0 / 4.0, 9.0 / 64.0, 25.0 / 256.0, 1225.0 / 16384.0]
        value = sum(coeffs[i] * (k2 ** i) for i in range(min(n_terms, len(coeffs))))
        return self._exp2_T0 * value

    def _exp2_pendulum_rhs(self, theta: float, omega: float):
        """Return (d_theta/dt, d_omega/dt) for the damped compound pendulum."""
        I = self._exp2_props["I"]
        m_total = self._exp2_props["m_total"]
        d = self._exp2_props["d"]
        alpha = -(self.exp2_damping / I) * omega - (m_total * 9.81 * d / I) * np.sin(theta)
        return omega, alpha

    def _exp2_rk4_step(self, theta: float, omega: float, dt: float):
        """Single RK4 integration step; returns (theta_new, omega_new, alpha_new)."""
        k1t, k1o = self._exp2_pendulum_rhs(theta, omega)
        k2t, k2o = self._exp2_pendulum_rhs(theta + 0.5 * dt * k1t, omega + 0.5 * dt * k1o)
        k3t, k3o = self._exp2_pendulum_rhs(theta + 0.5 * dt * k2t, omega + 0.5 * dt * k2o)
        k4t, k4o = self._exp2_pendulum_rhs(theta + dt * k3t, omega + dt * k3o)
        theta_new = theta + (dt / 6.0) * (k1t + 2 * k2t + 2 * k3t + k4t)
        omega_new = omega + (dt / 6.0) * (k1o + 2 * k2o + 2 * k3o + k4o)
        _, alpha_new = self._exp2_pendulum_rhs(theta_new, omega_new)
        return theta_new, omega_new, alpha_new

    def _exp2_update_pose(self, theta: float):
        """Set the USD Xform rotation to reflect current angle."""
        if self.exp2_rotate_op is not None:
            try:
                self.exp2_rotate_op.Set(Gf.Vec3f(0.0, float(np.degrees(theta)), 0.0))
            except Exception:
                pass

    async def _setup_exp2_scene(self):
        """Build the pendulum scene with classmate's exact visual layout.

        Uses the same approach as exp7 (direct UsdGeom — no World object)
        which is proven to work with the WebRTC frame-capture pipeline.
        All visual parameters (sizes, colours, positions, DomeLight) are
        identical to expt2_large_amplitude_pendulum_sim_fixed.py.
        """
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp2: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")

            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(0.0)

            UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1200.0)

            fz = EXP2_FLOOR_Z
            pv = np.array(EXP2_PIVOT_POS)
            r1 = self.exp2_r1
            r2 = self.exp2_r2

            # ---- Grid floor (classmate add_grid_floor lines 63-110) ----
            self._exp2_make_box(stage, "/World/GridFloorBase",
                                np.array([0, 0, fz]), np.array([8, 8, 0.02]),
                                np.array([0.12, 0.12, 0.14]))
            for i, x in enumerate(np.arange(-5.0, 5.01, 0.5)):
                self._exp2_make_box(stage, f"/World/GridLineX_{i}",
                                    np.array([float(x), 0, fz + 0.011]),
                                    np.array([0.01, 10, 0.002]),
                                    np.array([0.85, 0.85, 0.85]))
            for i, y in enumerate(np.arange(-5.0, 5.01, 0.5)):
                self._exp2_make_box(stage, f"/World/GridLineY_{i}",
                                    np.array([0, float(y), fz + 0.011]),
                                    np.array([10, 0.01, 0.002]),
                                    np.array([0.85, 0.85, 0.85]))
            self._exp2_make_box(stage, "/World/GridAxisX",
                                np.array([0, 0, fz + 0.012]),
                                np.array([10, 0.04, 0.004]),
                                np.array([0.95, 0.25, 0.25]))
            self._exp2_make_box(stage, "/World/GridAxisY",
                                np.array([0, 0, fz + 0.012]),
                                np.array([0.04, 10, 0.004]),
                                np.array([0.25, 0.55, 0.95]))

            # ---- VisualPendulum (classmate lines 206-255) ----
            self._exp2_make_box(stage, "/World/PivotMarker",
                                pv, np.array([EXP2_PIVOT_DRAW_SIZE] * 3),
                                np.array([1.0, 1.0, 0.0]))

            pendulum = UsdGeom.Xform.Define(stage, "/World/Pendulum")
            translate_op = pendulum.AddTranslateOp()
            self.exp2_rotate_op = pendulum.AddRotateXYZOp()
            translate_op.Set(Gf.Vec3d(float(pv[0]), float(pv[1]), float(pv[2])))
            self.exp2_rotate_op.Set(Gf.Vec3f(0, 0, 0))

            rod_center = np.array([0, 0, 0.5 * (-r1 + r2)])
            rod_vis_len = r1 + r2
            self._exp2_make_box(stage, "/World/Pendulum/Rod",
                                rod_center,
                                np.array([EXP2_ROD_DRAW_WIDTH, EXP2_ROD_DRAW_DEPTH, rod_vis_len]),
                                np.array([0.92, 0.92, 0.95]))
            self._exp2_make_box(stage, "/World/Pendulum/Bob1",
                                np.array([0, 0, -r1]),
                                np.array([EXP2_BOB_DRAW_SIZE] * 3),
                                np.array([1.0, 0.18, 0.18]))
            self._exp2_make_box(stage, "/World/Pendulum/Bob2",
                                np.array([0, 0, r2]),
                                np.array([EXP2_BOB_DRAW_SIZE] * 3),
                                np.array([0.18, 0.45, 1.0]))

            self.exp2_world = None
            self.exp2_scene_built = True
            self._reset_exp2_state()

            for _ in range(10):
                await app.next_update_async()

            self._force_exp2_camera(stage)
            carb.log_warn("exp2: scene built (classmate layout, UsdGeom)")
        except Exception as exc:
            carb.log_error(f"_setup_exp2_scene: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    @staticmethod
    def _exp2_make_box(stage, path, position, scale, color):
        """Classmate's exact _make_box (line 245-252)."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(float(position[0]), float(position[1]), float(position[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])

    async def _start_exp2_sim(self):
        """Start the RK4 simulation loop for exp2."""
        if self.exp2_sim_task and not self.exp2_sim_task.done():
            self.exp2_sim_task.cancel()

        self._exp2_recompute_props()
        self.exp2_theta = self.exp2_amplitude
        self.exp2_omega = 0.0
        _, self.exp2_alpha = self._exp2_pendulum_rhs(self.exp2_theta, 0.0)
        self.exp2_sim_time = 0.0
        self.exp2_measured_period = 0.0
        self.exp2_period_samples = []
        self.exp2_pos_zero_crossings = []
        self.exp2_prev_theta_sign = 1 if self.exp2_theta >= 0 else -1
        self.exp2_phase = "running"

        self._exp2_update_pose(self.exp2_theta)
        tl = omni.timeline.get_timeline_interface()
        tl.play()

        self.exp2_sim_task = asyncio.ensure_future(self._run_exp2_physics_loop())

    async def _run_exp2_physics_loop(self):
        """RK4 physics loop with Kit-native rendering (same pattern as exp7).

        Every 6 RK4 sub-steps we yield one Kit frame via
        app.next_update_async(), which triggers a viewport render that
        the WebRTC track captures.  6 steps × ~60 fps ≈ 360 Hz physics.
        """
        dt = EXP2_PHYSICS_DT
        render_n = EXP2_RENDER_EVERY_N
        app = omni.kit.app.get_app()

        try:
            while self.exp2_phase == "running":
                for _ in range(render_n):
                    self.exp2_theta, self.exp2_omega, self.exp2_alpha = (
                        self._exp2_rk4_step(self.exp2_theta, self.exp2_omega, dt)
                    )
                    self.exp2_sim_time += dt

                    curr_sign = 1 if self.exp2_theta >= 0 else -1
                    if curr_sign > 0 and self.exp2_prev_theta_sign <= 0:
                        self.exp2_pos_zero_crossings.append(self.exp2_sim_time)
                        if len(self.exp2_pos_zero_crossings) >= 2:
                            latest_p = (self.exp2_pos_zero_crossings[-1]
                                        - self.exp2_pos_zero_crossings[-2])
                            if 0.3 < latest_p < 10.0:
                                self.exp2_period_samples.append(latest_p)
                                if len(self.exp2_period_samples) > 5:
                                    self.exp2_period_samples.pop(0)
                                self.exp2_measured_period = (
                                    sum(self.exp2_period_samples)
                                    / len(self.exp2_period_samples)
                                )
                    self.exp2_prev_theta_sign = curr_sign

                self._exp2_update_pose(self.exp2_theta)
                await app.next_update_async()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            carb.log_error(f"_run_exp2_physics_loop: {exc}")

    async def _run_exp2_full_experiment(self, ws):
        """Run the complete experiment, generate all outputs, send as base64 for
        direct browser download (works behind SSH tunnels / firewalls)."""
        try:
            import base64
            import pandas as pd
            from core.exp2_analysis import (
                compute_pendulum_properties, theoretical_T0, period_series,
                simulate_pure_rk4, measure_period_zero,
                measure_period_two_cycles_zero_cross,
                save_three_curve_plot, save_overlay_plot,
                save_period_comparison_plot, save_error_plot,
                generate_pendulum_report,
            )
            import shutil
            from datetime import datetime

            self._exp2_recompute_props()
            cfg = {
                "rod_mass": EXP2_ROD_MASS, "rod_length": EXP2_ROD_LENGTH,
                "bob_mass_1": self.exp2_bob_mass1, "bob_mass_2": self.exp2_bob_mass2,
                "r1": self.exp2_r1, "r2": self.exp2_r2,
            }
            props = compute_pendulum_properties(cfg)
            T0 = theoretical_T0(props)
            damping = self.exp2_damping
            dt = EXP2_PHYSICS_DT
            small_amp, large_amp = 0.20, 2.80
            amp_start, amp_end, amp_step = 0.20, 2.40, 0.20

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(_PROJECT_ROOT, "outputs", f"expt2_web_{ts}")
            os.makedirs(out_dir, exist_ok=True)

            async def progress(name, num, total):
                if not ws.closed:
                    await ws.send_json({"type": "exp2_progress", "data": {
                        "phase": name, "current": num, "total": total}})

            await progress("Small amplitude simulation", 1, 5)
            small_df = simulate_pure_rk4(props, small_amp, damping, dt, 4.0, T0)
            small_df.to_csv(os.path.join(out_dir, "small_amp.csv"), index=False)
            save_three_curve_plot(small_df, f"Small-Amplitude (A0={small_amp:.2f} rad)",
                                  os.path.join(out_dir, "small_amp_plot.png"))
            await asyncio.sleep(0.01)

            await progress("Large amplitude simulation", 2, 5)
            large_df = simulate_pure_rk4(props, large_amp, damping, dt, 4.0, T0)
            large_df.to_csv(os.path.join(out_dir, "large_amp.csv"), index=False)
            save_three_curve_plot(large_df, f"Large-Amplitude (A0={large_amp:.2f} rad)",
                                  os.path.join(out_dir, "large_amp_plot.png"))
            save_overlay_plot(small_df, large_df, small_amp, large_amp,
                              os.path.join(out_dir, "small_vs_large_theta.png"))
            await asyncio.sleep(0.01)

            await progress("Period-zero measurement", 3, 5)
            pz_df = simulate_pure_rk4(props, 0.10, damping, dt, 14.0, T0)
            pz_df.to_csv(os.path.join(out_dir, "period_zero.csv"), index=False)
            T0_measured, amp_mid = measure_period_zero(pz_df)
            await asyncio.sleep(0.01)

            await progress("Amplitude sweep", 4, 5)
            amps = np.arange(amp_start, amp_end + 1e-12, amp_step)
            rows = []
            for A in amps:
                df = simulate_pure_rk4(props, float(A), damping, dt, 3.5, T0)
                df.to_csv(os.path.join(out_dir, f"amp_{A:.2f}_timeseries.csv"), index=False)
                T_meas, A_meas = measure_period_two_cycles_zero_cross(df)
                rows.append({
                    "amp_set": A, "amp_measured": A_meas,
                    "period_measured": T_meas, "T0_theory": T0,
                    "T0_measured_from_period_zero": T0_measured,
                    "T_series_2term": period_series(T0, A_meas, 2) if np.isfinite(A_meas) else np.nan,
                    "T_series_3term": period_series(T0, A_meas, 3) if np.isfinite(A_meas) else np.nan,
                    "T_series_4term": period_series(T0, A_meas, 4) if np.isfinite(A_meas) else np.nan,
                    "T_series_5term": period_series(T0, A_meas, 5) if np.isfinite(A_meas) else np.nan,
                })
            summary_df = pd.DataFrame(rows)
            summary_df.to_csv(os.path.join(out_dir, "period_summary.csv"), index=False)
            save_period_comparison_plot(summary_df, os.path.join(out_dir, "period_vs_amplitude.png"))
            save_error_plot(summary_df, os.path.join(out_dir, "small_angle_error.png"))
            await asyncio.sleep(0.01)

            await progress("Generating report & packaging", 5, 5)
            report_path = generate_pendulum_report(
                out_dir, props, T0, damping,
                small_amp, large_amp, amp_start, amp_end, amp_step, dt,
                summary_df, T0_measured, amp_mid,
            )
            import zipfile
            zip_path = out_dir + ".zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in os.listdir(out_dir):
                    if fname.startswith("amp_") and fname.endswith("_timeseries.csv"):
                        continue
                    if fname == "period_zero.csv":
                        continue
                    zf.write(os.path.join(out_dir, fname), fname)

            def _read_b64(fpath):
                with open(fpath, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")

            result_data = {
                "T0_theory": round(T0, 6),
                "T0_measured": round(float(T0_measured), 6),
                "sweep_points": len(rows),
                "plots": {
                    "overlay": "data:image/png;base64," + _read_b64(os.path.join(out_dir, "small_vs_large_theta.png")),
                    "period": "data:image/png;base64," + _read_b64(os.path.join(out_dir, "period_vs_amplitude.png")),
                    "error": "data:image/png;base64," + _read_b64(os.path.join(out_dir, "small_angle_error.png")),
                    "small_amp": "data:image/png;base64," + _read_b64(os.path.join(out_dir, "small_amp_plot.png")),
                    "large_amp": "data:image/png;base64," + _read_b64(os.path.join(out_dir, "large_amp_plot.png")),
                },
                "report_md": _read_b64(report_path),
                "period_csv": _read_b64(os.path.join(out_dir, "period_summary.csv")),
                "zip_b64": _read_b64(zip_path),
            }

            if not ws.closed:
                await ws.send_json({"type": "exp2_report_ready", "data": result_data})
            self._exp2_update_pose(0.0)
            carb.log_warn(f"exp2: full experiment complete → {out_dir}")

        except Exception as exc:
            carb.log_error(f"_run_exp2_full_experiment: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())
            if not ws.closed:
                await ws.send_json({"type": "exp2_progress", "data": {
                    "phase": f"Error: {exc}", "current": 0, "total": 0}})

    # --- Experiment 3 — ballistic pendulum (PhysX compound body + joint) ---

    async def _setup_exp3_scene(self):
        """Build the ballistic-pendulum scene procedurally.

        Scene layout (world-frame, Z-up, gravity = −9.81 m/s²):

            +Z (up)
             │     ┌─────────┐ pivot (kinematic, at (0, 0, EXP3_PIVOT_HEIGHT))
             │     │         │
             │     │ rod     │  thin vertical rod (compound child collider)
             │     │         │  body1 of the revolute joint
             │     │         │
             │     └──┬──────┘
             │        │        catcher CM at (0, 0, PIVOT_HEIGHT − L)
             │   ┌────┴────┐
             │   │ catcher │   4-walled "cup" opening toward −X (back wall +
             │   │  cup    │   left/right/floor walls ⇒ traps the ball on
             │   └─────────┘   impact by geometry, as a styrofoam catcher does)
             │
             │   ball  ──▶ +X   (fired on `start_simulation` with v0 toward
             │                    the catcher opening)
             └──────────────► +X
             launcher (visual only, on −X side)

        All collision shapes live on a single parent rigid body
        `/World/exp3/pendulum` so PhysX treats rod + cup as one compound
        body welded to the joint. The ball is a separate dynamic cuboid.
        A zero-restitution, high-friction material is bound to both sides
        so the collision is maximally inelastic (classical ballistic
        pendulum assumption).
        """
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp3: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")
            UsdGeom.Xform.Define(stage, "/World/exp3")

            # Physics scene — standard Earth gravity along −Z
            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(9.81)

            UsdLux.DomeLight.Define(stage, "/World/exp3/DomeLight").CreateIntensityAttr(1500.0)

            # Floor (visual only)
            self._exp3_make_visual(
                stage, "/World/exp3/ground",
                pos=(0, 0, EXP3_GROUND_Z),
                scale=(4.0, 3.0, 0.02),
                color=(0.11, 0.11, 0.13),
            )
            # Grid lines (light cosmetic detail, same style as exp5/exp7)
            for i, xv in enumerate(np.arange(-1.5, 1.51, 0.25)):
                self._exp3_make_visual(
                    stage, f"/World/exp3/GridX_{i}",
                    pos=(float(xv), 0, EXP3_GROUND_Z + 0.011),
                    scale=(0.006, 2.5, 0.002),
                    color=(0.75, 0.75, 0.78),
                )
            for i, yv in enumerate(np.arange(-1.25, 1.26, 0.25)):
                self._exp3_make_visual(
                    stage, f"/World/exp3/GridY_{i}",
                    pos=(0, float(yv), EXP3_GROUND_Z + 0.011),
                    scale=(3.0, 0.006, 0.002),
                    color=(0.75, 0.75, 0.78),
                )

            # -------- Support stand (visual only) --------------------------
            # A tall post on +Y holds a horizontal arm that carries the
            # pivot at (0,0,PIVOT_HEIGHT). Offset in +Y keeps the swing
            # plane (y≈0) unobstructed from the −Y camera view.
            post_y = 0.12
            post_top = EXP3_PIVOT_HEIGHT - 0.015
            self._exp3_make_visual(
                stage, "/World/exp3/post",
                pos=(0, post_y, (EXP3_GROUND_Z + post_top) / 2.0),
                scale=(0.05, 0.05, max(0.01, post_top - EXP3_GROUND_Z)),
                color=(0.30, 0.30, 0.34),
            )
            self._exp3_make_visual(
                stage, "/World/exp3/post_arm",
                pos=(0, post_y / 2.0, EXP3_PIVOT_HEIGHT),
                scale=(0.04, post_y, 0.04),
                color=(0.30, 0.30, 0.34),
            )
            self._exp3_make_visual(
                stage, "/World/exp3/post_base",
                pos=(0, post_y, EXP3_GROUND_Z + 0.015),
                scale=(0.22, 0.22, 0.025),
                color=(0.22, 0.22, 0.25),
            )

            # -------- Launcher (visual only, on −X side) -------------------
            # Muzzle is aimed at the centre of the catcher opening.
            catcher_front_x = -EXP3_CATCHER_W / 2.0  # opening face x-coord
            muzzle_x = catcher_front_x - EXP3_LAUNCHER_GAP
            catcher_z = EXP3_PIVOT_HEIGHT - self.exp3_L
            self._exp3_make_visual(
                stage, EXP3_LAUNCHER_PATH + "_barrel",
                pos=(muzzle_x - 0.10, 0, catcher_z),
                scale=(0.22, 0.035, 0.035),
                color=(0.85, 0.20, 0.15),
            )
            self._exp3_make_visual(
                stage, EXP3_LAUNCHER_PATH + "_body",
                pos=(muzzle_x - 0.22, 0, catcher_z - 0.03),
                scale=(0.10, 0.09, 0.09),
                color=(0.30, 0.32, 0.38),
            )
            self._exp3_make_visual(
                stage, EXP3_LAUNCHER_PATH + "_base",
                pos=(muzzle_x - 0.22, 0, EXP3_GROUND_Z + 0.015),
                scale=(0.18, 0.18, 0.025),
                color=(0.22, 0.22, 0.25),
            )

            # -------- Kinematic pivot (body0 of revolute joint) ------------
            self._exp3_make_pivot(
                stage, EXP3_PIVOT_PATH,
                pos=(0, 0, EXP3_PIVOT_HEIGHT),
                scale=(0.05, 0.05, 0.05),
                color=(0.95, 0.75, 0.10),
            )

            # -------- Pendulum compound rigid body (body1) -----------------
            # Parent Xform carries RigidBodyAPI + MassAPI. Child cubes carry
            # CollisionAPI only ⇒ PhysX welds them into one compound body.
            self._exp3_build_pendulum_body(stage)

            # -------- Revolute joint (Y-axis, swings in XZ plane) ----------
            self._exp3_make_joint(stage, self.exp3_L)

            # -------- Ball (independent dynamic body) ----------------------
            # Spawn just outside the catcher opening, aimed at its centre.
            ball_x = catcher_front_x - EXP3_BALL_SPAWN_OFFSET
            self._exp3_make_ball(
                stage, EXP3_BALL_PATH,
                pos=(ball_x, 0, catcher_z),
                mass=self.exp3_ball_mass,
                color=(0.92, 0.85, 0.20),
            )

            # -------- Physics materials ------------------------------------
            # Catcher: zero restitution + high friction → traps the ball.
            # Ball:    same, so the pair behaves perfectly inelastically.
            self._exp3_make_material(stage, EXP3_MATERIAL_CATCHER_PATH,
                                     restitution=0.0, static_fr=1.2, dyn_fr=1.0)
            self._exp3_make_material(stage, EXP3_MATERIAL_BALL_PATH,
                                     restitution=0.0, static_fr=0.8, dyn_fr=0.6)
            self._exp3_bind_material(
                stage, EXP3_PENDULUM_PATH, EXP3_MATERIAL_CATCHER_PATH,
            )
            self._exp3_bind_material(
                stage, EXP3_BALL_PATH, EXP3_MATERIAL_BALL_PATH,
            )

            self.exp3_scene_built = True
            self.exp3_phase = "idle"
            self.exp3_theta = 0.0
            self.exp3_omega = 0.0
            self.exp3_theta_max = 0.0
            self.exp3_v0_measured = 0.0
            self.exp3_collision_detected = False
            self.exp3_prev_omega_sign = 0

            for _ in range(8):
                await app.next_update_async()

            self._force_exp3_camera(stage)
            carb.log_warn(
                f"exp3: scene built  m_ball={self.exp3_ball_mass:.4f}  "
                f"m_pend={self.exp3_pend_mass:.4f}  L={self.exp3_L:.3f}  "
                f"v0={self.exp3_v0:.2f}"
            )
        except Exception as exc:
            carb.log_error(f"_setup_exp3_scene: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    # ---- exp3 scene primitive helpers --------------------------------------

    @staticmethod
    def _exp3_make_visual(stage, path, pos, scale, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])

    @staticmethod
    def _exp3_make_pivot(stage, path, pos, scale, color):
        """Kinematic static cube — body0 of the revolute joint."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()
        rb = UsdPhysics.RigidBodyAPI.Apply(prim)
        rb.CreateKinematicEnabledAttr(True)

    def _exp3_build_pendulum_body(self, stage):
        """Build the compound pendulum rigid body: rod + 4-walled catcher cup.

        Local frame convention:
          - parent Xform at world (0, 0, PIVOT_HEIGHT − L); CM sits here
            when the bar hangs straight down (θ=0).
          - local +Z points from catcher centre up to the pivot.
          - local +X (once rotated by θ) is the "ball-entering" direction
            in the world. At rest (θ=0), local +X == world +X.

        The compound colliders are:
          - rod:       thin square prism along local +Z, length = L
          - back wall: thin plate on +X face (behind the ball on impact)
          - left wall: thin plate on +Y face (+Y is the stand-side; OK)
          - right wall: thin plate on −Y face
          - floor:     thin plate on −Z face of the cup opening

        The opening points toward local −X, i.e. world −X at rest — which
        is exactly where the launcher sits and the ball approaches from.
        """
        parent_path = EXP3_PENDULUM_PATH
        L = float(self.exp3_L)
        t_rod = float(EXP3_ROD_THICKNESS)
        wx = float(EXP3_CATCHER_W)
        wh = float(EXP3_CATCHER_H)
        wt = float(EXP3_CATCHER_WALL_T)

        # Parent Xform at the catcher centre (rest pose). We give it an
        # identity orient+scale so child local coordinates are physical
        # meters. PhysX RigidBody is applied here.
        parent = UsdGeom.Xform.Define(stage, parent_path)
        xf = UsdGeom.Xformable(parent.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, EXP3_PIVOT_HEIGHT - L))
        xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        xf.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))

        parent_prim = parent.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(parent_prim)
        UsdPhysics.MassAPI.Apply(parent_prim)
        UsdPhysics.MassAPI(parent_prim).CreateMassAttr().Set(float(self.exp3_pend_mass))
        # Provide an explicit CM override at the local origin (catcher
        # centre) — this is also the joint-to-CM distance L from the pivot.
        UsdPhysics.MassAPI(parent_prim).CreateCenterOfMassAttr().Set(Gf.Vec3f(0, 0, 0))
        rb = PhysxSchema.PhysxRigidBodyAPI.Apply(parent_prim)
        rb.CreateSolverPositionIterationCountAttr(EXP3_SOLVER_POS_ITERS)
        rb.CreateSolverVelocityIterationCountAttr(EXP3_SOLVER_VEL_ITERS)
        rb.CreateLinearDampingAttr(0.0)
        rb.CreateAngularDampingAttr(0.0)
        rb.CreateSleepThresholdAttr(0.0)
        rb.CreateEnableCCDAttr(True)  # critical — ball moves fast on impact

        # --- Child collider cubes (no RigidBodyAPI on children) ----------
        # Rod: runs from catcher top (local z = +wh/2) up to pivot height
        # (local z = +L). Its centre is at z = (wh/2 + L)/2, length = L − wh/2.
        rod_len = max(0.02, L - wh / 2.0)
        rod_cz = (wh / 2.0 + L) / 2.0
        self._exp3_child_collider(
            stage, f"{parent_path}/rod",
            pos=(0, 0, rod_cz),
            scale=(t_rod, t_rod, rod_len),
            color=(0.85, 0.85, 0.88),
        )

        # Back wall: opposite the opening. At local +X face.
        self._exp3_child_collider(
            stage, f"{parent_path}/back",
            pos=(+wx / 2.0 - wt / 2.0, 0, 0),
            scale=(wt, wx, wh),
            color=(0.92, 0.72, 0.42),   # styrofoam-ish
        )
        # Left wall (+Y)
        self._exp3_child_collider(
            stage, f"{parent_path}/left",
            pos=(0, +wx / 2.0 - wt / 2.0, 0),
            scale=(wx, wt, wh),
            color=(0.92, 0.72, 0.42),
        )
        # Right wall (−Y)
        self._exp3_child_collider(
            stage, f"{parent_path}/right",
            pos=(0, -wx / 2.0 + wt / 2.0, 0),
            scale=(wx, wt, wh),
            color=(0.92, 0.72, 0.42),
        )
        # Floor (−Z), stops ball falling out through the bottom
        self._exp3_child_collider(
            stage, f"{parent_path}/floor",
            pos=(0, 0, -wh / 2.0 + wt / 2.0),
            scale=(wx, wx, wt),
            color=(0.82, 0.62, 0.32),
        )
        # Thin lip on the top so the ball can't climb out over the top
        self._exp3_child_collider(
            stage, f"{parent_path}/top",
            pos=(0, 0, +wh / 2.0 - wt / 2.0),
            scale=(wx, wx, wt),
            color=(0.82, 0.62, 0.32),
        )

    @staticmethod
    def _exp3_child_collider(stage, path, pos, scale, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()
        UsdPhysics.CollisionAPI.Apply(prim)
        col = PhysxSchema.PhysxCollisionAPI.Apply(prim)
        col.CreateContactOffsetAttr(0.0015)
        col.CreateRestOffsetAttr(0.0)

    def _exp3_make_ball(self, stage, path, pos, mass, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        xf.AddScaleOp().Set(Gf.Vec3f(EXP3_BALL_SIZE, EXP3_BALL_SIZE, EXP3_BALL_SIZE))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()

        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim)
        UsdPhysics.MassAPI(prim).CreateMassAttr().Set(float(mass))

        rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rb.CreateSolverPositionIterationCountAttr(EXP3_SOLVER_POS_ITERS)
        rb.CreateSolverVelocityIterationCountAttr(EXP3_SOLVER_VEL_ITERS)
        rb.CreateLinearDampingAttr(0.0)
        rb.CreateAngularDampingAttr(0.0)
        rb.CreateSleepThresholdAttr(0.0)
        rb.CreateEnableCCDAttr(True)          # fast projectile
        rb.CreateMaxLinearVelocityAttr(100.0)

        col = PhysxSchema.PhysxCollisionAPI.Apply(prim)
        col.CreateContactOffsetAttr(0.0015)
        col.CreateRestOffsetAttr(0.0)

    @staticmethod
    def _exp3_make_joint(stage, L: float):
        """Revolute joint around Y so the pendulum swings in XZ.

        body0 = pivot at world (0,0,PIVOT_HEIGHT)          — local (0,0,0)
        body1 = pendulum parent at world (0,0,PIVOT_HEIGHT−L).
                Locally, the pivot point is at z=+L above the parent origin
                (since the parent frame lives at the catcher centre).
        """
        jp = stage.GetPrimAtPath(EXP3_JOINT_PATH)
        if jp and jp.IsValid():
            stage.RemovePrim(EXP3_JOINT_PATH)
        joint = UsdPhysics.RevoluteJoint.Define(stage, EXP3_JOINT_PATH)
        joint.CreateBody0Rel().SetTargets([EXP3_PIVOT_PATH])
        joint.CreateBody1Rel().SetTargets([EXP3_PENDULUM_PATH])
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, float(L)))
        joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateAxisAttr().Set("Y")

    @staticmethod
    def _exp3_make_material(stage, path: str, restitution: float,
                             static_fr: float, dyn_fr: float):
        mat_prim = stage.GetPrimAtPath(path)
        if mat_prim and mat_prim.IsValid():
            api = UsdPhysics.MaterialAPI(mat_prim)
            api.GetStaticFrictionAttr().Set(float(static_fr))
            api.GetDynamicFrictionAttr().Set(float(dyn_fr))
            api.GetRestitutionAttr().Set(float(restitution))
            return
        mat = UsdShade.Material.Define(stage, path)
        UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        api = UsdPhysics.MaterialAPI(mat.GetPrim())
        api.CreateStaticFrictionAttr().Set(float(static_fr))
        api.CreateDynamicFrictionAttr().Set(float(dyn_fr))
        api.CreateRestitutionAttr().Set(float(restitution))

        PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim())
        phx = PhysxSchema.PhysxMaterialAPI(mat.GetPrim())
        phx.CreateFrictionCombineModeAttr().Set("max")
        phx.CreateRestitutionCombineModeAttr().Set("min")

    @staticmethod
    def _exp3_bind_material(stage, target_path: str, material_path: str):
        """Bind a PhysicsMaterial to every collider under target_path."""
        mat_prim = stage.GetPrimAtPath(material_path)
        tgt_prim = stage.GetPrimAtPath(target_path)
        if not (mat_prim and mat_prim.IsValid()
                and tgt_prim and tgt_prim.IsValid()):
            return
        if not tgt_prim.HasAPI(UsdShade.MaterialBindingAPI):
            UsdShade.MaterialBindingAPI.Apply(tgt_prim)
        UsdShade.MaterialBindingAPI(tgt_prim).Bind(UsdShade.Material(mat_prim))
        # Also bind each direct child that has a CollisionAPI (compound body)
        for child in tgt_prim.GetChildren():
            if child.HasAPI(UsdPhysics.CollisionAPI):
                if not child.HasAPI(UsdShade.MaterialBindingAPI):
                    UsdShade.MaterialBindingAPI.Apply(child)
                UsdShade.MaterialBindingAPI(child).Bind(UsdShade.Material(mat_prim))

    # ---- exp3 dynamics & telemetry helpers ---------------------------------

    async def _fire_exp3_ball(self):
        """Reset the ball to spawn pose, apply v0 toward +X, start PhysX."""
        try:
            if not self.exp3_scene_built:
                await self._setup_exp3_scene()

            tl = omni.timeline.get_timeline_interface()
            tl.stop()
            await asyncio.sleep(0.05)

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            # Reset ball pose
            catcher_front_x = -EXP3_CATCHER_W / 2.0
            catcher_z = EXP3_PIVOT_HEIGHT - float(self.exp3_L)
            ball_x = catcher_front_x - EXP3_BALL_SPAWN_OFFSET

            ball_prim = stage.GetPrimAtPath(EXP3_BALL_PATH)
            if ball_prim and ball_prim.IsValid():
                xf = UsdGeom.Xformable(ball_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(ball_x, 0.0, catcher_z))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(EXP3_BALL_SIZE, EXP3_BALL_SIZE, EXP3_BALL_SIZE))

            # Reset pendulum to vertical rest pose
            pend_prim = stage.GetPrimAtPath(EXP3_PENDULUM_PATH)
            if pend_prim and pend_prim.IsValid():
                xf = UsdGeom.Xformable(pend_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, catcher_z))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))

            # Update masses from current slider values
            await self._apply_mass_at(EXP3_BALL_PATH, self.exp3_ball_mass)
            await self._apply_mass_at(EXP3_PENDULUM_PATH, self.exp3_pend_mass)

            # Reset measurement state
            self.exp3_theta = 0.0
            self.exp3_omega = 0.0
            self.exp3_theta_max = 0.0
            self.exp3_v0_measured = 0.0
            self.exp3_ball_velocity = 0.0
            self.exp3_collision_detected = False
            self.exp3_prev_omega_sign = 0
            self.exp3_phase = "firing"
            self.exp3_fire_time = time.time()
            self.exp3_settle_deadline = self.exp3_fire_time + EXP3_AUTO_SETTLE_SECONDS

            self.simulation_control_enabled = True
            tl.play()
            await asyncio.sleep(EXP3_WARMUP_SECONDS)

            # Apply v0 through dynamic_control — PhysX now owns the motion.
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            dc = self._dc_interface
            h = dc.get_rigid_body(EXP3_BALL_PATH)
            if h != _dynamic_control.INVALID_HANDLE:
                dc.set_rigid_body_linear_velocity(h, (float(self.exp3_v0), 0.0, 0.0))
                dc.set_rigid_body_angular_velocity(h, (0.0, 0.0, 0.0))
            # Pendulum starts at rest
            ph = dc.get_rigid_body(EXP3_PENDULUM_PATH)
            if ph != _dynamic_control.INVALID_HANDLE:
                dc.set_rigid_body_linear_velocity(ph, (0.0, 0.0, 0.0))
                dc.set_rigid_body_angular_velocity(ph, (0.0, 0.0, 0.0))

            carb.log_warn(
                f"exp3: fired  v0={self.exp3_v0:.2f}  m_ball={self.exp3_ball_mass:.4f}  "
                f"m_pend={self.exp3_pend_mass:.4f}  L={self.exp3_L:.3f}"
            )
        except Exception as exc:
            carb.log_error(f"_fire_exp3_ball: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    async def _reset_exp3(self):
        """Return everything to idle (pre-fire) pose without rebuilding."""
        self.exp3_phase = "idle"
        self.exp3_theta = 0.0
        self.exp3_omega = 0.0
        self.exp3_theta_max = 0.0
        self.exp3_v0_measured = 0.0
        self.exp3_ball_velocity = 0.0
        self.exp3_collision_detected = False
        self.exp3_prev_omega_sign = 0
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            catcher_z = EXP3_PIVOT_HEIGHT - float(self.exp3_L)
            # Pendulum to vertical
            pend = stage.GetPrimAtPath(EXP3_PENDULUM_PATH)
            if pend and pend.IsValid():
                xf = UsdGeom.Xformable(pend)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, catcher_z))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))
            # Ball back to spawn
            ball = stage.GetPrimAtPath(EXP3_BALL_PATH)
            if ball and ball.IsValid():
                catcher_front_x = -EXP3_CATCHER_W / 2.0
                ball_x = catcher_front_x - EXP3_BALL_SPAWN_OFFSET
                xf = UsdGeom.Xformable(ball)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(ball_x, 0.0, catcher_z))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(EXP3_BALL_SIZE, EXP3_BALL_SIZE, EXP3_BALL_SIZE))
        except Exception as exc:
            carb.log_error(f"_reset_exp3: {exc}")

    def _read_exp3_pendulum_state(self):
        """Return (theta_rad, omega_rad_s) from the live pendulum pose."""
        theta = 0.0
        omega = 0.0
        try:
            stage = omni.usd.get_context().get_stage()
            if stage:
                prim = stage.GetPrimAtPath(EXP3_PENDULUM_PATH)
                if prim and prim.IsValid():
                    mtx = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
                    q = mtx.ExtractRotationQuat()
                    qw = float(q.GetReal())
                    qy = float(q.GetImaginary()[1])
                    theta = 2.0 * math.atan2(qy, qw)
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(EXP3_PENDULUM_PATH)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_angular_velocity(h)
                if v:
                    omega = float(v[1])
        except Exception:
            pass
        return theta, omega

    def _read_exp3_ball_speed(self) -> float:
        """Return the ball's scalar linear speed (m/s)."""
        try:
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(EXP3_BALL_PATH)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_linear_velocity(h)
                if v:
                    return float(math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]))
        except Exception:
            pass
        return 0.0

    def _exp3_update_swing_metrics(self, theta: float, omega: float, now: float):
        """Track |θ|_max during the upswing and snap v0_measured once ω
        first crosses zero (⇒ pendulum reached its apex).

        The ballistic pendulum formula:
            v0 = (m_ball + m_pend) / m_ball · √(2 g L (1 − cos θ_max))
        Combined momentum + energy conservation, derived in the lab PDF.
        """
        abs_theta = abs(theta)
        if abs_theta > self.exp3_theta_max:
            self.exp3_theta_max = abs_theta

        # Detect first sign-flip of ω after fire → apex reached → "settled"
        curr_sign = 1 if omega > 1e-4 else (-1 if omega < -1e-4 else 0)
        if (self.exp3_phase in ("firing", "swinging") and curr_sign != 0
                and self.exp3_prev_omega_sign != 0
                and curr_sign != self.exp3_prev_omega_sign):
            # ω changed sign — the pendulum is at apex.
            self.exp3_v0_measured = self._exp3_compute_v0(self.exp3_theta_max)
            self.exp3_phase = "settled"
        self.exp3_prev_omega_sign = curr_sign if curr_sign != 0 else self.exp3_prev_omega_sign

        # Phase auto-transition when the ball starts driving the pendulum
        if self.exp3_phase == "firing" and abs_theta > math.radians(1.5):
            self.exp3_phase = "swinging"
            self.exp3_collision_detected = True
            self.exp3_collision_time = now

        # Safety timeout — never leave the UI stuck
        if (self.exp3_phase in ("firing", "swinging")
                and now > self.exp3_settle_deadline):
            self.exp3_v0_measured = self._exp3_compute_v0(self.exp3_theta_max)
            self.exp3_phase = "settled"

    def _exp3_compute_v0(self, theta_max: float) -> float:
        """Ballistic-pendulum inversion: v0 from θmax (Eq. 4 in PDF)."""
        g = 9.81
        M = float(self.exp3_ball_mass) + float(self.exp3_pend_mass)
        L = max(1e-6, float(self.exp3_L))
        h = L * (1.0 - math.cos(float(theta_max)))
        if self.exp3_ball_mass <= 1e-9 or h <= 0.0:
            return 0.0
        return (M / self.exp3_ball_mass) * math.sqrt(2.0 * g * h)

    # ---- exp3 camera -------------------------------------------------------
    # Viewed from behind the launcher (−X) and slightly +Y above ground so
    # the swing plane (y≈0) is visible with the stand peeking from +Y.
    _EXP3_CAM_EYE = Gf.Vec3d(-0.75, -1.35, 0.70)
    _EXP3_CAM_TGT = Gf.Vec3d(0.0, 0.0, 0.55)
    _EXP3_CAM_FL = 22.0

    def _force_exp3_camera(self, stage=None):
        eye = self._EXP3_CAM_EYE
        tgt = self._EXP3_CAM_TGT
        fl = self._EXP3_CAM_FL
        try:
            self._try_set_camera_view(eye, tgt)
            if stage is None:
                stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(cam_path)
            if not cam_prim or not cam_prim.IsValid():
                cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
            if cam_prim and cam_prim.IsValid():
                mtx = self._build_lookat_matrix(eye, tgt)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(fl)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            self.camera_controller.set_from_eye_target(eye, tgt)
            carb.log_warn(f"exp3 camera: eye={eye} tgt={tgt} fl={fl}")
        except Exception as exc:
            carb.log_error(f"_force_exp3_camera: {exc}")

    async def _deferred_exp3_camera(self):
        for delay in (1.0, 2.0, 4.0):
            await asyncio.sleep(delay)
            if self.current_experiment != "3":
                return
            self._force_exp3_camera()

    # --- Experiment 5 — physical pendulum (PhysX revolute joint) -----------

    async def _setup_exp5_scene(self):
        """Build the physical pendulum scene procedurally.

        The bar (uniform rod) is a DynamicCuboid attached to a kinematic pivot
        via a revolute joint around the **Y-axis**, so gravity (-Z) produces
        a real torque and the bar swings in the XZ plane.  The original
        standalone script used a Z-axis joint which, under Z-up gravity,
        yields no torque and no oscillation — we fix that here.

        Physics:
            period  T = 2π √((L²/12 + x²) / (g · x))
            minimum at x = L / √12
        """
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp5: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")
            UsdGeom.Xform.Define(stage, "/World/exp5")

            # Physics scene — standard Earth gravity
            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(9.81)

            UsdLux.DomeLight.Define(stage, "/World/exp5/DomeLight").CreateIntensityAttr(1200.0)

            # Ground + grid (visual only, no collision)
            self._exp5_make_visual(
                stage, "/World/exp5/ground",
                pos=(0, 0, EXP5_GROUND_Z),
                scale=(6.0, 6.0, 0.02),
                color=(0.12, 0.12, 0.14),
            )
            for i, xv in enumerate(np.arange(-2.0, 2.01, 0.5)):
                self._exp5_make_visual(
                    stage, f"/World/exp5/GridX_{i}",
                    pos=(float(xv), 0, EXP5_GROUND_Z + 0.011),
                    scale=(0.008, 4.0, 0.002),
                    color=(0.78, 0.78, 0.80),
                )
            for i, yv in enumerate(np.arange(-2.0, 2.01, 0.5)):
                self._exp5_make_visual(
                    stage, f"/World/exp5/GridY_{i}",
                    pos=(0, float(yv), EXP5_GROUND_Z + 0.011),
                    scale=(4.0, 0.008, 0.002),
                    color=(0.78, 0.78, 0.80),
                )

            # Pivot support — L-bracket offset into +Y so the swing plane (XZ,
            # at y=0) is never occluded by the stand. A vertical column rises
            # from the floor at y=+0.10, and a short horizontal arm reaches
            # back to the pivot at y=0. This matches how a real classroom
            # pendulum stand holds the pivot from behind.
            post_top = EXP5_PIVOT_HEIGHT - 0.01
            post_y = 0.10
            self._exp5_make_visual(
                stage, "/World/exp5/post",
                pos=(0, post_y, (EXP5_GROUND_Z + post_top) / 2.0),
                scale=(0.04, 0.04, max(0.01, post_top - EXP5_GROUND_Z)),
                color=(0.30, 0.30, 0.35),
            )
            # Horizontal arm: thin cross-bar from post top to pivot (y=0)
            self._exp5_make_visual(
                stage, "/World/exp5/post_arm",
                pos=(0, post_y / 2.0, EXP5_PIVOT_HEIGHT),
                scale=(0.035, post_y, 0.035),
                color=(0.30, 0.30, 0.35),
            )
            # Small base plate at the post foot for visual stability
            self._exp5_make_visual(
                stage, "/World/exp5/post_base",
                pos=(0, post_y, EXP5_GROUND_Z + 0.015),
                scale=(0.18, 0.18, 0.025),
                color=(0.22, 0.22, 0.25),
            )

            # Kinematic pivot cube (body0 of joint)
            self._exp5_make_pivot(
                stage, EXP5_PIVOT_PATH,
                pos=(0, 0, EXP5_PIVOT_HEIGHT),
                scale=(0.05, 0.05, 0.05),
                color=(0.95, 0.75, 0.10),
            )

            # Dynamic bar (body1 of joint) — hanging straight down at rest.
            # Bar local frame: long axis = Z (length = L), cross-section in XY.
            # CM placed at pivot height − x, so joint-to-CM distance = x.
            bar_cm_z = EXP5_PIVOT_HEIGHT - self.exp5_x
            self._exp5_make_bar(
                stage, EXP5_BAR_PATH,
                pos=(0, 0, bar_cm_z),
                scale=(EXP5_BAR_THICKNESS, EXP5_BAR_THICKNESS, self.exp5_L),
                mass=self.exp5_m,
                color=(0.20, 0.60, 1.00),
            )

            # Revolute joint (Y-axis) — swings in XZ plane
            self._exp5_make_joint(stage, self.exp5_x)

            # Frictionless physics material (no energy loss from contacts)
            self._exp5_make_material(stage)
            mat = stage.GetPrimAtPath(EXP5_MATERIAL_PATH)
            bar_prim = stage.GetPrimAtPath(EXP5_BAR_PATH)
            if mat and mat.IsValid() and bar_prim and bar_prim.IsValid():
                if not bar_prim.HasAPI(UsdShade.MaterialBindingAPI):
                    UsdShade.MaterialBindingAPI.Apply(bar_prim)
                UsdShade.MaterialBindingAPI(bar_prim).Bind(UsdShade.Material(mat))

            self.exp5_scene_built = True
            self.exp5_phase = "idle"
            self.exp5_theta = 0.0
            self.exp5_omega = 0.0
            self.exp5_measured_period = 0.0
            self.exp5_period_samples = []
            self.exp5_pos_zero_crossings = []
            self.exp5_prev_theta_sign = 1

            for _ in range(8):
                await app.next_update_async()

            self._force_exp5_camera(stage)
            carb.log_warn(
                f"exp5: scene built  m={self.exp5_m:.3f}  L={self.exp5_L:.3f}  "
                f"x={self.exp5_x:.3f}  θ₀={self.exp5_theta0_deg:.1f}°"
            )
        except Exception as exc:
            carb.log_error(f"_setup_exp5_scene: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    @staticmethod
    def _exp5_make_visual(stage, path, pos, scale, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])

    @staticmethod
    def _exp5_make_pivot(stage, path, pos, scale, color):
        """Kinematic static cube acting as body0 of the revolute joint."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()
        rb = UsdPhysics.RigidBodyAPI.Apply(prim)
        rb.CreateKinematicEnabledAttr(True)

    @staticmethod
    def _exp5_make_bar(stage, path, pos, scale, mass, color):
        """Dynamic rigid body — the swinging bar.

        Initial orientation = identity (bar hangs straight down along its local
        Z-axis).  A small initial angle is applied on `start_simulation` by
        rewriting the xform and letting PhysX pick up the new default pose.
        """
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()

        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim)
        UsdPhysics.MassAPI(prim).CreateMassAttr().Set(float(mass))

        rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rb.CreateSolverPositionIterationCountAttr(EXP5_SOLVER_POS_ITERS)
        rb.CreateSolverVelocityIterationCountAttr(EXP5_SOLVER_VEL_ITERS)
        rb.CreateLinearDampingAttr(0.0)
        rb.CreateAngularDampingAttr(0.0)
        rb.CreateSleepThresholdAttr(0.0)

    @staticmethod
    def _exp5_make_joint(stage, pivot_distance_x: float):
        """Revolute joint around Y so the bar swings in the vertical XZ plane.

        localPos0 = (0, 0, 0)        joint point at pivot's centre (body0)
        localPos1 = (0, 0, +x)       in bar's local frame, the point that
                                     sits x metres above the bar's CM along
                                     its local Z — coincides with the pivot.
        """
        jp = stage.GetPrimAtPath(EXP5_JOINT_PATH)
        if jp and jp.IsValid():
            stage.RemovePrim(EXP5_JOINT_PATH)
        joint = UsdPhysics.RevoluteJoint.Define(stage, EXP5_JOINT_PATH)
        joint.CreateBody0Rel().SetTargets([EXP5_PIVOT_PATH])
        joint.CreateBody1Rel().SetTargets([EXP5_BAR_PATH])
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, float(pivot_distance_x)))
        joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateAxisAttr().Set("Y")

    @staticmethod
    def _exp5_make_material(stage):
        mat_prim = stage.GetPrimAtPath(EXP5_MATERIAL_PATH)
        if mat_prim and mat_prim.IsValid():
            return
        mat = UsdShade.Material.Define(stage, EXP5_MATERIAL_PATH)
        UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        api = UsdPhysics.MaterialAPI(mat.GetPrim())
        api.CreateStaticFrictionAttr().Set(0.0)
        api.CreateDynamicFrictionAttr().Set(0.0)
        api.CreateRestitutionAttr().Set(0.0)

    async def _start_exp5_sim(self):
        """Apply current initial angle θ₀ and start the timeline."""
        try:
            if not self.exp5_scene_built:
                await self._setup_exp5_scene()

            tl = omni.timeline.get_timeline_interface()
            tl.stop()
            await asyncio.sleep(0.05)

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            # Rewrite the bar's default pose so PhysX reads the perturbed
            # initial angle on timeline play.
            theta0 = math.radians(float(self.exp5_theta0_deg))
            x = float(self.exp5_x)
            L = float(self.exp5_L)
            t = float(EXP5_BAR_THICKNESS)
            pivot_z = float(EXP5_PIVOT_HEIGHT)

            # Rest CM is at (0, 0, pivot_z − x); rotation around Y by θ₀
            # moves it to (−x·sinθ, 0, pivot_z − x·cosθ).
            cm = (-x * math.sin(theta0), 0.0, pivot_z - x * math.cos(theta0))
            q = Gf.Quatf(math.cos(theta0 / 2.0), 0.0, math.sin(theta0 / 2.0), 0.0)

            bar_prim = stage.GetPrimAtPath(EXP5_BAR_PATH)
            if bar_prim and bar_prim.IsValid():
                xf = UsdGeom.Xformable(bar_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(*cm))
                xf.AddOrientOp().Set(q)
                xf.AddScaleOp().Set(Gf.Vec3f(t, t, L))

            # Update bar mass in case the slider moved
            await self._apply_mass_at(EXP5_BAR_PATH, self.exp5_m)

            # Reset derived state
            self.exp5_theta = theta0
            self.exp5_omega = 0.0
            self.exp5_measured_period = 0.0
            self.exp5_period_samples = []
            self.exp5_pos_zero_crossings = []
            self.exp5_prev_theta_sign = 1 if theta0 >= 0 else -1
            self.exp5_sim_start_time = time.time()
            self.exp5_phase = "running"

            self.simulation_control_enabled = True
            tl.play()
            carb.log_warn(
                f"exp5: started  θ₀={self.exp5_theta0_deg:.2f}°  "
                f"T_theory={self._exp5_T_theory():.4f}s"
            )
        except Exception as exc:
            carb.log_error(f"_start_exp5_sim: {exc}")

    async def _reset_exp5(self):
        """Return the pendulum to its rest pose and stop motion."""
        self.exp5_phase = "idle"
        self.exp5_theta = 0.0
        self.exp5_omega = 0.0
        self.exp5_measured_period = 0.0
        self.exp5_period_samples = []
        self.exp5_pos_zero_crossings = []
        self.exp5_prev_theta_sign = 1
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            bar_prim = stage.GetPrimAtPath(EXP5_BAR_PATH)
            if bar_prim and bar_prim.IsValid():
                xf = UsdGeom.Xformable(bar_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(
                    Gf.Vec3d(0.0, 0.0, EXP5_PIVOT_HEIGHT - self.exp5_x)
                )
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(
                    Gf.Vec3f(EXP5_BAR_THICKNESS, EXP5_BAR_THICKNESS, self.exp5_L)
                )
        except Exception as exc:
            carb.log_error(f"_reset_exp5: {exc}")

    def _exp5_T_theory(self) -> float:
        """Small-amplitude theoretical period T = 2π √((L²/12 + x²) / (g x))."""
        g = 9.81
        L = max(1e-6, float(self.exp5_L))
        x = max(1e-6, float(self.exp5_x))
        I_over_mx = (L * L / 12.0 + x * x) / x
        return float(2.0 * math.pi * math.sqrt(I_over_mx / g))

    def _exp5_x_min_period(self) -> float:
        """Pivot distance giving the minimum period (x = L / √12)."""
        return float(self.exp5_L) / math.sqrt(12.0)

    def _read_exp5_state(self):
        """Return (theta_rad, omega_rad_s) from the bar's live pose.

        theta is the rotation angle about the Y-axis (0 = straight down).
        """
        theta = 0.0
        omega = 0.0
        try:
            stage = omni.usd.get_context().get_stage()
            if stage:
                prim = stage.GetPrimAtPath(EXP5_BAR_PATH)
                if prim and prim.IsValid():
                    mtx = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
                    q = mtx.ExtractRotationQuat()
                    qw = float(q.GetReal())
                    qi = q.GetImaginary()
                    qy = float(qi[1])
                    theta = 2.0 * math.atan2(qy, qw)
            # Angular velocity via dynamic_control
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(EXP5_BAR_PATH)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_angular_velocity(h)
                if v:
                    omega = float(v[1])
        except Exception:
            pass
        return theta, omega

    def _exp5_update_period_measurement(self, theta: float, sim_time: float):
        """Zero-crossing period estimator (same logic as exp2)."""
        curr_sign = 1 if theta >= 0 else -1
        if curr_sign > 0 and self.exp5_prev_theta_sign <= 0:
            self.exp5_pos_zero_crossings.append(sim_time)
            if len(self.exp5_pos_zero_crossings) >= 2:
                latest_p = (self.exp5_pos_zero_crossings[-1]
                            - self.exp5_pos_zero_crossings[-2])
                if 0.1 < latest_p < 10.0:
                    self.exp5_period_samples.append(latest_p)
                    if len(self.exp5_period_samples) > 5:
                        self.exp5_period_samples.pop(0)
                    self.exp5_measured_period = (
                        sum(self.exp5_period_samples)
                        / len(self.exp5_period_samples)
                    )
        self.exp5_prev_theta_sign = curr_sign

    # --- Exp5 camera -------------------------------------------------------

    # Viewed from the "back" of the stand (-Y side). The support bracket is
    # offset to +Y, so from -Y the swinging bar (at y≈0) sits in front and
    # the stand sits behind it, out of the way. Slight +X offset + elevated
    # eye gives a three-quarter angle that reads as a proper pendulum view.
    _EXP5_CAM_EYE = Gf.Vec3d(0.35, -1.25, 0.70)
    _EXP5_CAM_TGT = Gf.Vec3d(0.0, 0.0, 0.50)
    _EXP5_CAM_FL = 20.0

    def _force_exp5_camera(self, stage=None):
        """Position the viewport camera to watch the pendulum swing in XZ."""
        eye = self._EXP5_CAM_EYE
        tgt = self._EXP5_CAM_TGT
        fl = self._EXP5_CAM_FL
        try:
            self._try_set_camera_view(eye, tgt)
            if stage is None:
                stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(cam_path)
            if not cam_prim or not cam_prim.IsValid():
                cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
            if cam_prim and cam_prim.IsValid():
                mtx = self._build_lookat_matrix(eye, tgt)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(fl)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            self.camera_controller.set_from_eye_target(eye, tgt)
            carb.log_warn(f"exp5 camera: eye={eye} tgt={tgt} fl={fl}")
        except Exception as exc:
            carb.log_error(f"_force_exp5_camera: {exc}")

    async def _deferred_exp5_camera(self):
        """Re-apply exp5 camera after stage init settles."""
        for delay in (1.0, 2.0, 4.0):
            await asyncio.sleep(delay)
            if self.current_experiment != "5":
                return
            self._force_exp5_camera()

    # --- Experiment 4 — driven damped torsional oscillator (PhysX drive) ----
    #
    # Physical model (solved by PhysX, not by closed-form formulas):
    #     I·θ̈ + b·θ̇ + κ·θ = κ·A_drive·sin(ω_d·t)
    #
    # Implementation:
    #     • Dynamic disk rotates about Z via a RevoluteJoint to a kinematic
    #       pivot cube. MassAPI overrides the inertia tensor so the body
    #       behaves as a true aluminium disk (I_z = ½MR²).
    #     • UsdPhysics.DriveAPI (angular, type="force") on the joint gives
    #       stiffness = κ, damping = b → PhysX applies -κθ -bθ̇ every sub-step.
    #     • A lightweight async task updates targetPosition =
    #       A_drive·sin(ω_d·t); PhysX then also applies +κ·target, which is
    #       exactly the sinusoidal driving torque τ₀·sin(ωt) with τ₀ = κ·A.
    #     • A visual driver arm rotates synchronously for feedback.
    #
    # Unit conversion: USD revolute-joint DriveAPI uses DEGREES for position
    # and deg/s for velocity, so stiffness/damping must be scaled by π/180
    # (stiffness_usd = κ_SI · π/180 in N·m/deg, etc.).

    _EXP4_DEG_PER_RAD = 180.0 / math.pi
    _EXP4_RAD_PER_DEG = math.pi / 180.0

    async def _setup_exp4_scene(self):
        """Build the driven-damped torsional oscillator scene procedurally."""
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp4: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")
            UsdGeom.Xform.Define(stage, "/World/exp4")

            # Physics scene — gravity is irrelevant because the disk rotates
            # about its own Z axis and the joint constrains all translations.
            # Keep a small g to match the rest of the platform (prevents NaN
            # if a user switches scenes mid-play).
            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(9.81)

            UsdLux.DomeLight.Define(stage, "/World/exp4/DomeLight").CreateIntensityAttr(1200.0)

            # Ground + grid (visual only — no collision)
            self._exp4_make_visual(
                stage, "/World/exp4/ground",
                pos=(0, 0, EXP4_GROUND_Z),
                scale=(6.0, 6.0, 0.02),
                color=(0.12, 0.12, 0.14),
            )
            for i, xv in enumerate(np.arange(-2.0, 2.01, 0.5)):
                self._exp4_make_visual(
                    stage, f"/World/exp4/GridX_{i}",
                    pos=(float(xv), 0, EXP4_GROUND_Z + 0.011),
                    scale=(0.008, 4.0, 0.002),
                    color=(0.78, 0.78, 0.80),
                )
            for i, yv in enumerate(np.arange(-2.0, 2.01, 0.5)):
                self._exp4_make_visual(
                    stage, f"/World/exp4/GridY_{i}",
                    pos=(0, float(yv), EXP4_GROUND_Z + 0.011),
                    scale=(4.0, 0.008, 0.002),
                    color=(0.78, 0.78, 0.80),
                )

            # Support stand + mounting column (visual only)
            self._exp4_make_visual(
                stage, "/World/exp4/base_plate",
                pos=(0, 0.25, EXP4_GROUND_Z + 0.015),
                scale=(0.35, 0.20, 0.025),
                color=(0.22, 0.22, 0.25),
            )
            column_top = EXP4_PIVOT_HEIGHT - 0.01
            column_z = (EXP4_GROUND_Z + column_top) / 2.0
            column_h = max(0.01, column_top - EXP4_GROUND_Z)
            self._exp4_make_visual(
                stage, "/World/exp4/stand_column",
                pos=(0, 0.22, column_z),
                scale=(0.05, 0.05, column_h),
                color=(0.30, 0.30, 0.35),
            )
            # Horizontal arm reaching from the column to the pivot at (0,0,H)
            self._exp4_make_visual(
                stage, "/World/exp4/stand_arm",
                pos=(0, 0.11, EXP4_PIVOT_HEIGHT),
                scale=(0.04, 0.22, 0.04),
                color=(0.30, 0.30, 0.35),
            )

            # Kinematic pivot (body0 of the revolute joint)
            self._exp4_make_pivot(
                stage, EXP4_PIVOT_PATH,
                pos=(0, 0, EXP4_PIVOT_HEIGHT),
                scale=(0.03, 0.03, 0.03),
                color=(0.95, 0.75, 0.10),
            )

            # Dynamic aluminium disk (body1) — rotates freely about Z.
            #   visual: flat square plate (scale = 2R × 2R × thickness)
            #   physics: explicit diagonal inertia I_z = ½MR² (thin disk)
            R = EXP4_DISK_RADIUS
            self._exp4_make_disk(
                stage, EXP4_DISK_PATH,
                pos=(0, 0, EXP4_PIVOT_HEIGHT),
                scale=(2.0 * R, 2.0 * R, EXP4_DISK_THICKNESS),
                mass=self.exp4_disk_mass,
                radius=R,
                color=(0.72, 0.74, 0.80),
            )

            # Visual "driver arm" — a thin rod above the disk that rotates
            # synchronously with target_position, giving the user a visible
            # reference to see phase lag at a glance.
            driver_arm = UsdGeom.Xform.Define(stage, EXP4_DRIVER_ARM_PATH)
            xf = UsdGeom.Xformable(driver_arm.GetPrim())
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(
                Gf.Vec3d(0.0, 0.0, EXP4_PIVOT_HEIGHT + 0.015)
            )
            self._exp4_drive_arm_op = xf.AddRotateZOp()
            self._exp4_drive_arm_op.Set(0.0)
            # Arm body (thin horizontal bar)
            self._exp4_make_visual(
                stage, EXP4_DRIVER_ARM_PATH + "/bar",
                pos=(0.0, 0.0, 0.008),
                scale=(2.2 * R, 0.010, 0.006),
                color=(0.95, 0.30, 0.10),
            )
            # Arm end markers
            self._exp4_make_visual(
                stage, EXP4_DRIVER_ARM_PATH + "/end_right",
                pos=(1.05 * R, 0.0, 0.008),
                scale=(0.018, 0.018, 0.018),
                color=(1.00, 0.55, 0.10),
            )
            self._exp4_make_visual(
                stage, EXP4_DRIVER_ARM_PATH + "/end_left",
                pos=(-1.05 * R, 0.0, 0.008),
                scale=(0.018, 0.018, 0.018),
                color=(1.00, 0.55, 0.10),
            )

            # Two decorative springs running from the disk rim outward — they
            # model the visible two-spring setup from the PASCO lab but do
            # not participate in physics (the PhysX drive reproduces their
            # combined torque exactly).
            self._exp4_make_visual(
                stage, "/World/exp4/spring_right",
                pos=(R + 0.10, 0.0, EXP4_PIVOT_HEIGHT),
                scale=(0.18, 0.012, 0.012),
                color=(0.55, 0.55, 0.60),
            )
            self._exp4_make_visual(
                stage, "/World/exp4/spring_left",
                pos=(-R - 0.10, 0.0, EXP4_PIVOT_HEIGHT),
                scale=(0.18, 0.012, 0.012),
                color=(0.55, 0.55, 0.60),
            )
            # Magnetic damper block (decorative, sits near disk rim)
            self._exp4_make_visual(
                stage, "/World/exp4/magnet",
                pos=(0.0, -R - 0.035, EXP4_PIVOT_HEIGHT),
                scale=(0.03, 0.04, 0.04),
                color=(0.15, 0.15, 0.18),
            )

            # Revolute joint (Z axis) + angular DriveAPI
            self._exp4_make_joint(stage)
            self._exp4_make_material(stage)
            mat = stage.GetPrimAtPath(EXP4_MATERIAL_PATH)
            disk_prim = stage.GetPrimAtPath(EXP4_DISK_PATH)
            if mat and mat.IsValid() and disk_prim and disk_prim.IsValid():
                if not disk_prim.HasAPI(UsdShade.MaterialBindingAPI):
                    UsdShade.MaterialBindingAPI.Apply(disk_prim)
                UsdShade.MaterialBindingAPI(disk_prim).Bind(UsdShade.Material(mat))

            self._apply_exp4_drive_params()

            self.exp4_scene_built = True
            self.exp4_phase = "idle"
            self.exp4_theta = 0.0
            self.exp4_omega = 0.0
            self.exp4_theta_drive = 0.0
            self.exp4_peak_amp = 0.0

            for _ in range(8):
                await app.next_update_async()

            self._force_exp4_camera(stage)
            carb.log_warn(
                f"exp4: scene built  κ={self.exp4_spring_k:.5f} N·m/rad  "
                f"γ=b/I={self.exp4_damping_gamma:.3f}/s  "
                f"A={self.exp4_drive_amp:.3f} rad  f={self.exp4_frequency:.3f} Hz  "
                f"ω₀={math.sqrt(self.exp4_spring_k / self._exp4_I()):.3f} rad/s"
            )
        except Exception as exc:
            carb.log_error(f"_setup_exp4_scene: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    @staticmethod
    def _exp4_make_visual(stage, path, pos, scale, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])

    @staticmethod
    def _exp4_make_pivot(stage, path, pos, scale, color):
        """Kinematic static cube acting as body0 of the revolute joint."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        rb = UsdPhysics.RigidBodyAPI.Apply(cube.GetPrim())
        rb.CreateKinematicEnabledAttr(True)

    @staticmethod
    def _exp4_make_disk(stage, path, pos, scale, mass, radius, color):
        """Dynamic thin-disk rigid body with explicit disk inertia tensor.

        A cuboid of side (2R,2R,t) with uniform density has I_zz =
        (1/6)·M·(2R)² = (2/3)·M·R² — nearly 33 % too large for the real
        disk result I_zz = ½·M·R². We override the inertia tensor via
        MassAPI.CreateDiagonalInertiaAttr so PhysX treats the body exactly
        like a thin disk:

            I_axial     = ½ M R²          (about spin axis, Z)
            I_transverse = ¼ M R² + 1/12 M t²  (about X, Y)
        """
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
        prim = cube.GetPrim()

        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim)
        mass_api = UsdPhysics.MassAPI(prim)
        mass_api.CreateMassAttr().Set(float(mass))

        I_axial = 0.5 * float(mass) * float(radius) ** 2
        t = float(scale[2])
        I_trans = 0.25 * float(mass) * float(radius) ** 2 + (1.0 / 12.0) * float(mass) * t * t
        mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(I_trans, I_trans, I_axial))
        mass_api.CreatePrincipalAxesAttr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))

        rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rb.CreateSolverPositionIterationCountAttr(EXP4_SOLVER_POS_ITERS)
        rb.CreateSolverVelocityIterationCountAttr(EXP4_SOLVER_VEL_ITERS)
        # PhysX built-in damping OFF — all damping comes from the joint drive
        rb.CreateLinearDampingAttr(0.0)
        rb.CreateAngularDampingAttr(0.0)
        rb.CreateSleepThresholdAttr(0.0)
        # Lock translation + non-spin rotations so the disk is effectively
        # a pure 1-DOF body. (The revolute joint already does this, but the
        # locks guarantee numerical stability if PhysX drifts at high ω.)
        rb.CreateLockedPosAxisAttr().Set(7)       # bitmask: 1|2|4 = X|Y|Z
        rb.CreateLockedRotAxisAttr().Set(3)       # lock X & Y rotation

    @staticmethod
    def _exp4_make_joint(stage):
        """Revolute joint around +Z so the disk spins in the XY plane."""
        jp = stage.GetPrimAtPath(EXP4_JOINT_PATH)
        if jp and jp.IsValid():
            stage.RemovePrim(EXP4_JOINT_PATH)
        joint = UsdPhysics.RevoluteJoint.Define(stage, EXP4_JOINT_PATH)
        joint.CreateBody0Rel().SetTargets([EXP4_PIVOT_PATH])
        joint.CreateBody1Rel().SetTargets([EXP4_DISK_PATH])
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
        joint.CreateAxisAttr().Set("Z")
        # Generous rotation range (disk never hits stops in practice).
        joint.CreateLowerLimitAttr().Set(-1e9)
        joint.CreateUpperLimitAttr().Set(1e9)

        # Angular drive: stiffness = κ (spring), damping = b (magnet brake)
        UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
        drive = UsdPhysics.DriveAPI(joint.GetPrim(), "angular")
        drive.CreateTypeAttr().Set("force")
        drive.CreateTargetPositionAttr().Set(0.0)     # degrees
        drive.CreateTargetVelocityAttr().Set(0.0)
        drive.CreateMaxForceAttr().Set(1.0e9)
        drive.CreateStiffnessAttr().Set(0.0)
        drive.CreateDampingAttr().Set(0.0)

    @staticmethod
    def _exp4_make_material(stage):
        mat_prim = stage.GetPrimAtPath(EXP4_MATERIAL_PATH)
        if mat_prim and mat_prim.IsValid():
            return
        mat = UsdShade.Material.Define(stage, EXP4_MATERIAL_PATH)
        UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        api = UsdPhysics.MaterialAPI(mat.GetPrim())
        api.CreateStaticFrictionAttr().Set(0.0)
        api.CreateDynamicFrictionAttr().Set(0.0)
        api.CreateRestitutionAttr().Set(0.0)

    def _exp4_I(self) -> float:
        """Disk spin-axis moment of inertia I_zz = ½ M R²."""
        return 0.5 * float(self.exp4_disk_mass) * float(self.exp4_disk_radius) ** 2

    def _apply_exp4_drive_params(self) -> None:
        """Push current κ, b onto the revolute-joint angular drive.

        USD DriveAPI on a revolute joint works in **degrees**, so both
        stiffness and damping must be scaled by (π/180) to match the SI
        equation of motion.
        """
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            joint_prim = stage.GetPrimAtPath(EXP4_JOINT_PATH)
            if not (joint_prim and joint_prim.IsValid()):
                return
            drive = UsdPhysics.DriveAPI(joint_prim, "angular")
            I = self._exp4_I()
            b_SI = float(self.exp4_damping_gamma) * I
            stiffness_usd = float(self.exp4_spring_k) * self._EXP4_RAD_PER_DEG
            damping_usd = b_SI * self._EXP4_RAD_PER_DEG
            drive.GetStiffnessAttr().Set(stiffness_usd)
            drive.GetDampingAttr().Set(damping_usd)
            # Cache handle so the driver task doesn't pay the prim lookup cost
            self._exp4_drive_target_attr = drive.GetTargetPositionAttr()
        except Exception as exc:
            carb.log_error(f"_apply_exp4_drive_params: {exc}")

    async def _start_exp4_sim(self):
        """Apply current params, reset pose, and start the sinusoidal driver."""
        try:
            if not self.exp4_scene_built:
                await self._setup_exp4_scene()

            tl = omni.timeline.get_timeline_interface()
            tl.stop()
            await asyncio.sleep(0.05)

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            # Reset the disk to θ=0, ω=0 by rewriting its xform.
            disk_prim = stage.GetPrimAtPath(EXP4_DISK_PATH)
            if disk_prim and disk_prim.IsValid():
                xf = UsdGeom.Xformable(disk_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, EXP4_PIVOT_HEIGHT))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(
                    2.0 * EXP4_DISK_RADIUS,
                    2.0 * EXP4_DISK_RADIUS,
                    EXP4_DISK_THICKNESS,
                ))

            self._apply_exp4_drive_params()
            # Mass may have changed since last build
            await self._apply_mass_at(EXP4_DISK_PATH, self.exp4_disk_mass)

            # Cancel any previous driver task
            if self.exp4_drive_task and not self.exp4_drive_task.done():
                self.exp4_drive_task.cancel()

            self.exp4_theta = 0.0
            self.exp4_omega = 0.0
            self.exp4_theta_drive = 0.0
            self.exp4_peak_amp = 0.0
            self.exp4_sim_start_time = time.time()
            self.exp4_phase = "running"
            self.simulation_control_enabled = True

            tl.play()
            self.exp4_drive_task = asyncio.ensure_future(self._run_exp4_drive_loop())

            carb.log_warn(
                f"exp4: started   f={self.exp4_frequency:.3f} Hz  "
                f"A={self.exp4_drive_amp:.3f} rad  γ={self.exp4_damping_gamma:.3f}/s  "
                f"κ={self.exp4_spring_k:.5f}  Q={self._exp4_Q():.2f}"
            )
        except Exception as exc:
            carb.log_error(f"_start_exp4_sim: {exc}")

    async def _start_exp4_free_oscillation(self):
        """Free-oscillation test (PDF procedure #1 & #5).

        Sets drive amplitude → 0 so the driver supplies no torque, then
        perturbs the disk by a small initial angular velocity. The disk
        rings down at ω_d = √(ω₀² − γ²/4), whose period is the undamped
        natural period to <1 % for small γ.
        """
        try:
            if not self.exp4_scene_built:
                await self._setup_exp4_scene()

            tl = omni.timeline.get_timeline_interface()
            tl.stop()
            await asyncio.sleep(0.05)

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            disk_prim = stage.GetPrimAtPath(EXP4_DISK_PATH)
            if disk_prim and disk_prim.IsValid():
                xf = UsdGeom.Xformable(disk_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, EXP4_PIVOT_HEIGHT))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(
                    2.0 * EXP4_DISK_RADIUS,
                    2.0 * EXP4_DISK_RADIUS,
                    EXP4_DISK_THICKNESS,
                ))

            # Drive OFF but spring + damping ON
            self._apply_exp4_drive_params()
            if self._exp4_drive_target_attr is not None:
                self._exp4_drive_target_attr.Set(0.0)

            if self.exp4_drive_task and not self.exp4_drive_task.done():
                self.exp4_drive_task.cancel()

            self.exp4_theta = 0.0
            self.exp4_omega = 0.0
            self.exp4_theta_drive = 0.0
            self.exp4_peak_amp = 0.0
            self.exp4_sim_start_time = time.time()
            self.exp4_phase = "free"
            self.simulation_control_enabled = True

            tl.play()
            # Let timeline pick up the pose, then kick the disk.
            await asyncio.sleep(0.05)
            try:
                from omni.isaac.dynamic_control import _dynamic_control
                if self._dc_interface is None:
                    self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
                h = self._dc_interface.get_rigid_body(EXP4_DISK_PATH)
                if h != _dynamic_control.INVALID_HANDLE:
                    # Kick that yields ≈ 0.5 rad amplitude at ω₀
                    omega_kick = math.sqrt(max(1e-6, self.exp4_spring_k / self._exp4_I())) * 0.5
                    self._dc_interface.set_rigid_body_angular_velocity(
                        h, (0.0, 0.0, float(omega_kick))
                    )
            except Exception as exc:
                carb.log_error(f"exp4 free-osc kick: {exc}")

            carb.log_warn(
                f"exp4: FREE oscillation   ω₀={math.sqrt(self.exp4_spring_k / self._exp4_I()):.3f} rad/s"
            )
        except Exception as exc:
            carb.log_error(f"_start_exp4_free_oscillation: {exc}")

    async def _reset_exp4(self):
        """Stop driver, return disk to rest."""
        self.exp4_phase = "idle"
        if self.exp4_drive_task and not self.exp4_drive_task.done():
            self.exp4_drive_task.cancel()
            self.exp4_drive_task = None
        self.exp4_theta = 0.0
        self.exp4_omega = 0.0
        self.exp4_theta_drive = 0.0
        self.exp4_peak_amp = 0.0
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            if self._exp4_drive_target_attr is not None:
                self._exp4_drive_target_attr.Set(0.0)
            if self._exp4_drive_arm_op is not None:
                self._exp4_drive_arm_op.Set(0.0)
            disk_prim = stage.GetPrimAtPath(EXP4_DISK_PATH)
            if disk_prim and disk_prim.IsValid():
                xf = UsdGeom.Xformable(disk_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, EXP4_PIVOT_HEIGHT))
                xf.AddOrientOp().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                xf.AddScaleOp().Set(Gf.Vec3f(
                    2.0 * EXP4_DISK_RADIUS,
                    2.0 * EXP4_DISK_RADIUS,
                    EXP4_DISK_THICKNESS,
                ))
        except Exception as exc:
            carb.log_error(f"_reset_exp4: {exc}")

    async def _run_exp4_drive_loop(self):
        """Update the joint drive's target_position to A·sin(ω_d·t).

        This is the *only* per-tick work the server has to do — PhysX
        takes care of integrating κ, b, and the driving torque at its
        internal sub-step rate (typically 240 Hz).
        """
        dt = 1.0 / max(30.0, EXP4_DRIVER_UPDATE_HZ)
        try:
            while self.exp4_phase == "running":
                if not self.ws_clients:
                    # Still drive — user may open the UI later — but sleep
                    # longer to conserve CPU.
                    await asyncio.sleep(dt)
                    continue
                sim_time = time.time() - self.exp4_sim_start_time
                omega_d = 2.0 * math.pi * float(self.exp4_frequency)
                A_rad = float(self.exp4_drive_amp)
                theta_drive_rad = A_rad * math.sin(omega_d * sim_time)
                self.exp4_theta_drive = theta_drive_rad
                target_deg = theta_drive_rad * self._EXP4_DEG_PER_RAD
                if self._exp4_drive_target_attr is not None:
                    try:
                        self._exp4_drive_target_attr.Set(float(target_deg))
                    except Exception:
                        pass
                if self._exp4_drive_arm_op is not None:
                    try:
                        self._exp4_drive_arm_op.Set(float(target_deg))
                    except Exception:
                        pass
                await asyncio.sleep(dt)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            carb.log_error(f"_run_exp4_drive_loop: {exc}")

    def _read_exp4_state(self) -> tuple:
        """Return (theta_rad, omega_rad_s) of the disk (about Z).

        Theta is pulled from the USD pose quaternion and unwrapped modulo
        2π; omega comes from the dynamic_control angular-velocity readback.
        """
        theta = 0.0
        omega = 0.0
        try:
            stage = omni.usd.get_context().get_stage()
            if stage:
                prim = stage.GetPrimAtPath(EXP4_DISK_PATH)
                if prim and prim.IsValid():
                    mtx = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
                    q = mtx.ExtractRotationQuat()
                    qw = float(q.GetReal())
                    qi = q.GetImaginary()
                    qz = float(qi[2])
                    theta = 2.0 * math.atan2(qz, qw)
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(EXP4_DISK_PATH)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_angular_velocity(h)
                if v:
                    omega = float(v[2])
        except Exception:
            pass
        return theta, omega

    def _exp4_update_peak(self, theta: float) -> None:
        """Exponentially-decaying peak-hold on |θ| (rad)."""
        abs_theta = abs(float(theta))
        if abs_theta > self.exp4_peak_amp:
            self.exp4_peak_amp = abs_theta
        else:
            # Slow decay so the peak tracks amplitude changes when the
            # drive frequency is swept.
            self.exp4_peak_amp *= float(self.exp4_peak_decay)

    # --- Analytical derived quantities (shown on UI, not used by PhysX) -----

    def _exp4_natural_freq_hz(self) -> float:
        """f₀ = (1/2π)·√(κ/I)."""
        I = self._exp4_I()
        return float(math.sqrt(max(0.0, self.exp4_spring_k) / max(1e-12, I)) / (2.0 * math.pi))

    def _exp4_Q(self) -> float:
        """Quality factor Q = √(κI) / b = ω₀/(2γ)."""
        I = self._exp4_I()
        b = float(self.exp4_damping_gamma) * I
        num = math.sqrt(max(0.0, self.exp4_spring_k) * max(0.0, I))
        if b < 1e-12:
            return float("inf")
        return float(num / b)

    def _exp4_theory_amplitude(self) -> float:
        """Steady-state amplitude θ₀(ω) from closed-form (for reference).

            θ₀ = (κ·A / I) / √((ω²−ω₀²)² + (bω/I)²)
        """
        I = self._exp4_I()
        if I <= 0.0:
            return 0.0
        w = 2.0 * math.pi * float(self.exp4_frequency)
        w0_sq = float(self.exp4_spring_k) / I
        b_over_I = float(self.exp4_damping_gamma)
        num = (float(self.exp4_spring_k) / I) * float(self.exp4_drive_amp)
        denom = math.sqrt((w * w - w0_sq) ** 2 + (b_over_I * w) ** 2)
        if denom < 1e-12:
            return 0.0
        return float(num / denom)

    def _exp4_theory_phase_deg(self) -> float:
        """Phase lag of disk w.r.t. driver, φ = atan2(ω·γ, ω₀²−ω²)   [deg]."""
        I = self._exp4_I()
        if I <= 0.0:
            return 0.0
        w = 2.0 * math.pi * float(self.exp4_frequency)
        w0_sq = float(self.exp4_spring_k) / I
        return float(math.degrees(math.atan2(float(self.exp4_damping_gamma) * w, w0_sq - w * w)))

    # --- Exp4 camera --------------------------------------------------------

    # A slight elevation + a rotation offset so both the disk face and the
    # overhead driver arm are visible in the same shot.
    _EXP4_CAM_EYE = Gf.Vec3d(0.45, -0.55, 0.78)
    _EXP4_CAM_TGT = Gf.Vec3d(0.0, 0.0, EXP4_PIVOT_HEIGHT)
    _EXP4_CAM_FL = 22.0

    def _force_exp4_camera(self, stage=None):
        eye = self._EXP4_CAM_EYE
        tgt = self._EXP4_CAM_TGT
        fl = self._EXP4_CAM_FL
        try:
            self._try_set_camera_view(eye, tgt)
            if stage is None:
                stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(cam_path)
            if not cam_prim or not cam_prim.IsValid():
                cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
            if cam_prim and cam_prim.IsValid():
                mtx = self._build_lookat_matrix(eye, tgt)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(fl)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            self.camera_controller.set_from_eye_target(eye, tgt)
            carb.log_warn(f"exp4 camera: eye={eye} tgt={tgt} fl={fl}")
        except Exception as exc:
            carb.log_error(f"_force_exp4_camera: {exc}")

    async def _deferred_exp4_camera(self):
        for delay in (1.0, 2.0, 4.0):
            await asyncio.sleep(delay)
            if self.current_experiment != "4":
                return
            self._force_exp4_camera()

    def _store_param(self, exp_id: str, key: str, data: dict):
        """Store a generic parameter for experiments that don't need immediate USD apply."""
        self._exp_params.setdefault(exp_id, {})[key] = float(data.get("value", 0))

    async def _apply_mass_at(self, prim_path: str, mass: float):
        """Apply MassAPI to any prim — shared helper for exp3-8."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            prim = stage.GetPrimAtPath(prim_path)
            if prim and prim.IsValid():
                if not prim.HasAPI(UsdPhysics.MassAPI):
                    UsdPhysics.MassAPI.Apply(prim)
                UsdPhysics.MassAPI(prim).GetMassAttr().Set(float(mass))
        except Exception as exc:
            carb.log_error(f"apply_mass_at({prim_path}): {exc}")

    @staticmethod
    def _build_lookat_matrix(eye: Gf.Vec3d, target: Gf.Vec3d, up: Gf.Vec3d = Gf.Vec3d(0, 0, 1)) -> Gf.Matrix4d:
        backward = (eye - target).GetNormalized()
        right = (up ^ backward).GetNormalized()
        cam_up = (backward ^ right).GetNormalized()
        m = Gf.Matrix4d(1)
        m[0, 0], m[0, 1], m[0, 2] = right[0], right[1], right[2]
        m[1, 0], m[1, 1], m[1, 2] = cam_up[0], cam_up[1], cam_up[2]
        m[2, 0], m[2, 1], m[2, 2] = backward[0], backward[1], backward[2]
        m[3, 0], m[3, 1], m[3, 2] = eye[0], eye[1], eye[2]
        return m

    def _find_exp1_center(self) -> Gf.Vec3d:
        """Robustly locate the experiment-1 apparatus center by traversing
        stage prims. Falls back to the origin."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return Gf.Vec3d(0, 0, 0)
            for path in [EXP1_DISK_PATH, EXP1_RING_PATH,
                         "/World/exp1", "/World/exp1/bracket1"]:
                p = stage.GetPrimAtPath(path)
                if p and p.IsValid():
                    try:
                        xf = UsdGeom.Xformable(p)
                        t = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                        pos = Gf.Vec3d(t[0], t[1], t[2])
                        carb.log_warn(f"Exp1 center from {path}: {pos}")
                        return pos
                    except Exception:
                        pass
            for prim in stage.Traverse():
                name = str(prim.GetPath())
                if "exp1" in name.lower() and prim.IsA(UsdGeom.Xformable):
                    try:
                        xf = UsdGeom.Xformable(prim)
                        t = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                        pos = Gf.Vec3d(t[0], t[1], t[2])
                        carb.log_warn(f"Exp1 center from traverse {name}: {pos}")
                        return pos
                    except Exception:
                        pass
        except Exception as exc:
            carb.log_error(f"_find_exp1_center: {exc}")
        carb.log_warn("Exp1 center: fallback to origin (0,0,0)")
        return Gf.Vec3d(0, 0, 0)

    @staticmethod
    def _try_set_camera_view(eye: Gf.Vec3d, target: Gf.Vec3d) -> bool:
        """Try Isaac Sim's official Viewport API to position the camera."""
        eye_list = [float(eye[0]), float(eye[1]), float(eye[2])]
        tgt_list = [float(target[0]), float(target[1]), float(target[2])]
        for mod_path in [
            "omni.isaac.core.utils.viewports",
            "isaacsim.core.utils.viewports",
        ]:
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                mod.set_camera_view(eye=eye_list, target=tgt_list)
                carb.log_warn(f"Camera set via {mod_path}")
                return True
            except (ImportError, AttributeError, Exception):
                continue
        return False

    async def _switch_camera(self, experiment_id: str):
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            if experiment_id == "1":
                center = self._find_exp1_center()
                # 45-degree isometric overhead: look DOWN at the turntable
                dist = 0.8
                target = Gf.Vec3d(center[0], center[1], center[2] + 0.03)
                eye = Gf.Vec3d(
                    center[0] + dist * 0.70,
                    center[1] - dist * 0.70,
                    center[2] + dist,
                )
                focal = 18.0
            else:
                presets = {
                    "2": (WebRTCServer._EXP2_CAM_EYE, WebRTCServer._EXP2_CAM_TGT, WebRTCServer._EXP2_CAM_FL),
                    "3": (WebRTCServer._EXP3_CAM_EYE, WebRTCServer._EXP3_CAM_TGT, WebRTCServer._EXP3_CAM_FL),
                    "4": (WebRTCServer._EXP4_CAM_EYE, WebRTCServer._EXP4_CAM_TGT, WebRTCServer._EXP4_CAM_FL),
                    "5": (WebRTCServer._EXP5_CAM_EYE, WebRTCServer._EXP5_CAM_TGT, WebRTCServer._EXP5_CAM_FL),
                    "7": (Gf.Vec3d(0.0, -1.6, 0.6), Gf.Vec3d(0, 0, 0.0), 24.0),
                    "8": (WebRTCServer._EXP8_CAM_EYE, WebRTCServer._EXP8_CAM_TGT, WebRTCServer._EXP8_CAM_FL),
                }
                if experiment_id in presets:
                    eye, target, focal = presets[experiment_id]
                else:
                    return

            # Strategy 1: official Isaac Sim Viewport API (most reliable)
            camera_set = self._try_set_camera_view(eye, target)

            # Strategy 2: direct USD xform fallback
            if not camera_set:
                viewport = vp_util.get_active_viewport()
                camera_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
                cam_prim = stage.GetPrimAtPath(camera_path)
                if cam_prim and cam_prim.IsValid():
                    mtx = self._build_lookat_matrix(eye, target)
                    xform = UsdGeom.Xformable(cam_prim)
                    xform.ClearXformOpOrder()
                    xform.AddTransformOp().Set(mtx)
                    carb.log_warn("Camera set via USD xform fallback")

            # Camera properties (focal length, clipping)
            viewport = vp_util.get_active_viewport()
            camera_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(camera_path)
            if cam_prim and cam_prim.IsValid():
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(focal)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))

            self.camera_controller.set_from_eye_target(eye, target)
            carb.log_warn(f"Camera final: eye={eye} target={target}")
        except Exception as exc:
            carb.log_error(f"Camera switch failed: {exc}")

    async def _deferred_camera_readjust(self):
        """Re-adjust camera after 2s when the stage has fully settled."""
        await asyncio.sleep(2.0)
        try:
            center = self._find_exp1_center()
            carb.log_warn(f"Deferred camera readjust: center={center}")
            dist = 0.8
            target = Gf.Vec3d(center[0], center[1], center[2] + 0.03)
            eye = Gf.Vec3d(
                center[0] + dist * 0.70,
                center[1] - dist * 0.70,
                center[2] + dist,
            )
            if not self._try_set_camera_view(eye, target):
                stage = omni.usd.get_context().get_stage()
                if not stage:
                    return
                viewport = vp_util.get_active_viewport()
                cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
                cam_prim = stage.GetPrimAtPath(cam_path)
                if not cam_prim or not cam_prim.IsValid():
                    return
                mtx = self._build_lookat_matrix(eye, target)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
            self.camera_controller.set_from_eye_target(eye, target)
        except Exception as exc:
            carb.log_error(f"Deferred camera: {exc}")

    _EXP2_CAM_EYE = Gf.Vec3d(1.5, 3.5, 2.0)
    _EXP2_CAM_TGT = Gf.Vec3d(0, 0, 0.30)
    _EXP2_CAM_FL = 15.0

    def _force_exp2_camera(self, stage=None):
        """Set exp2 camera using every available method."""
        eye = self._EXP2_CAM_EYE
        tgt = self._EXP2_CAM_TGT
        fl = self._EXP2_CAM_FL
        try:
            self._try_set_camera_view(eye, tgt)

            if stage is None:
                stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(cam_path)
            if not cam_prim or not cam_prim.IsValid():
                cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
            if cam_prim and cam_prim.IsValid():
                mtx = self._build_lookat_matrix(eye, tgt)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(fl)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            self.camera_controller.set_from_eye_target(eye, tgt)
            carb.log_warn(f"exp2 camera forced: eye={eye} tgt={tgt} fl={fl}")
        except Exception as exc:
            carb.log_error(f"_force_exp2_camera: {exc}")

    async def _deferred_exp2_camera(self):
        """Re-apply exp2 camera at 1s, 2s, and 4s after enter to beat
        Isaac Sim's async stage-init camera resets."""
        for delay in (1.0, 2.0, 4.0):
            await asyncio.sleep(delay)
            if self.current_experiment != "2":
                return
            self._force_exp2_camera()
            carb.log_warn(f"exp2 deferred camera at +{delay}s")

    async def _set_initial_angular_velocity(self):
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            prim = stage.GetPrimAtPath(EXP1_DISK_PATH)
            if prim and prim.IsValid() and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rb = UsdPhysics.RigidBodyAPI(prim)
                SCALE = 10.0
                dps = float(self.exp1_initial_vel) * (180.0 / math.pi) * SCALE
                rb.GetAngularVelocityAttr().Set(Gf.Vec3f(0, 0, dps))
        except Exception as exc:
            carb.log_error(f"Failed to set angular velocity: {exc}")

    async def _apply_exp1_params(self):
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            for path, mass in [(EXP1_DISK_PATH, self.exp1_disk_mass), (EXP1_RING_PATH, self.exp1_ring_mass)]:
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid():
                    if not prim.HasAPI(UsdPhysics.MassAPI):
                        UsdPhysics.MassAPI.Apply(prim)
                    UsdPhysics.MassAPI(prim).GetMassAttr().Set(float(mass))
        except Exception as exc:
            carb.log_error(f"apply_exp1_params: {exc}")

    async def _drop_ring_or_disk(self):
        """Drop the ring/disk onto the spinning lower disk with realistic physics.

        Includes: angular momentum conservation, random eccentric offset
        (parallel-axis theorem), and bearing friction model.
        """
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            R_d = self.exp1_disk_radius
            I_disk = 0.5 * self.exp1_disk_mass * (R_d ** 2)

            # Random eccentric offset simulating human hand error (σ ≈ 2mm)
            offset_x = random.gauss(0, 0.002)
            offset_y = random.gauss(0, 0.002)
            self.exp1_drop_offset = math.sqrt(offset_x**2 + offset_y**2)

            if self.exp1_drop_object == "ring":
                R1 = self.exp1_ring_inner_r
                R2 = self.exp1_ring_outer_r
                I_obj_cm = 0.5 * self.exp1_ring_mass * (R1**2 + R2**2)
            else:
                I_obj_cm = 0.5 * self.exp1_ring_mass * (R_d ** 2)

            # Parallel-axis theorem: I = I_cm + m*x²
            I_obj = I_obj_cm + self.exp1_ring_mass * (self.exp1_drop_offset ** 2)
            I_final = I_disk + I_obj
            self.exp1_I_final_actual = I_final

            dv, _ = self._get_angular_velocities()
            if abs(dv) < 0.01:
                dv = self.exp1_initial_vel

            # Friction loss during collision (bearing drag, 1-3% loss)
            friction_loss = random.uniform(0.01, 0.03)
            omega_f = (I_disk * dv) / I_final * (1.0 - friction_loss)

            self.exp1_omega_after_drop = omega_f
            self.exp1_final_am = I_final * omega_f
            self.exp1_ke_final = 0.5 * I_final * omega_f * omega_f

            SCALE = 10.0
            dps = float(omega_f) * (180.0 / math.pi) * SCALE
            for path in [EXP1_DISK_PATH, EXP1_RING_PATH]:
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid() and prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    rb = UsdPhysics.RigidBodyAPI(prim)
                    rb.GetAngularVelocityAttr().Set(Gf.Vec3f(0, 0, dps))
        except Exception as exc:
            carb.log_error(f"drop_ring_or_disk: {exc}")

    async def _apply_exp2_params(self):
        """No-op kept for backward compat; exp2 is now procedural RK4."""
        pass

    # --- Angular velocity read-back ----------------------------------------

    def _get_angular_velocities(self):
        disk_vel = ring_vel = 0.0
        try:
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            dc = self._dc_interface
            SCALE = 10.0
            dh = dc.get_rigid_body(EXP1_DISK_PATH)
            if dh != _dynamic_control.INVALID_HANDLE:
                v = dc.get_rigid_body_angular_velocity(dh)
                if v:
                    disk_vel = float(v[2]) / SCALE
            rh = dc.get_rigid_body(EXP1_RING_PATH)
            if rh != _dynamic_control.INVALID_HANDLE:
                v = dc.get_rigid_body_angular_velocity(rh)
                if v:
                    ring_vel = float(v[2]) / SCALE
        except Exception:
            pass
        return disk_vel, ring_vel

    def _get_exp2_angle(self):
        """Legacy shim — angle is now computed by RK4, not read from USD."""
        return np.degrees(self.exp2_theta)

    # --- Physics readback helpers for exp3-8 --------------------------------

    def _read_velocity(self, prim_path: str) -> float:
        """Read linear velocity magnitude of a rigid body."""
        try:
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(prim_path)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_linear_velocity(h)
                if v:
                    return round(math.sqrt(v[0]**2 + v[1]**2 + v[2]**2), 2)
        except Exception:
            pass
        return 0.0

    def _read_kinetic_energy(self, prim_path: str, mass: float) -> float:
        vel = self._read_velocity(prim_path)
        return round(0.5 * mass * vel * vel, 2)

    def _read_displacement(self, prim_path: str) -> float:
        """Read Z-position offset from origin (for oscillation experiments)."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return 0.0
            prim = stage.GetPrimAtPath(prim_path)
            if prim and prim.IsValid():
                xf = UsdGeom.Xformable(prim)
                mtx = xf.ComputeLocalToWorldTransform(0)
                return round(float(mtx.ExtractTranslation()[2]), 3)
        except Exception:
            pass
        return 0.0

    def _read_total_momentum(self) -> float:
        """Sum of momenta for two-cart collision (exp7)."""
        v1 = self._read_exp7_vx(EXP7_CART1_PATH)
        v2 = self._read_exp7_vx(EXP7_CART2_PATH)
        return round(self.exp7_mass1 * v1 + self.exp7_mass2 * v2, 4)

    def _read_total_ke(self) -> float:
        v1 = self._read_exp7_vx(EXP7_CART1_PATH)
        v2 = self._read_exp7_vx(EXP7_CART2_PATH)
        return round(0.5 * self.exp7_mass1 * v1 * v1 + 0.5 * self.exp7_mass2 * v2 * v2, 4)

    # --- Experiment 7 — full scene builder & collision logic ----------------

    def _read_exp7_vx(self, prim_path: str) -> float:
        """Read x-component of linear velocity for a rigid body."""
        try:
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            h = self._dc_interface.get_rigid_body(prim_path)
            if h != _dynamic_control.INVALID_HANDLE:
                v = self._dc_interface.get_rigid_body_linear_velocity(h)
                if v:
                    return float(v[0])
        except Exception:
            pass
        return 0.0

    def _read_exp7_px(self, prim_path: str) -> float:
        """Read x-position of a prim."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return 0.0
            prim = stage.GetPrimAtPath(prim_path)
            if prim and prim.IsValid():
                xf = UsdGeom.Xformable(prim)
                mtx = xf.ComputeLocalToWorldTransform(0)
                return float(mtx.ExtractTranslation()[0])
        except Exception:
            pass
        return 0.0

    async def _setup_exp7_scene(self):
        """Build the momentum-conservation scene from scratch (ground + 2 carts)."""
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp7: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")
            UsdGeom.Xform.Define(stage, "/World/exp7")

            # Physics scene — zero gravity: models a leveled frictionless track
            # where the normal force exactly cancels gravity.
            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(0.0)

            # Dome light
            light = UsdLux.DomeLight.Define(stage, "/World/exp7/DomeLight")
            light.CreateIntensityAttr(1500.0)

            # Ground — visual only (no CollisionAPI; carts float with zero-g)
            self._create_exp7_visual(
                stage, EXP7_GROUND_PATH,
                pos=(0, 0, -0.01), scale=(4.0, 1.0, 0.02),
                color=(0.15, 0.15, 0.18),
            )

            # Track visual strip
            self._create_exp7_visual(
                stage, "/World/exp7/track",
                pos=(0, 0, 0.002), scale=(3.0, 0.12, 0.004),
                color=(0.25, 0.25, 0.30),
            )

            # Cart 1 (red)
            self._create_exp7_cart(
                stage, EXP7_CART1_PATH,
                pos=EXP7_CART1_INIT_POS, mass=self.exp7_mass1,
                color=(1.0, 0.15, 0.15),
            )
            # Cart 2 (blue)
            self._create_exp7_cart(
                stage, EXP7_CART2_PATH,
                pos=EXP7_CART2_INIT_POS, mass=self.exp7_mass2,
                color=(0.15, 0.45, 1.0),
            )

            # Physics material (frictionless, configurable restitution)
            self._create_exp7_material(stage, self.exp7_restitution)

            # Bind material to carts only (ground is visual-only)
            mat = stage.GetPrimAtPath(EXP7_MATERIAL_PATH)
            for path in [EXP7_CART1_PATH, EXP7_CART2_PATH]:
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid() and mat and mat.IsValid():
                    if not prim.HasAPI(UsdShade.MaterialBindingAPI):
                        UsdShade.MaterialBindingAPI.Apply(prim)
                    UsdShade.MaterialBindingAPI(prim).Bind(
                        UsdShade.Material(mat),
                    )

            self.exp7_scene_built = True
            self.exp7_phase = "idle"
            self.exp7_collision_detected = False
            carb.log_warn("exp7: scene built successfully")

            for _ in range(5):
                await app.next_update_async()
        except Exception as exc:
            carb.log_error(f"_setup_exp7_scene: {exc}")
            import traceback
            tracb = traceback.format_exc()
            carb.log_error(tracb)

    @staticmethod
    def _create_exp7_visual(stage, path: str, pos: tuple, scale: tuple, color: tuple):
        """Create a purely visual cube — no collision, no rigid body."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])

    def _create_exp7_cart(
        self, stage, path: str, pos: tuple, mass: float, color: tuple,
    ):
        """Create a dynamic cuboid with full PhysX settings for accurate 1D collisions."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*EXP7_CART_SIZE))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])

        prim = cube.GetPrim()

        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.CollisionAPI.Apply(prim)

        UsdPhysics.MassAPI.Apply(prim)
        UsdPhysics.MassAPI(prim).CreateMassAttr().Set(float(mass))

        rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        rb.CreateEnableCCDAttr(True)
        rb.CreateSolverPositionIterationCountAttr(EXP7_SOLVER_POS_ITERS)
        rb.CreateSolverVelocityIterationCountAttr(EXP7_SOLVER_VEL_ITERS)
        rb.CreateLinearDampingAttr(0.0)
        rb.CreateAngularDampingAttr(100.0)
        rb.CreateSleepThresholdAttr(0.0)

        col = PhysxSchema.PhysxCollisionAPI.Apply(prim)
        col.CreateContactOffsetAttr(0.002)
        col.CreateRestOffsetAttr(0.0)

    def _create_exp7_material(self, stage, restitution: float):
        """Create / update the frictionless physics material for exp7."""
        mat_prim = stage.GetPrimAtPath(EXP7_MATERIAL_PATH)
        if mat_prim and mat_prim.IsValid():
            api = UsdPhysics.MaterialAPI(mat_prim)
            api.GetRestitutionAttr().Set(float(restitution))
            return

        mat = UsdShade.Material.Define(stage, EXP7_MATERIAL_PATH)
        UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        api = UsdPhysics.MaterialAPI(mat.GetPrim())
        api.CreateStaticFrictionAttr().Set(0.0)
        api.CreateDynamicFrictionAttr().Set(0.0)
        api.CreateRestitutionAttr().Set(float(restitution))

        PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim())
        phx = PhysxSchema.PhysxMaterialAPI(mat.GetPrim())
        phx.CreateFrictionCombineModeAttr().Set("min")
        phx.CreateRestitutionCombineModeAttr().Set("max")

    async def _update_exp7_restitution(self):
        """Live-update the physics material restitution without rebuilding the scene."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            mat_prim = stage.GetPrimAtPath(EXP7_MATERIAL_PATH)
            if mat_prim and mat_prim.IsValid():
                UsdPhysics.MaterialAPI(mat_prim).GetRestitutionAttr().Set(
                    float(self.exp7_restitution)
                )
        except Exception as exc:
            carb.log_error(f"_update_exp7_restitution: {exc}")

    async def _start_exp7_collision(self):
        """Reset cart positions, warm up, then apply initial velocities."""
        try:
            tl = omni.timeline.get_timeline_interface()
            tl.stop()
            await asyncio.sleep(0.05)

            stage = omni.usd.get_context().get_stage()
            if not stage:
                return

            if not self.exp7_scene_built:
                await self._setup_exp7_scene()
                stage = omni.usd.get_context().get_stage()

            # Reset positions
            for path, pos in [(EXP7_CART1_PATH, EXP7_CART1_INIT_POS),
                               (EXP7_CART2_PATH, EXP7_CART2_INIT_POS)]:
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid():
                    xf = UsdGeom.Xformable(prim)
                    xf.ClearXformOpOrder()
                    xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
                    xf.AddScaleOp().Set(Gf.Vec3f(*EXP7_CART_SIZE))

            # Update masses & material
            await self._apply_mass_at(EXP7_CART1_PATH, self.exp7_mass1)
            await self._apply_mass_at(EXP7_CART2_PATH, self.exp7_mass2)
            self._create_exp7_material(stage, self.exp7_restitution)

            self.exp7_pre_v1 = self.exp7_v1
            self.exp7_pre_v2 = self.exp7_v2
            self.exp7_post_v1 = 0.0
            self.exp7_post_v2 = 0.0
            self.exp7_prev_v1 = None
            self.exp7_prev_v2 = None
            self.exp7_collision_detected = False
            self.exp7_phase = "warmup"

            # Play timeline; no settling needed (zero gravity)
            self.simulation_control_enabled = True
            tl.play()
            await asyncio.sleep(EXP7_WARMUP_SECONDS)

            # Zero out any residual motion, then apply clean X-only velocities
            from omni.isaac.dynamic_control import _dynamic_control
            if self._dc_interface is None:
                self._dc_interface = _dynamic_control.acquire_dynamic_control_interface()
            dc = self._dc_interface
            for path, vel in [(EXP7_CART1_PATH, self.exp7_v1),
                               (EXP7_CART2_PATH, self.exp7_v2)]:
                h = dc.get_rigid_body(path)
                if h != _dynamic_control.INVALID_HANDLE:
                    dc.set_rigid_body_linear_velocity(h, (vel, 0.0, 0.0))
                    dc.set_rigid_body_angular_velocity(h, (0.0, 0.0, 0.0))

            self.exp7_phase = "running"

            # Deadline: auto-settle if no collision is detected in time.
            # closing_speed > 0 means carts are approaching each other.
            gap = abs(EXP7_CART2_INIT_POS[0] - EXP7_CART1_INIT_POS[0]) - EXP7_CART_SIZE[0]
            closing_speed = self.exp7_v1 - self.exp7_v2
            if closing_speed > 0.001:
                t_impact = gap / closing_speed
                self.exp7_deadline = time.time() + t_impact + 2.0
            else:
                self.exp7_deadline = time.time() + 3.0

            carb.log_warn(
                f"exp7: collision started  v1={self.exp7_v1} v2={self.exp7_v2} "
                f"m1={self.exp7_mass1} m2={self.exp7_mass2} e={self.exp7_restitution} "
                f"deadline_in={self.exp7_deadline - time.time():.1f}s"
            )
        except Exception as exc:
            carb.log_error(f"_start_exp7_collision: {exc}")

    async def _reset_exp7(self):
        """Reset exp7 state for the next trial."""
        self.exp7_phase = "idle"
        self.exp7_collision_detected = False
        self.exp7_prev_v1 = None
        self.exp7_prev_v2 = None
        self.exp7_post_v1 = 0.0
        self.exp7_post_v2 = 0.0
        self.exp7_deadline = 0.0

    def _check_exp7_collision(self, v1: float, v2: float):
        """Lightweight collision detector called every telemetry tick.

        Two exit paths to "settled":
          1. Normal: velocity spike detected → wait 0.4 s for settling → done.
          2. Timeout: deadline exceeded (carts never collided) → capture
             current velocities and move on so the UI is never stuck.
        """
        if self.exp7_phase != "running":
            return

        now = time.time()

        # --- Path 2: deadline timeout (no collision possible / missed) ---
        if now > self.exp7_deadline:
            self.exp7_post_v1 = v1
            self.exp7_post_v2 = v2
            self.exp7_phase = "settled"
            carb.log_warn("exp7: deadline reached — auto-settling (no collision detected)")
            return

        # --- Path 1: normal collision detection ---
        if self.exp7_prev_v1 is not None:
            dv1 = abs(v1 - self.exp7_prev_v1)
            dv2 = abs(v2 - self.exp7_prev_v2)
            if (dv1 + dv2) > 0.02:
                self.exp7_collision_detected = True
                self.exp7_collision_time = now
        self.exp7_prev_v1 = v1
        self.exp7_prev_v2 = v2

        if self.exp7_collision_detected and now - self.exp7_collision_time > 0.4:
            self.exp7_post_v1 = v1
            self.exp7_post_v2 = v2
            self.exp7_phase = "settled"

    # --- Experiment 8 — resonance in an air column ------------------------
    # Physics: a 1-D scalar wave equation is integrated by the standard
    # second-order leapfrog / central-difference finite-difference method
    # inside a driver asyncio task running at EXP8_WAVE_TICK_HZ.  The
    # resulting node-displacement field is written each tick into the pose
    # of kinematic "air slice" rigid bodies in the PhysX stage so that
    # standing waves emerge from authentic, transient dynamics — never
    # from a closed-form L = n·λ/4 formula.
    #
    # The dispersion relation of the FDM scheme matches the continuous
    # equation for spatial wavelengths ≫ h, so mode-lock locations and
    # relative amplitude ratios are quantitatively correct.

    _EXP8_CAM_EYE = Gf.Vec3d(0.60, -1.40, 0.78)
    _EXP8_CAM_TGT = Gf.Vec3d(0.60, 0.0, 0.40)
    _EXP8_CAM_FL = 16.0

    def _force_exp8_camera(self, stage=None):
        eye = self._EXP8_CAM_EYE
        tgt = self._EXP8_CAM_TGT
        fl = self._EXP8_CAM_FL
        try:
            self._try_set_camera_view(eye, tgt)
            if stage is None:
                stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            cam_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(cam_path)
            if not cam_prim or not cam_prim.IsValid():
                cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
            if cam_prim and cam_prim.IsValid():
                mtx = self._build_lookat_matrix(eye, tgt)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                camera = UsdGeom.Camera(cam_prim)
                camera.GetFocalLengthAttr().Set(fl)
                camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            self.camera_controller.set_from_eye_target(eye, tgt)
        except Exception as exc:
            carb.log_error(f"_force_exp8_camera: {exc}")

    async def _deferred_exp8_camera(self):
        for delay in (1.0, 2.0, 4.0):
            await asyncio.sleep(delay)
            if self.current_experiment != "8":
                return
            self._force_exp8_camera()

    def _exp8_reset_fields(self):
        """Zero the FDM displacement fields and the probe history."""
        n = EXP8_N_SLICES + 1
        self._exp8_u_prev = np.zeros(n, dtype=np.float64)
        self._exp8_u_curr = np.zeros(n, dtype=np.float64)
        self._exp8_u_next = np.zeros(n, dtype=np.float64)
        self._exp8_probe_history = []
        self._exp8_amp_history = []
        self._exp8_last_rms = 0.0
        self._exp8_last_peak = 0.0

    async def _setup_exp8_scene(self):
        """Build the resonance-tube scene from scratch: tube, speaker, piston,
        marker clips and N kinematic air-slice spheres that will visualise the
        simulated standing-wave displacement field."""
        try:
            ctx = omni.usd.get_context()
            ctx.new_stage()
            app = omni.kit.app.get_app()
            for _ in range(15):
                await app.next_update_async()
            stage = ctx.get_stage()
            if not stage:
                carb.log_error("exp8: no stage after new_stage()")
                return

            UsdGeom.Xform.Define(stage, "/World")
            UsdGeom.Xform.Define(stage, EXP8_ROOT_PATH)
            UsdGeom.Xform.Define(stage, EXP8_SLICE_ROOT)
            UsdGeom.Xform.Define(stage, EXP8_MARKER_ROOT)

            # Physics scene — gravity off (horizontal, air-column is 1-D along X)
            ps = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
            ps.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
            ps.CreateGravityMagnitudeAttr().Set(0.0)

            # Lighting
            UsdLux.DomeLight.Define(stage, f"{EXP8_ROOT_PATH}/DomeLight").CreateIntensityAttr(1300.0)
            rect = UsdLux.RectLight.Define(stage, f"{EXP8_ROOT_PATH}/RectLight")
            rect.CreateIntensityAttr(2200.0)
            rect.CreateWidthAttr(2.0)
            rect.CreateHeightAttr(0.6)
            rx = UsdGeom.Xformable(rect.GetPrim())
            rx.ClearXformOpOrder()
            rx.AddTranslateOp().Set(Gf.Vec3d(0.60, -0.4, 1.2))
            rx.AddRotateXYZOp().Set(Gf.Vec3f(-60.0, 0.0, 0.0))

            # Optical bench / lab table (visual only)
            self._exp8_make_visual(
                stage, f"{EXP8_ROOT_PATH}/bench",
                pos=(0.60, 0.0, EXP8_GROUND_Z),
                scale=(1.60, 0.70, 0.03),
                color=(0.22, 0.22, 0.26),
            )
            # Adjustable foot 1 & 2 — classical PASCO V-cradle mounts
            for i, fx in enumerate((0.10, EXP8_TUBE_TOTAL_LENGTH - 0.10)):
                self._exp8_make_visual(
                    stage, f"{EXP8_ROOT_PATH}/foot_{i}",
                    pos=(EXP8_TUBE_BASE_X + fx, 0.0, EXP8_TUBE_Z - EXP8_TUBE_DIAMETER / 2 - 0.06),
                    scale=(0.06, 0.12, 0.12),
                    color=(0.35, 0.38, 0.42),
                )

            # Main tube — a transparent-ish translucent shell.
            # We render it as a slightly-scaled cylinder along the X-axis so
            # users can see the internal air slices.
            self._exp8_make_tube(stage)

            # Speaker housing + driven diaphragm (kinematic rigid body we move
            # each wave tick so the PhysX pose matches the driver signal)
            self._exp8_make_speaker(stage)

            # Piston and handle
            self._exp8_make_piston(stage)

            # Marker clips (four ring-shaped clips that user can move)
            for i, mx in enumerate((0.25, 0.50, 0.75, 1.00)):
                path = EXP8_MARKER_PATH_TEMPLATE.format(i)
                self._exp8_make_visual(
                    stage, path,
                    pos=(EXP8_TUBE_BASE_X + mx, 0.0,
                         EXP8_TUBE_Z + EXP8_TUBE_DIAMETER / 2 + 0.012),
                    scale=(0.014, EXP8_TUBE_DIAMETER + 0.01, 0.006),
                    color=(0.95, 0.75, 0.20),
                )

            # Air-slice rigid bodies — these are the mass points whose
            # position is driven each physics step from the FDM solution.
            self._exp8_make_air_slices(stage)

            # Apply current piston position (= current tube length)
            await self._exp8_apply_piston_position()

            self._exp8_reset_fields()
            self.exp8_scene_built = True
            self.exp8_phase = "idle"
            self.exp8_driver_running = False

            for _ in range(6):
                await app.next_update_async()

            self._force_exp8_camera(stage)
            carb.log_warn(
                f"exp8: scene built  L={self.exp8_length_m*100:.1f} cm  "
                f"f={self.exp8_frequency:.1f} Hz  mode={self.exp8_mode}"
            )
        except Exception as exc:
            carb.log_error(f"_setup_exp8_scene: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    @staticmethod
    def _exp8_make_visual(stage, path, pos, scale, color, opacity: float = 1.0):
        """Create a purely visual cuboid (no physics body)."""
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])
        if opacity < 1.0:
            cube.CreateDisplayOpacityAttr([float(opacity)])

    def _exp8_make_tube(self, stage):
        """A translucent cylindrical shell along +X used purely for visuals."""
        tube = UsdGeom.Cylinder.Define(stage, EXP8_TUBE_PATH)
        tube.CreateHeightAttr(EXP8_TUBE_TOTAL_LENGTH)
        tube.CreateRadiusAttr(EXP8_TUBE_DIAMETER / 2.0 + EXP8_TUBE_WALL)
        tube.CreateAxisAttr("X")
        xf = UsdGeom.Xformable(tube.GetPrim())
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(
            EXP8_TUBE_BASE_X + EXP8_TUBE_TOTAL_LENGTH / 2.0,
            EXP8_TUBE_Y,
            EXP8_TUBE_Z,
        ))
        tube.CreateDisplayColorAttr([Gf.Vec3f(0.70, 0.82, 0.92)])
        tube.CreateDisplayOpacityAttr([0.22])

        # Inner hollow + end caps drawn as thin rings for definition
        ring_r = EXP8_TUBE_DIAMETER / 2.0
        for end_x in (EXP8_TUBE_BASE_X, EXP8_TUBE_BASE_X + EXP8_TUBE_TOTAL_LENGTH):
            cap = UsdGeom.Cylinder.Define(
                stage, f"{EXP8_TUBE_PATH}_cap_{int(end_x * 1000)}",
            )
            cap.CreateHeightAttr(0.006)
            cap.CreateRadiusAttr(ring_r + EXP8_TUBE_WALL * 1.2)
            cap.CreateAxisAttr("X")
            cf = UsdGeom.Xformable(cap.GetPrim())
            cf.ClearXformOpOrder()
            cf.AddTranslateOp().Set(Gf.Vec3d(end_x, EXP8_TUBE_Y, EXP8_TUBE_Z))
            cap.CreateDisplayColorAttr([Gf.Vec3f(0.50, 0.60, 0.70)])
            cap.CreateDisplayOpacityAttr([0.55])

        # Axis scale ticks underneath (every 10 cm)
        for i in range(13):
            gx = EXP8_TUBE_BASE_X + i * 0.10
            self._exp8_make_visual(
                stage, f"{EXP8_ROOT_PATH}/tick_{i:02d}",
                pos=(gx, 0.0, EXP8_TUBE_Z - EXP8_TUBE_DIAMETER / 2 - 0.011),
                scale=(0.003, 0.04, 0.004),
                color=(0.85, 0.85, 0.90),
            )

    def _exp8_make_speaker(self, stage):
        """Kinematic speaker housing + a driven diaphragm disk at x ≈ 0."""
        housing_path = EXP8_SPEAKER_PATH
        box_w = EXP8_TUBE_DIAMETER * 2.2
        box_h = EXP8_TUBE_DIAMETER * 2.2
        box_d = 0.10
        self._exp8_make_visual(
            stage, housing_path,
            pos=(EXP8_TUBE_BASE_X - box_d / 2.0 - 0.002, 0.0, EXP8_TUBE_Z),
            scale=(box_d, box_w, box_h),
            color=(0.12, 0.12, 0.14),
        )
        # Magnet / basket decoration
        self._exp8_make_visual(
            stage, f"{housing_path}_cone_ring",
            pos=(EXP8_TUBE_BASE_X - 0.005, 0.0, EXP8_TUBE_Z),
            scale=(0.008, box_w * 0.75, box_h * 0.75),
            color=(0.85, 0.60, 0.15),
        )

        # Kinematic diaphragm — we reposition each wave tick with the
        # driver signal so the PhysX pose matches the boundary condition
        # u(0, t) = A sin(2π f t).
        diaphragm = UsdGeom.Cylinder.Define(stage, EXP8_DIAPHRAGM_PATH)
        diaphragm.CreateHeightAttr(0.01)
        diaphragm.CreateRadiusAttr(EXP8_TUBE_DIAMETER / 2.0 * 0.85)
        diaphragm.CreateAxisAttr("X")
        dx = UsdGeom.Xformable(diaphragm.GetPrim())
        dx.ClearXformOpOrder()
        dx.AddTranslateOp().Set(Gf.Vec3d(EXP8_TUBE_BASE_X, EXP8_TUBE_Y, EXP8_TUBE_Z))
        diaphragm.CreateDisplayColorAttr([Gf.Vec3f(0.15, 0.75, 1.00)])
        prim = diaphragm.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)

    def _exp8_make_piston(self, stage):
        """Kinematic piston disk + handle at x = L (user-controlled position)."""
        disk = UsdGeom.Cylinder.Define(stage, EXP8_PISTON_PATH)
        disk.CreateHeightAttr(0.012)
        disk.CreateRadiusAttr(EXP8_TUBE_DIAMETER / 2.0 * 0.92)
        disk.CreateAxisAttr("X")
        px = UsdGeom.Xformable(disk.GetPrim())
        px.ClearXformOpOrder()
        px.AddTranslateOp().Set(Gf.Vec3d(
            EXP8_TUBE_BASE_X + self.exp8_length_m, EXP8_TUBE_Y, EXP8_TUBE_Z,
        ))
        disk.CreateDisplayColorAttr([Gf.Vec3f(0.85, 0.35, 0.20)])
        prim = disk.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
        UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)

        # Handle rod extending out of the tube (+X end)
        handle = UsdGeom.Cylinder.Define(stage, f"{EXP8_PISTON_PATH}_handle")
        handle.CreateHeightAttr(0.35)
        handle.CreateRadiusAttr(0.006)
        handle.CreateAxisAttr("X")
        hx = UsdGeom.Xformable(handle.GetPrim())
        hx.ClearXformOpOrder()
        hx.AddTranslateOp().Set(Gf.Vec3d(
            EXP8_TUBE_BASE_X + self.exp8_length_m + 0.18,
            EXP8_TUBE_Y, EXP8_TUBE_Z,
        ))
        handle.CreateDisplayColorAttr([Gf.Vec3f(0.75, 0.75, 0.78)])

        grip = UsdGeom.Sphere.Define(stage, f"{EXP8_PISTON_PATH}_grip")
        grip.CreateRadiusAttr(0.020)
        gx = UsdGeom.Xformable(grip.GetPrim())
        gx.ClearXformOpOrder()
        gx.AddTranslateOp().Set(Gf.Vec3d(
            EXP8_TUBE_BASE_X + self.exp8_length_m + 0.36,
            EXP8_TUBE_Y, EXP8_TUBE_Z,
        ))
        grip.CreateDisplayColorAttr([Gf.Vec3f(0.15, 0.15, 0.18)])

    def _exp8_make_air_slices(self, stage):
        """Build N kinematic sphere rigid bodies representing air mass points.
        These are the nodes whose displacement from equilibrium is produced
        by the wave equation solver."""
        for i in range(1, EXP8_N_SLICES):
            path = EXP8_SLICE_PATH_TEMPLATE.format(i)
            existing = stage.GetPrimAtPath(path)
            if existing and existing.IsValid():
                stage.RemovePrim(path)
            sphere = UsdGeom.Sphere.Define(stage, path)
            sphere.CreateRadiusAttr(EXP8_SLICE_DRAW_RADIUS)
            xf = UsdGeom.Xformable(sphere.GetPrim())
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(self._exp8_slice_rest_pos(i))
            # Colour varies along tube for easy identification of standing-wave
            # node/antinode locations at runtime.
            t = i / float(EXP8_N_SLICES)
            sphere.CreateDisplayColorAttr([Gf.Vec3f(
                0.20 + 0.70 * t, 0.40 + 0.20 * (1.0 - t), 0.85,
            )])
            prim = sphere.GetPrim()
            UsdPhysics.RigidBodyAPI.Apply(prim)
            UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)

    def _exp8_slice_rest_pos(self, i: int) -> Gf.Vec3d:
        """Rest-position (no wave displacement) for slice i along the tube."""
        L = max(0.05, float(self.exp8_length_m))
        x_rel = (i / float(EXP8_N_SLICES)) * L
        return Gf.Vec3d(
            EXP8_TUBE_BASE_X + x_rel, EXP8_TUBE_Y, EXP8_TUBE_Z,
        )

    async def _exp8_apply_piston_position(self):
        """Move the piston prim (and slice rest positions) to match current L.
        In 'open' mode the piston is parked just past the far end of the tube
        so the user still sees the hardware; physics uses a Neumann BC."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            if self.exp8_mode == "open":
                visual_x = EXP8_TUBE_BASE_X + EXP8_TUBE_TOTAL_LENGTH + 0.08
            else:
                visual_x = EXP8_TUBE_BASE_X + float(self.exp8_length_m)
            piston = stage.GetPrimAtPath(EXP8_PISTON_PATH)
            if piston and piston.IsValid():
                xf = UsdGeom.Xformable(piston)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(visual_x, EXP8_TUBE_Y, EXP8_TUBE_Z))
            handle = stage.GetPrimAtPath(f"{EXP8_PISTON_PATH}_handle")
            if handle and handle.IsValid():
                xf = UsdGeom.Xformable(handle)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(visual_x + 0.18, EXP8_TUBE_Y, EXP8_TUBE_Z))
            grip = stage.GetPrimAtPath(f"{EXP8_PISTON_PATH}_grip")
            if grip and grip.IsValid():
                xf = UsdGeom.Xformable(grip)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(visual_x + 0.36, EXP8_TUBE_Y, EXP8_TUBE_Z))
            # Reposition every air-slice sphere to its new rest X
            for i in range(1, EXP8_N_SLICES):
                path = EXP8_SLICE_PATH_TEMPLATE.format(i)
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid():
                    xf = UsdGeom.Xformable(prim)
                    xf.ClearXformOpOrder()
                    xf.AddTranslateOp().Set(self._exp8_slice_rest_pos(i))
        except Exception as exc:
            carb.log_error(f"_exp8_apply_piston_position: {exc}")

    def _exp8_freq_sim(self) -> float:
        """Return the simulation-time-scaled driver frequency.  Wave-speed
        ratio c_sim/c_real is applied uniformly so resonance lengths and
        mode ratios remain exactly equal to the real experiment."""
        return max(0.01, float(self.exp8_frequency) * EXP8_FREQ_SCALE)

    def _exp8_step_wave(self, dt: float, t_now: float):
        """Advance the FDM scheme by a single sub-step of size ``dt``.

        The discretisation is
            u_i^{n+1} = 2u_i^n - u_i^{n-1}
                     + (c·dt/h)² (u_{i+1}^n - 2 u_i^n + u_{i-1}^n)
                     - 2 γ dt (u_i^n - u_i^{n-1})
        with boundary conditions that depend on `self.exp8_mode`.
        """
        N = EXP8_N_SLICES
        L = max(0.05, float(self.exp8_length_m))
        c = EXP8_C_SIM
        h = L / N
        C2 = (c * dt / h) ** 2

        up = self._exp8_u_prev
        uc = self._exp8_u_curr
        un = self._exp8_u_next

        # Interior nodes (vectorised)
        un[1:N] = (2.0 * uc[1:N] - up[1:N]
                   + C2 * (uc[2:N + 1] - 2.0 * uc[1:N] + uc[0:N - 1])
                   - 2.0 * float(self.exp8_damping) * dt
                   * (uc[1:N] - up[1:N]))

        # Boundary 0 (speaker) — driven Dirichlet
        amp_m = float(self.exp8_amplitude_mm) * 0.001      # mm → m
        f_sim = self._exp8_freq_sim()
        un[0] = amp_m * math.sin(2.0 * math.pi * f_sim * t_now)

        # Boundary N (piston / open end)
        if self.exp8_mode == "closed":
            un[N] = 0.0                           # Dirichlet: no motion through piston
        else:
            # Open end: free Neumann (∂u/∂x = 0) implemented with a ghost
            # node u_{N+1} = u_{N-1}, giving the simple reflection-free stub
            un[N] = (2.0 * uc[N] - up[N]
                     + 2.0 * C2 * (uc[N - 1] - uc[N])
                     - 2.0 * float(self.exp8_damping) * dt
                     * (uc[N] - up[N]))

        # Rotate buffers
        self._exp8_u_prev = uc
        self._exp8_u_curr = un
        self._exp8_u_next = up            # reuse storage

    async def _exp8_driver_loop(self):
        """Background task: integrate the wave equation and update the pose
        of every slice prim so the Isaac Sim viewport reflects the current
        displacement field.  Runs at ``EXP8_WAVE_TICK_HZ`` with
        ``EXP8_PHYS_SUBSTEPS`` FDM sub-steps per tick to satisfy CFL even
        when the user shortens the tube aggressively."""
        try:
            tick_dt = 1.0 / float(EXP8_WAVE_TICK_HZ)
            carb.log_warn("exp8: driver loop started")
            while self.exp8_driver_running:
                loop_start = time.time()
                t_sim = loop_start - self.exp8_sim_start_time
                # Ensure CFL ⇒ sub-step dt below stability limit
                L = max(0.05, float(self.exp8_length_m))
                h = L / EXP8_N_SLICES
                dt_cfl = 0.9 * h / EXP8_C_SIM
                substeps = max(EXP8_PHYS_SUBSTEPS,
                               int(math.ceil(tick_dt / dt_cfl)))
                dt = tick_dt / substeps
                for s in range(substeps):
                    self._exp8_step_wave(dt, t_sim + s * dt)
                self._exp8_update_visuals()
                self._exp8_update_probe(t_sim)
                # Sleep to maintain tick rate (accounting for work done)
                remaining = tick_dt - (time.time() - loop_start)
                if remaining > 0:
                    await asyncio.sleep(remaining)
                else:
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            carb.log_warn("exp8: driver loop cancelled")
            raise
        except Exception as exc:
            carb.log_error(f"_exp8_driver_loop: {exc}")
            import traceback
            carb.log_error(traceback.format_exc())

    def _exp8_update_visuals(self):
        """Copy the current displacement field into Isaac Sim slice poses."""
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            amp = EXP8_AMP_SCALE
            # Speaker diaphragm (index 0)
            diaphragm = stage.GetPrimAtPath(EXP8_DIAPHRAGM_PATH)
            if diaphragm and diaphragm.IsValid():
                xf = UsdGeom.Xformable(diaphragm)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(
                    EXP8_TUBE_BASE_X + amp * float(self._exp8_u_curr[0]),
                    EXP8_TUBE_Y, EXP8_TUBE_Z,
                ))
            # Interior slices
            for i in range(1, EXP8_N_SLICES):
                path = EXP8_SLICE_PATH_TEMPLATE.format(i)
                prim = stage.GetPrimAtPath(path)
                if not (prim and prim.IsValid()):
                    continue
                rest = self._exp8_slice_rest_pos(i)
                dx = amp * float(self._exp8_u_curr[i])
                xf = UsdGeom.Xformable(prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(rest[0] + dx, rest[1], rest[2]))
        except Exception:
            pass

    def _exp8_update_probe(self, t_sim: float):
        """Sample the current |u| field to drive charts + resonance detection."""
        u = self._exp8_u_curr
        # Probe at the midpoint of the active tube (most sensitive to f1)
        idx_probe = max(1, int(0.5 * EXP8_N_SLICES))
        probe_val = float(u[idx_probe])
        self._exp8_probe_history.append((t_sim, probe_val))
        if len(self._exp8_probe_history) > EXP8_TELEMETRY_HISTORY:
            self._exp8_probe_history.pop(0)
        peak = float(np.max(np.abs(u[1:EXP8_N_SLICES])))
        self._exp8_amp_history.append(peak)
        if len(self._exp8_amp_history) > int(EXP8_WAVE_TICK_HZ):   # ~1 s window
            self._exp8_amp_history.pop(0)
        if self._exp8_amp_history:
            self._exp8_last_peak = float(np.max(self._exp8_amp_history))
        rms = float(np.sqrt(np.mean(u[1:EXP8_N_SLICES] ** 2))) if EXP8_N_SLICES > 1 else 0.0
        self._exp8_last_rms = rms
        drive_amp_m = max(1e-9, float(self.exp8_amplitude_mm) * 0.001)
        self._exp8_resonance_ratio = self._exp8_last_peak / drive_amp_m

    def _exp8_resonance_lengths(self) -> list:
        """Predicted piston positions (metres) at which the current driver
        frequency produces resonance.  Includes the empirical end-effect
        correction (0.3 d for closed, 0.6 d for open tubes)."""
        f = max(1.0, float(self.exp8_frequency))
        lam = EXP8_C_REAL / f
        d = EXP8_TUBE_DIAMETER
        results = []
        if self.exp8_mode == "closed":
            # L + 0.3 d = (2n − 1) λ / 4
            for n in range(1, 12):
                L = (2 * n - 1) * lam / 4.0 - 0.3 * d
                if 0.02 <= L <= EXP8_TUBE_TOTAL_LENGTH:
                    results.append((n, round(L, 4)))
        else:
            # L + 0.6 d = n λ / 2
            for n in range(1, 12):
                L = n * lam / 2.0 - 0.6 * d
                if 0.02 <= L <= EXP8_TUBE_TOTAL_LENGTH:
                    results.append((n, round(L, 4)))
        return results

    def _exp8_resonance_frequencies(self) -> list:
        """Predicted resonance frequencies at the current piston position."""
        L = float(self.exp8_length_m)
        d = EXP8_TUBE_DIAMETER
        results = []
        if self.exp8_mode == "closed":
            # f_n = (2n − 1) c / [4 (L + 0.3 d)]
            denom = max(1e-6, L + 0.3 * d)
            for n in range(1, 8):
                f_n = (2 * n - 1) * EXP8_C_REAL / (4.0 * denom)
                if 20.0 <= f_n <= 5000.0:
                    results.append((n, round(f_n, 1)))
        else:
            denom = max(1e-6, L + 0.6 * d)
            for n in range(1, 8):
                f_n = n * EXP8_C_REAL / (2.0 * denom)
                if 20.0 <= f_n <= 5000.0:
                    results.append((n, round(f_n, 1)))
        return results

    def _exp8_nearest_resonance(self):
        """Return (n*, f_n*, relative_detuning) for the nearest mode."""
        fs = self._exp8_resonance_frequencies()
        if not fs:
            return (0, 0.0, 1.0)
        f_now = float(self.exp8_frequency)
        best = min(fs, key=lambda nf: abs(nf[1] - f_now))
        det = (f_now - best[1]) / best[1] if best[1] > 0 else 1.0
        self._exp8_nearest_mode = best[0]
        return (best[0], best[1], round(det, 4))

    async def _start_exp8_drive(self):
        """Start (or restart) the wave driver and PhysX timeline."""
        try:
            if not self.exp8_scene_built:
                await self._setup_exp8_scene()

            # Cancel any previous driver
            if self._exp8_update_task and not self._exp8_update_task.done():
                self.exp8_driver_running = False
                self._exp8_update_task.cancel()
                try:
                    await self._exp8_update_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._exp8_update_task = None

            self._exp8_reset_fields()
            self.exp8_sim_start_time = time.time()
            self.exp8_driver_running = True
            self.exp8_phase = "running"
            self._exp8_update_task = asyncio.ensure_future(self._exp8_driver_loop())

            tl = omni.timeline.get_timeline_interface()
            self.simulation_control_enabled = True
            tl.play()
            carb.log_warn(
                f"exp8: driver started  L={self.exp8_length_m*100:.1f}cm  "
                f"f={self.exp8_frequency:.1f}Hz  A={self.exp8_amplitude_mm:.2f}mm  "
                f"mode={self.exp8_mode}  f_sim={self._exp8_freq_sim():.3f}Hz"
            )
        except Exception as exc:
            carb.log_error(f"_start_exp8_drive: {exc}")

    async def _stop_exp8_drive(self):
        """Halt the wave driver without tearing down the scene."""
        try:
            self.exp8_driver_running = False
            if self._exp8_update_task and not self._exp8_update_task.done():
                self._exp8_update_task.cancel()
                try:
                    await self._exp8_update_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._exp8_update_task = None
            self.exp8_phase = "stopped"
            carb.log_warn("exp8: driver stopped")
        except Exception as exc:
            carb.log_error(f"_stop_exp8_drive: {exc}")

    async def _reset_exp8(self):
        """Return every slice to its rest position and clear measurements."""
        await self._stop_exp8_drive()
        self._exp8_reset_fields()
        self.exp8_phase = "idle"
        try:
            stage = omni.usd.get_context().get_stage()
            if stage:
                for i in range(1, EXP8_N_SLICES):
                    path = EXP8_SLICE_PATH_TEMPLATE.format(i)
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        xf = UsdGeom.Xformable(prim)
                        xf.ClearXformOpOrder()
                        xf.AddTranslateOp().Set(self._exp8_slice_rest_pos(i))
                dia = stage.GetPrimAtPath(EXP8_DIAPHRAGM_PATH)
                if dia and dia.IsValid():
                    xf = UsdGeom.Xformable(dia)
                    xf.ClearXformOpOrder()
                    xf.AddTranslateOp().Set(Gf.Vec3d(
                        EXP8_TUBE_BASE_X, EXP8_TUBE_Y, EXP8_TUBE_Z,
                    ))
        except Exception as exc:
            carb.log_error(f"_reset_exp8: {exc}")

    def _exp8_telemetry(self, now: float, tl) -> dict:
        """Build the per-tick telemetry payload for experiment 8."""
        try:
            n_mode, f_mode, detuning = self._exp8_nearest_resonance()
            res_lengths = self._exp8_resonance_lengths()
            res_freqs = self._exp8_resonance_frequencies()
            u = self._exp8_u_curr
            # Compress the per-node displacement to a compact envelope for the
            # client (front-end bandwidth friendly, but enough to draw the
            # real-time standing-wave shape).
            envelope = np.abs(u[:EXP8_N_SLICES + 1]).astype(np.float32)
            env_list = envelope.tolist()
            env_list = [round(v, 6) for v in env_list]
            probe_trace = [round(v, 6) for (_, v) in self._exp8_probe_history[-128:]]
            running = self.exp8_driver_running
            return {
                "timestamp": now,
                "amplitude": round(self._exp8_last_rms, 6),
                "peak_amplitude": round(self._exp8_last_peak, 6),
                "resonance_ratio": round(self._exp8_resonance_ratio, 3),
                "resonance_peaks": round(self._exp8_resonance_ratio, 3),
                "is_resonant": self._exp8_resonance_ratio >= EXP8_RESONANCE_THRESHOLD,
                "probe_value": round(float(u[max(1, int(0.5 * EXP8_N_SLICES))]), 6),
                "probe_trace": probe_trace,
                "envelope": env_list,
                "length_cm": round(self.exp8_length_m * 100.0, 2),
                "length_m": round(self.exp8_length_m, 4),
                "frequency": round(self.exp8_frequency, 2),
                "amplitude_mm": round(self.exp8_amplitude_mm, 3),
                "damping": round(self.exp8_damping, 3),
                "mode": self.exp8_mode,
                "wavelength": round(EXP8_C_REAL / max(1.0, self.exp8_frequency), 4),
                "n_mode": int(n_mode),
                "f_mode": float(f_mode),
                "detuning": float(detuning),
                "resonance_lengths": res_lengths,
                "resonance_frequencies": res_freqs,
                "c_sound": EXP8_C_REAL,
                "tube_diameter": EXP8_TUBE_DIAMETER,
                "is_running": running,
                "phase": self.exp8_phase,
            }
        except Exception as exc:
            carb.log_error(f"_exp8_telemetry: {exc}")
            return {"timestamp": now, "is_running": False, "phase": "error"}

    # --- Telemetry loop ----------------------------------------------------

    async def _telemetry_loop(self):
        while True:
            try:
                tl = omni.timeline.get_timeline_interface()
                if self.ws_clients:
                    now = time.time()
                    if self.current_experiment == "1":
                        dv_raw, rv_raw = (0.0, 0.0) if not tl.is_playing() else self._get_angular_velocities()
                        # Analytical fallback when live readback returns 0
                        if tl.is_playing() and abs(dv_raw) < 0.001:
                            if self.exp1_phase == "spinning":
                                dv_raw = self.exp1_initial_vel
                            elif self.exp1_phase == "dropped":
                                dv_raw = self.exp1_omega_after_drop
                                rv_raw = self.exp1_omega_after_drop
                        if tl.is_playing() and self.exp1_phase == "dropped" and abs(rv_raw) < 0.001:
                            rv_raw = self.exp1_omega_after_drop
                        # Sensor noise ±0.002 rad/s (PASCO Rotary Motion Sensor)
                        dv = dv_raw + random.gauss(0, 0.002) if tl.is_playing() else 0.0
                        rv = rv_raw + random.gauss(0, 0.002) if tl.is_playing() else 0.0
                        # Bearing damping: slow linear decay (simulates bearing friction)
                        if self.exp1_phase == "spinning" and tl.is_playing():
                            damping = 1.0 - 0.0008
                            dv *= damping
                            self.exp1_initial_vel *= damping
                        R_d = self.exp1_disk_radius
                        I_disk = 0.5 * self.exp1_disk_mass * (R_d ** 2)
                        offset = getattr(self, 'exp1_drop_offset', 0.0)
                        if self.exp1_drop_object == "ring":
                            R1, R2 = self.exp1_ring_inner_r, self.exp1_ring_outer_r
                            I_obj = 0.5 * self.exp1_ring_mass * (R1**2 + R2**2) + self.exp1_ring_mass * offset**2
                        else:
                            I_obj = 0.5 * self.exp1_ring_mass * (R_d ** 2) + self.exp1_ring_mass * offset**2
                        I_total = I_disk + I_obj
                        live_am = I_disk * dv + I_obj * rv
                        live_ke = 0.5 * I_disk * dv * dv + 0.5 * I_obj * rv * rv
                        if self.exp1_phase == "dropped" and abs(dv - rv) < 0.3 and self.exp1_omega_after_drop == 0.0:
                            self.exp1_omega_after_drop = (dv + rv) / 2
                            self.exp1_final_am = I_total * self.exp1_omega_after_drop
                            self.exp1_ke_final = 0.5 * I_total * self.exp1_omega_after_drop ** 2
                        ke_loss_pct = 0.0
                        if self.exp1_ke_initial > 0:
                            ke_loss_pct = ((self.exp1_ke_final - self.exp1_ke_initial) / self.exp1_ke_initial) * 100
                        am_diff_pct = 0.0
                        if self.exp1_initial_am != 0:
                            am_diff_pct = ((self.exp1_final_am - self.exp1_initial_am) / self.exp1_initial_am) * 100
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "disk_angular_velocity": round(dv, 3),
                            "ring_angular_velocity": round(rv, 3),
                            "angular_momentum": round(live_am, 6),
                            "kinetic_energy": round(live_ke, 6),
                            "disk_mass": self.exp1_disk_mass,
                            "ring_mass": self.exp1_ring_mass,
                            "initial_velocity": round(self.exp1_initial_vel, 2),
                            "is_running": tl.is_playing(),
                            "phase": self.exp1_phase,
                            "drop_object": self.exp1_drop_object,
                            "drop_offset_cm": round(offset * 100, 3),
                            "I_initial": round(I_disk, 8),
                            "I_final": round(I_total, 8),
                            "omega_before_drop": round(self.exp1_omega_before_drop, 4),
                            "omega_after_drop": round(self.exp1_omega_after_drop, 4),
                            "initial_angular_momentum": round(self.exp1_initial_am, 6),
                            "final_angular_momentum": round(self.exp1_final_am, 6),
                            "am_diff_percent": round(am_diff_pct, 2),
                            "ke_initial": round(self.exp1_ke_initial, 6),
                            "ke_final": round(self.exp1_ke_final, 6),
                            "ke_loss_percent": round(ke_loss_pct, 2),
                        }}
                    elif self.current_experiment == "2":
                        theta_deg = round(np.degrees(self.exp2_theta), 3)
                        T_series = self._exp2_period_series(self.exp2_amplitude, 5) if self.exp2_amplitude > 0.01 else self._exp2_T0
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "theta": theta_deg,
                            "omega": round(self.exp2_omega, 4),
                            "alpha": round(self.exp2_alpha, 4),
                            "period": round(self.exp2_measured_period, 4),
                            "T0_theory": round(self._exp2_T0, 4),
                            "T_series": round(T_series, 4),
                            "amplitude_deg": round(np.degrees(self.exp2_amplitude), 1),
                            "damping": self.exp2_damping,
                            "sim_time": round(self.exp2_sim_time, 3),
                            "phase": self.exp2_phase,
                            "is_running": self.exp2_phase == "running",
                        }}
                    elif self.current_experiment == "3":
                        g = 9.81
                        if tl.is_playing() and self.exp3_scene_built:
                            theta, omega = self._read_exp3_pendulum_state()
                            self.exp3_theta = theta
                            self.exp3_omega = omega
                            self.exp3_ball_velocity = self._read_exp3_ball_speed()
                            self._exp3_update_swing_metrics(theta, omega, now)
                        theta = self.exp3_theta
                        theta_max = self.exp3_theta_max
                        L = float(self.exp3_L)
                        M = float(self.exp3_ball_mass) + float(self.exp3_pend_mass)
                        h = L * (1.0 - math.cos(theta)) if abs(theta) > 1e-6 else 0.0
                        h_max = L * (1.0 - math.cos(theta_max)) if theta_max > 1e-6 else 0.0
                        # KE of the ball-catcher system just after collision
                        # (ideal inelastic model, independent of PhysX state)
                        p_in = float(self.exp3_ball_mass) * float(self.exp3_v0)
                        v_after_ideal = p_in / M if M > 1e-9 else 0.0
                        ke_after_ideal = 0.5 * M * v_after_ideal * v_after_ideal
                        ke_loss_pct = 0.0
                        ke_in = 0.5 * float(self.exp3_ball_mass) * float(self.exp3_v0) ** 2
                        if ke_in > 1e-9:
                            ke_loss_pct = (ke_in - ke_after_ideal) / ke_in * 100.0
                        v0_meas = float(self.exp3_v0_measured)
                        v0_err_pct = 0.0
                        if self.exp3_v0 > 1e-6 and v0_meas > 0.0:
                            v0_err_pct = (v0_meas - self.exp3_v0) / self.exp3_v0 * 100.0
                        sim_time = (now - self.exp3_fire_time) if self.exp3_fire_time > 0 else 0.0
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            # charted keys
                            "theta": round(math.degrees(theta), 3),
                            "omega": round(float(self.exp3_omega), 4),
                            "ball_velocity": round(float(self.exp3_ball_velocity), 3),
                            "height": round(h, 5),
                            # status panel metrics
                            "theta_max": round(math.degrees(theta_max), 3),
                            "h_max": round(h_max, 5),
                            "v0_input": round(float(self.exp3_v0), 3),
                            "v0_measured": round(v0_meas, 3),
                            "v0_error_pct": round(v0_err_pct, 2),
                            "v_after_ideal": round(v_after_ideal, 4),
                            "ke_input": round(ke_in, 5),
                            "ke_after_ideal": round(ke_after_ideal, 5),
                            "ke_loss_percent": round(ke_loss_pct, 2),
                            "ball_mass": float(self.exp3_ball_mass),
                            "pend_mass": float(self.exp3_pend_mass),
                            "L": float(self.exp3_L),
                            "M_total": round(M, 5),
                            "sim_time": round(sim_time, 3),
                            "phase": self.exp3_phase,
                            "is_running": tl.is_playing(),
                            # legacy field names so older UI builds keep working
                            "velocity": round(float(self.exp3_ball_velocity), 3),
                            "energy": round(ke_after_ideal, 5),
                        }}
                    elif self.current_experiment == "4":
                        if tl.is_playing():
                            theta_live, omega_live = self._read_exp4_state()
                            self.exp4_theta = theta_live
                            self.exp4_omega = omega_live
                            self._exp4_update_peak(theta_live)
                            sim_time = now - self.exp4_sim_start_time
                        else:
                            sim_time = 0.0
                        I = self._exp4_I()
                        b_SI = float(self.exp4_damping_gamma) * I
                        theta_deg = math.degrees(self.exp4_theta)
                        theta_drv_deg = math.degrees(self.exp4_theta_drive)
                        # Current energies (reported for pedagogical value)
                        ke = 0.5 * I * (self.exp4_omega ** 2)
                        pe = 0.5 * float(self.exp4_spring_k) * (self.exp4_theta ** 2)
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            # live state
                            "theta": round(theta_deg, 3),
                            "omega": round(self.exp4_omega, 4),
                            "theta_drive": round(theta_drv_deg, 3),
                            "amplitude": round(math.degrees(self.exp4_peak_amp), 3),
                            "sim_time": round(sim_time, 3),
                            # analytical theory (reference, not used by PhysX)
                            "f_drive": round(float(self.exp4_frequency), 4),
                            "f_natural": round(self._exp4_natural_freq_hz(), 4),
                            "omega_drive_rad": round(2.0 * math.pi * float(self.exp4_frequency), 4),
                            "omega_natural_rad": round(2.0 * math.pi * self._exp4_natural_freq_hz(), 4),
                            "theory_amp_deg": round(math.degrees(self._exp4_theory_amplitude()), 3),
                            "phase_lag_deg": round(self._exp4_theory_phase_deg(), 2),
                            "quality_factor": round(self._exp4_Q(), 2),
                            # drivers / params
                            "drive_amp_deg": round(math.degrees(float(self.exp4_drive_amp)), 2),
                            "drive_amp_rad": round(float(self.exp4_drive_amp), 4),
                            "spring_k": round(float(self.exp4_spring_k), 6),
                            "damping_gamma": round(float(self.exp4_damping_gamma), 4),
                            "damping_b_SI": round(b_SI, 8),
                            "inertia_I": round(I, 8),
                            "disk_mass": round(float(self.exp4_disk_mass), 4),
                            "disk_radius": round(float(self.exp4_disk_radius), 4),
                            # energies
                            "kinetic_energy": round(ke, 8),
                            "potential_energy": round(pe, 8),
                            # state
                            "phase": self.exp4_phase,
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "5":
                        if tl.is_playing():
                            theta_live, omega_live = self._read_exp5_state()
                            self.exp5_theta = theta_live
                            self.exp5_omega = omega_live
                            sim_time = now - self.exp5_sim_start_time
                            self._exp5_update_period_measurement(theta_live, sim_time)
                        else:
                            sim_time = 0.0
                        L = max(1e-6, float(self.exp5_L))
                        x = max(1e-6, float(self.exp5_x))
                        I_cm = self.exp5_m * L * L / 12.0
                        I_total = I_cm + self.exp5_m * x * x
                        T_theory = self._exp5_T_theory()
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "theta": round(math.degrees(self.exp5_theta), 3),
                            "omega": round(self.exp5_omega, 4),
                            "period": round(self.exp5_measured_period, 4),
                            "T_theory": round(T_theory, 4),
                            "inertia": round(I_total, 6),
                            "I_cm": round(I_cm, 6),
                            "x_min_period": round(self._exp5_x_min_period(), 4),
                            "sim_time": round(sim_time, 3),
                            "m": self.exp5_m,
                            "L": self.exp5_L,
                            "x": self.exp5_x,
                            "theta0_deg": self.exp5_theta0_deg,
                            "phase": self.exp5_phase,
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "6":
                        fc = self.exp6_mass * self.exp6_radius * self.exp6_angular_velocity ** 2
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "centripetal_force": round(fc, 2),
                            "tension": round(fc, 2),
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "7":
                        v1x = self._read_exp7_vx(EXP7_CART1_PATH) if tl.is_playing() else 0.0
                        v2x = self._read_exp7_vx(EXP7_CART2_PATH) if tl.is_playing() else 0.0
                        if tl.is_playing():
                            self._check_exp7_collision(v1x, v2x)
                        p1 = self.exp7_mass1 * v1x
                        p2 = self.exp7_mass2 * v2x
                        ke1 = 0.5 * self.exp7_mass1 * v1x * v1x
                        ke2 = 0.5 * self.exp7_mass2 * v2x * v2x
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "v1": round(v1x, 4),
                            "v2": round(v2x, 4),
                            "p1": round(p1, 4),
                            "p2": round(p2, 4),
                            "p_total": round(p1 + p2, 4),
                            "ke1": round(ke1, 4),
                            "ke2": round(ke2, 4),
                            "ke_total": round(ke1 + ke2, 4),
                            "x1": round(self._read_exp7_px(EXP7_CART1_PATH), 4),
                            "x2": round(self._read_exp7_px(EXP7_CART2_PATH), 4),
                            "phase": self.exp7_phase,
                            "is_running": tl.is_playing(),
                            "v1_initial": round(self.exp7_pre_v1, 4),
                            "v2_initial": round(self.exp7_pre_v2, 4),
                            "v1_final": round(self.exp7_post_v1, 4),
                            "v2_final": round(self.exp7_post_v2, 4),
                            "mass1": self.exp7_mass1,
                            "mass2": self.exp7_mass2,
                            "restitution": self.exp7_restitution,
                        }}
                    elif self.current_experiment == "8":
                        msg = {"type": "telemetry", "data": self._exp8_telemetry(now, tl)}
                    else:
                        msg = {"type": "telemetry", "data": {"timestamp": now, "is_running": tl.is_playing()}}

                    # VR hand tracking: tick + inject status into telemetry
                    if self.vr_bridge.enabled:
                        vr_info = self.vr_bridge.tick(
                            TELEMETRY_BROADCAST_INTERVAL,
                            graspable_paths=self._vr_graspable_paths(),
                        )
                        msg["data"]["vr"] = vr_info

                    for ws in list(self.ws_clients):
                        if not ws.closed:
                            await ws.send_json(msg)
            except Exception:
                pass
            await asyncio.sleep(TELEMETRY_BROADCAST_INTERVAL)

    # --- WebSocket JPEG video fallback (works through SSH tunnels) ---------

    async def video_feed_handler(self, request):
        """Stream viewport frames as JPEG over a WebSocket.

        Used as a fallback when WebRTC ICE cannot connect (e.g. SSH tunnel).
        Lower quality/fps than WebRTC but works over any TCP proxy.
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        carb.log_warn("WS video feed client connected")

        capture = _SharedFrameCapture.instance()
        try:
            while not ws.closed:
                jpeg_bytes = await capture.grab_jpeg(
                    width=1920, height=1080, quality=80
                )
                if jpeg_bytes:
                    await ws.send_bytes(jpeg_bytes)
                await asyncio.sleep(1.0 / 24)  # ~24 fps
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        except Exception as exc:
            carb.log_error(f"video_feed error: {exc}")
        carb.log_warn("WS video feed client disconnected")
        return ws

    # --- Lifecycle ---------------------------------------------------------

    async def start(self):
        if not HAS_WEBRTC:
            carb.log_error("Cannot start — aiortc/aiohttp not installed")
            return

        app = web.Application()
        app.router.add_post("/offer", self.offer)
        app.router.add_post("/camera", self.camera_control)
        app.router.add_post("/load_usd", self.load_usd)
        app.router.add_get("/video_feed", self.video_feed_handler)

        outputs_dir = os.path.join(_PROJECT_ROOT, "outputs")
        os.makedirs(outputs_dir, exist_ok=True)
        app.router.add_static("/outputs", outputs_dir, show_index=True)

        async def _cors_options(r):
            return web.Response(headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
            })
        app.router.add_options("/{tail:.*}", _cors_options)

        self._http_runner = web.AppRunner(app)
        await self._http_runner.setup()
        self._http_site = web.TCPSite(self._http_runner, self.host, self.http_port)
        await self._http_site.start()

        ws_app = web.Application()
        ws_app.router.add_get("/", self.websocket_handler)
        self._ws_runner = web.AppRunner(ws_app)
        await self._ws_runner.setup()
        self._ws_site = web.TCPSite(self._ws_runner, self.host, self.ws_port)
        await self._ws_site.start()

        self._monitor_task = asyncio.ensure_future(self._telemetry_loop())

        # Start VR hand tracking receiver
        if self.vr_bridge.enabled:
            self.vr_bridge.start()
            carb.log_info(f"VR hand tracking listening on UDP :{VR_UDP_PORT}")

        carb.log_info(
            f"Server started — HTTP :{self.http_port}  WS :{self.ws_port}  IP {HOST_IP}"
        )

    async def stop(self):
        if self._monitor_task:
            self._monitor_task.cancel()
        if self.vr_bridge.enabled:
            self.vr_bridge.stop()
        if hasattr(self, "_http_site"):
            await self._http_site.stop()
        if hasattr(self, "_ws_site"):
            await self._ws_site.stop()
        for pc in self.pcs:
            await pc.close()
