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

import numpy as np

# Isaac Sim core — must already be initialised before this module loads
import carb
import omni.ext
import omni.kit.viewport.utility as vp_util
import omni.usd
import omni.timeline
from pxr import Gf, UsdGeom, UsdPhysics

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
    EXP2_GROUP_PATH, EXP2_CYLINDER_PATH,
    EXP2_MASS1_PATH, EXP2_MASS2_PATH,
    EXP2_DEFAULT_INITIAL_ANGLE, EXP2_DEFAULT_MASS1, EXP2_DEFAULT_MASS2,
    REPLICATOR_INIT_MAX_RETRIES, CAMERA_SCRIPT_DIR,
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
# Camera controller
# ===================================================================
class CameraController:
    def __init__(self):
        self.distance = 10.0
        self.azimuth = 45.0
        self.elevation = 30.0
        self.target = Gf.Vec3d(0, 0, 0)

    def orbit(self, dx, dy):
        self.azimuth = (self.azimuth + dx * 0.3) % 360
        self.elevation = max(-89, min(89, self.elevation + dy * 0.3))
        self._apply()

    def zoom(self, delta):
        self.distance = max(1.0, self.distance + delta * 0.1)
        self._apply()

    def reset(self):
        self.distance, self.azimuth, self.elevation = 10.0, 45.0, 30.0
        self._apply()

    def _apply(self):
        try:
            viewport = vp_util.get_active_viewport()
            if not viewport:
                return
            cam = viewport.get_active_camera()
            if not cam:
                return
            az = math.radians(self.azimuth)
            el = math.radians(self.elevation)
            x = self.distance * math.cos(el) * math.cos(az)
            y = self.distance * math.cos(el) * math.sin(az)
            z = self.distance * math.sin(el)
            pos = self.target + Gf.Vec3d(x, y, z)
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            prim = stage.GetPrimAtPath(cam)
            if prim and prim.IsValid():
                xform = UsdGeom.Xformable(prim)
                xform.AddTranslateOp().Set(pos)
        except Exception:
            pass


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

        # Experiment 2 — large-amplitude pendulum
        self.exp2_initial_angle = EXP2_DEFAULT_INITIAL_ANGLE
        self.exp2_mass1 = EXP2_DEFAULT_MASS1
        self.exp2_mass2 = EXP2_DEFAULT_MASS2

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

        # Experiment 7 — momentum conservation
        self.exp7_mass1 = 1.0
        self.exp7_mass2 = 1.0
        self.exp7_velocity1 = 5.0
        self.exp7_elasticity = 1.0

        # Experiment 8 — resonance in air column
        self.exp8_length = 50.0
        self.exp8_frequency = 512.0

        # Generic per-experiment parameter store for telemetry
        self._exp_params: Dict[str, Dict[str, float]] = {}

        self.current_experiment = "1"
        self.exp2_angle_history: list = []
        self.exp2_last_peak_time = None
        self.exp2_period = 0.0
        self.exp2_period_samples: list = []
        self.exp2_zero_cross_times: list = []
        self.exp2_last_angle_sign = None

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

        # Patch SDP with real server IP
        sdp_lines = answer.sdp.splitlines()
        new_lines = []
        for line in sdp_lines:
            if "c=IN IP4" in line:
                new_lines.append(f"c=IN IP4 {HOST_IP}")
            elif line.startswith("o="):
                new_lines.append(line.replace("0.0.0.0", HOST_IP).replace("127.0.0.1", HOST_IP))
            elif "a=candidate" in line:
                new_lines.append(line.replace("0.0.0.0", HOST_IP).replace("127.0.0.1", HOST_IP).replace(".local", ""))
            else:
                new_lines.append(line)
        patched = RTCSessionDescription(sdp="\r\n".join(new_lines) + "\r\n", type=answer.type)
        await pc.setLocalDescription(patched)
        return web.Response(
            content_type="application/json",
            text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def camera_control(self, request):
        p = await request.json()
        action = p.get("action")
        if action == "orbit":
            self.camera_controller.orbit(p.get("deltaX", 0), p.get("deltaY", 0))
        elif action == "zoom":
            self.camera_controller.zoom(p.get("delta", 0))
        elif action == "reset":
            self.camera_controller.reset()
        return web.Response(text=json.dumps({"status": "ok"}))

    async def load_usd(self, request):
        p = await request.json()
        usd_path = p.get("usd_path", DEFAULT_USD_PATH)
        ok = omni.usd.get_context().open_stage(usd_path)
        if ok:
            self.simulation_control_enabled = False
            omni.timeline.get_timeline_interface().stop()
            await self._apply_exp1_params()
            return web.Response(text=json.dumps({"status": "ok"}))
        return web.Response(status=500, text="Failed to load USD")

    # --- WebSocket handler --------------------------------------------------

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
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
            if not getattr(self, "_has_started", False):
                if self.current_experiment == "1":
                    await self._set_initial_angular_velocity()
                self._has_started = True
            self.simulation_control_enabled = True
            tl.play()

        elif mtype == "stop_simulation":
            self.simulation_control_enabled = False
            tl.stop()

        elif mtype == "reset":
            self.simulation_control_enabled = False
            self._has_started = False
            self._reset_exp2_state()
            tl.stop()
            tl.set_current_time(0.0)
            tl.stop()
            await asyncio.sleep(0.1)
            tl.stop()

        elif mtype == "enter_experiment":
            exp_id = data.get("experiment_id", "1")
            self.current_experiment = exp_id
            self._reset_exp2_state()
            await self._switch_camera(exp_id)
            if exp_id == "1":
                await self._apply_exp1_params()
            elif exp_id == "2":
                await self._apply_exp2_params()
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

        elif mtype == "set_initial_angle":
            self.exp2_initial_angle = float(data.get("value", 90.0))
            await self._apply_exp2_params()
        elif mtype == "set_exp2_mass1":
            self.exp2_mass1 = float(data.get("value", 1.0))
            await self._apply_exp2_params()
        elif mtype == "set_exp2_mass2":
            self.exp2_mass2 = float(data.get("value", 1.0))
            await self._apply_exp2_params()
        elif mtype == "set_exp2_offset1":
            self._store_param("3", "offset1", data)
        elif mtype == "set_exp2_offset2":
            self._store_param("3", "offset2", data)

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
            self.exp7_mass1 = float(data.get("value", 1.0))
            await self._apply_mass_at("/World/exp7/cart1", self.exp7_mass1)
        elif mtype == "set_mass2":
            self.exp7_mass2 = float(data.get("value", 1.0))
            await self._apply_mass_at("/World/exp7/cart2", self.exp7_mass2)
        elif mtype == "set_velocity1":
            self.exp7_velocity1 = float(data.get("value", 5.0))
        elif mtype == "set_elasticity":
            self.exp7_elasticity = float(data.get("value", 1.0))

        # Experiment 8 — resonance in air column
        elif mtype == "set_length":
            self.exp8_length = float(data.get("value", 50.0))

    # --- Helpers -----------------------------------------------------------

    def _reset_exp2_state(self):
        self.exp2_angle_history = []
        self.exp2_last_peak_time = None
        self.exp2_period = 0.0
        self.exp2_period_samples = []
        self.exp2_zero_cross_times = []
        self.exp2_last_angle_sign = None

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

    async def _switch_camera(self, experiment_id: str):
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            viewport = vp_util.get_active_viewport()
            camera_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            prim = stage.GetPrimAtPath(camera_path)
            if not prim or not prim.IsValid():
                return
            camera = UsdGeom.Camera(prim)
            xform = UsdGeom.Xformable(prim)

            xform.ClearXformOpOrder()
            translate_op = xform.AddTranslateOp()
            orient_op = xform.AddOrientOp()

            presets = {
                "1": (Gf.Vec3d(3.458, 4.154, 2.507), Gf.Quatd(0.808, 0.229, 0.148, 0.522)),
                "2": (Gf.Vec3d(1.170, 5.385, 2.553), Gf.Quatd(0.826, 0.014, 0.010, 0.563)),
                "3": (Gf.Vec3d(-0.560, 6.867, 3.155), Gf.Quatd(0.808, 0.229, 0.148, 0.522)),
                "4": (Gf.Vec3d(0.6, 0.6, 0.3),       Gf.Quatd(0.88, 0.12, 0.38, 0.25)),
                "5": (Gf.Vec3d(0.8, 0.8, 0.5),       Gf.Quatd(0.86, 0.14, 0.42, 0.22)),
                "6": (Gf.Vec3d(0.25, 0.35, 0.2),      Gf.Quatd(0.92, 0.08, 0.32, 0.18)),
                "7": (Gf.Vec3d(1.0, 1.0, 0.6),        Gf.Quatd(0.84, 0.16, 0.46, 0.24)),
                "8": (Gf.Vec3d(0.15, 0.20, 0.15),     Gf.Quatd(0.94, 0.06, 0.28, 0.16)),
            }
            if experiment_id in presets:
                pos, quat = presets[experiment_id]
                translate_op.Set(pos)
                orient_op.Set(quat)
            camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
            camera.GetFocalLengthAttr().Set(18.147)
        except Exception as exc:
            carb.log_error(f"Camera switch failed: {exc}")

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

    async def _apply_exp2_params(self):
        try:
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return
            tl = omni.timeline.get_timeline_interface()
            was_playing = tl.is_playing()
            if was_playing:
                tl.stop()
                await asyncio.sleep(0.1)
            grp = stage.GetPrimAtPath(EXP2_GROUP_PATH)
            if grp and grp.IsValid():
                xf = UsdGeom.Xformable(grp)
                xf.ClearXformOpOrder()
                xf.AddRotateYOp().Set(float(self.exp2_initial_angle))
            for path, mass in [(EXP2_MASS1_PATH, self.exp2_mass1), (EXP2_MASS2_PATH, self.exp2_mass2)]:
                prim = stage.GetPrimAtPath(path)
                if prim and prim.IsValid():
                    if not prim.HasAPI(UsdPhysics.MassAPI):
                        UsdPhysics.MassAPI.Apply(prim)
                    UsdPhysics.MassAPI(prim).GetMassAttr().Set(float(mass))
        except Exception as exc:
            carb.log_error(f"apply_exp2_params: {exc}")

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
        try:
            from omni.isaac.core.prims import RigidPrim
            from scipy.spatial.transform import Rotation as R
            rp = RigidPrim(EXP2_CYLINDER_PATH)
            _, orientation = rp.get_world_pose()
            if orientation is not None:
                q = [float(orientation[i]) for i in range(4)]
                euler = R.from_quat(q).as_euler("xyz", degrees=True)
                a = float(euler[1])
                while a > 180:
                    a -= 360
                while a < -180:
                    a += 360
                return a
        except Exception:
            pass
        return 0.0

    def _calculate_exp2_period(self, angle, t):
        sign = 1 if angle >= 0 else -1
        if self.exp2_last_angle_sign is not None and sign != self.exp2_last_angle_sign:
            cross_type = self.exp2_last_angle_sign
            self.exp2_zero_cross_times.append((t, cross_type))
            cutoff = t - 10.0
            self.exp2_zero_cross_times = [(tt, ct) for tt, ct in self.exp2_zero_cross_times if tt >= cutoff]
            same = [(tt, ct) for tt, ct in self.exp2_zero_cross_times if ct == cross_type]
            if len(same) >= 2:
                period = same[-1][0] - same[-2][0]
                if 0.3 < period < 10.0:
                    self.exp2_period_samples.append(period)
                    if len(self.exp2_period_samples) > 3:
                        self.exp2_period_samples.pop(0)
                    self.exp2_period = sum(self.exp2_period_samples) / len(self.exp2_period_samples)
        self.exp2_last_angle_sign = sign
        return self.exp2_period

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
        v1 = self._read_velocity("/World/exp7/cart1")
        v2 = self._read_velocity("/World/exp7/cart2")
        return round(self.exp7_mass1 * v1 + self.exp7_mass2 * v2, 2)

    def _read_total_ke(self) -> float:
        ke1 = self._read_kinetic_energy("/World/exp7/cart1", self.exp7_mass1)
        ke2 = self._read_kinetic_energy("/World/exp7/cart2", self.exp7_mass2)
        return round(ke1 + ke2, 2)

    # --- Telemetry loop ----------------------------------------------------

    async def _telemetry_loop(self):
        while True:
            try:
                tl = omni.timeline.get_timeline_interface()
                if self.ws_clients:
                    now = time.time()
                    if self.current_experiment == "1":
                        dv, rv = (0.0, 0.0) if not tl.is_playing() else self._get_angular_velocities()
                        am = round(self.exp1_disk_mass * dv + self.exp1_ring_mass * rv, 2)
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "disk_angular_velocity": round(dv, 2),
                            "ring_angular_velocity": round(rv, 2),
                            "angular_momentum": am,
                            "disk_mass": self.exp1_disk_mass,
                            "ring_mass": self.exp1_ring_mass,
                            "initial_velocity": round(self.exp1_initial_vel, 2),
                            "is_running": tl.is_playing(),
                        }}
                    elif self.current_experiment == "2":
                        angle = period = 0.0
                        if tl.is_playing():
                            angle = self._get_exp2_angle()
                            period = self._calculate_exp2_period(angle, now)
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "angle": round(angle, 2),
                            "period": round(period, 2),
                            "initial_angle": self.exp2_initial_angle,
                            "mass1": self.exp2_mass1,
                            "mass2": self.exp2_mass2,
                            "is_running": tl.is_playing(),
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
                        msg = {"type": "telemetry", "data": {
                            "timestamp": now,
                            "total_momentum": self._read_total_momentum(),
                            "kinetic_energy": self._read_total_ke(),
                            "is_running": tl.is_playing(),
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

    # --- Lifecycle ---------------------------------------------------------

    async def start(self):
        if not HAS_WEBRTC:
            carb.log_error("Cannot start — aiortc/aiohttp not installed")
            return

        app = web.Application()
        app.router.add_post("/offer", self.offer)
        app.router.add_post("/camera", self.camera_control)
        app.router.add_post("/load_usd", self.load_usd)

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
