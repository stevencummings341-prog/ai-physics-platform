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
    EXP7_CART1_PATH, EXP7_CART2_PATH, EXP7_GROUND_PATH, EXP7_MATERIAL_PATH,
    EXP7_DEFAULT_MASS1, EXP7_DEFAULT_MASS2,
    EXP7_DEFAULT_V1, EXP7_DEFAULT_V2, EXP7_DEFAULT_RESTITUTION,
    EXP7_CART_SIZE, EXP7_CART1_INIT_POS, EXP7_CART2_INIT_POS,
    EXP7_WARMUP_SECONDS, EXP7_SOLVER_POS_ITERS, EXP7_SOLVER_VEL_ITERS,
)

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

        # Experiment 3 — ballistic pendulum
        self.exp3_projectile_mass = 0.05
        self.exp3_pendulum_mass = 2.0

        # Experiment 4 — driven damped oscillation
        self.exp4_damping = 0.5
        self.exp4_frequency = 1.0

        # Experiment 5 — rotational inertia
        self.exp5_pivot = 25.0
        self.exp5_angle = 10.0

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

        # Experiment 8 — resonance in air column
        self.exp8_length = 50.0
        self.exp8_frequency = 512.0

        # Generic per-experiment parameter store for telemetry
        self._exp_params: Dict[str, Dict[str, float]] = {}

        self.current_experiment = "1"

        self._dc_interface = None

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
            elif self.current_experiment == "7":
                await self._reset_exp7()
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
            elif exp_id == "7":
                await self._setup_exp7_scene()
            await self._switch_camera(exp_id)
            if exp_id == "1":
                await self._apply_exp1_params()
                asyncio.ensure_future(self._deferred_camera_readjust())
            elif exp_id == "2":
                asyncio.ensure_future(self._deferred_exp2_camera())
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
        elif mtype == "set_projectile_mass":
            self.exp3_projectile_mass = float(data.get("value", 0.05))
            await self._apply_mass_at("/World/exp3/projectile", self.exp3_projectile_mass)
        elif mtype == "set_pendulum_mass":
            self.exp3_pendulum_mass = float(data.get("value", 2.0))
            await self._apply_mass_at("/World/exp3/pendulum", self.exp3_pendulum_mass)

        # Experiment 4 — driven damped oscillation
        elif mtype == "set_damping":
            self.exp4_damping = float(data.get("value", 0.5))
        elif mtype == "set_frequency":
            val = float(data.get("value", 1.0))
            if self.current_experiment == "4":
                self.exp4_frequency = val
            elif self.current_experiment == "8":
                self.exp8_frequency = val

        # Experiment 5 — rotational inertia
        elif mtype == "set_pivot":
            self.exp5_pivot = float(data.get("value", 25.0))
        elif mtype == "set_angle":
            self.exp5_angle = float(data.get("value", 10.0))

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
            self.exp8_length = float(data.get("value", 50.0))

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
                    "3": (Gf.Vec3d(-0.5, 6.8, 3.2), Gf.Vec3d(0, 6, 2.5), 18.0),
                    "7": (Gf.Vec3d(0.0, -1.6, 0.6), Gf.Vec3d(0, 0, 0.0), 24.0),
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
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "velocity": self._read_velocity("/World/exp3/projectile"),
                            "energy": self._read_kinetic_energy("/World/exp3/projectile", self.exp3_projectile_mass),
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "4":
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "displacement": self._read_displacement("/World/exp4/oscillator"),
                            "amplitude": abs(self._read_displacement("/World/exp4/oscillator")),
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "5":
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "period": 0.0,
                            "inertia": 0.0,
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
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "amplitude": 0.0,
                            "resonance_peaks": 0.0,
                            "is_running": tl.is_playing(),
                        }}
                    else:
                        msg = {"type": "telemetry", "data": {"timestamp": now, "is_running": tl.is_playing()}}
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
        carb.log_info(
            f"Server started — HTTP :{self.http_port}  WS :{self.ws_port}  IP {HOST_IP}"
        )

    async def stop(self):
        if self._monitor_task:
            self._monitor_task.cancel()
        if hasattr(self, "_http_site"):
            await self._http_site.stop()
        if hasattr(self, "_ws_site"):
            await self._ws_site.stop()
        for pc in self.pcs:
            await pc.close()
