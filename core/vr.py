"""VR bridge — connects Meta Quest hand tracking to the Isaac Sim WebRTC server.

This module sits between :class:`VRHandReceiver` (UDP data) and the WebRTC
server's USD scene.  It creates kinematic hand prims, updates their poses
each tick, and implements proximity-based grab/release logic.

Integration path:
  1. ``WebRTCServer`` instantiates ``VRBridge(enabled=True)``
  2. ``VRBridge.start()`` is called inside the server's ``start()``
  3. On every telemetry tick the server calls ``vr_bridge.tick(dt)``
  4. ``VRBridge.stop()`` is called on shutdown

The receiver runs in its own thread (see ``core/vr_hand_receiver.py``);
everything else happens on the main asyncio / Kit thread.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


class VRBridge:
    """Manages the VR hand tracking lifecycle and in-scene hand prims."""

    def __init__(
        self,
        enabled: bool = False,
        *,
        host: str = "0.0.0.0",
        port: int = 8888,
        timeout: float = 0.1,
        update_rate: float = 60.0,
        smoothing: bool = True,
        smoothing_alpha: float = 0.3,
        position_scale: float = 2.0,
        position_offset: Tuple[float, float, float] = (0.5, 0.0, 0.5),
        pinch_threshold: float = 0.6,
        grasp_distance: float = 0.15,
        release_delay: float = 0.1,
        hand_size: Tuple[float, float, float] = (0.08, 0.04, 0.12),
        left_hand_path: str = "/World/vr/left_hand",
        right_hand_path: str = "/World/vr/right_hand",
    ):
        self.enabled = enabled
        self._host = host
        self._port = port
        self._timeout = timeout
        self._update_rate = update_rate
        self._smoothing = smoothing
        self._smoothing_alpha = smoothing_alpha

        self.scale = position_scale
        self.offset = np.array(position_offset, dtype=np.float64)
        self.pinch_threshold = pinch_threshold
        self.grasp_distance = grasp_distance
        self.release_delay = release_delay
        self.hand_size = hand_size
        self.left_hand_path = left_hand_path
        self.right_hand_path = right_hand_path

        self._receiver = None  # VRHandReceiver (lazy import avoids startup cost)
        self._callbacks: Dict[str, List[Callable]] = {}

        # Grasp state
        self._left_grasped_path: Optional[str] = None
        self._right_grasped_path: Optional[str] = None
        self._left_grasp_offset = np.zeros(3)
        self._right_grasp_offset = np.zeros(3)
        self._left_release_elapsed = 0.0
        self._right_release_elapsed = 0.0

        self._hands_created = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the UDP receiver thread."""
        if not self.enabled:
            return
        from core.vr_hand_receiver import VRHandReceiver
        self._receiver = VRHandReceiver(
            host=self._host,
            port=self._port,
            timeout=self._timeout,
            update_rate=self._update_rate,
            smoothing=self._smoothing,
            smoothing_alpha=self._smoothing_alpha,
        )
        self._receiver.start()
        log.info("VR bridge started (UDP %s:%d)", self._host, self._port)

    def stop(self) -> None:
        """Stop the UDP receiver."""
        if self._receiver:
            self._receiver.stop()
            self._receiver = None

    @property
    def any_tracking(self) -> bool:
        if not self._receiver:
            return False
        return self._receiver.any_tracking

    @property
    def packets_received(self) -> int:
        return self._receiver.packets_received if self._receiver else 0

    # -- event system (same API as old stub) --------------------------------

    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._callbacks.setdefault(event_name, []).append(callback)

    def emit(self, event_name: str, **kwargs: Any) -> None:
        for cb in self._callbacks.get(event_name, []):
            try:
                cb(**kwargs)
            except Exception:
                log.exception("VR event callback error: %s", event_name)

    # -- scene primitives --------------------------------------------------

    def ensure_hand_prims(self) -> None:
        """Create the kinematic hand cuboids in the current USD stage if
        they don't already exist."""
        if self._hands_created or not self.enabled:
            return
        try:
            self._create_hand_prim(self.left_hand_path, color=(0.2, 0.6, 0.8))
            self._create_hand_prim(self.right_hand_path, color=(0.8, 0.6, 0.2))
            self._hands_created = True
            log.info("VR hand prims created")
        except Exception:
            log.exception("Failed to create VR hand prims")

    @staticmethod
    def _create_hand_prim(prim_path: str, color: Tuple[float, ...]) -> None:
        """Create a kinematic VisualCuboid at *prim_path*.

        We deliberately use a **VisualCuboid** (no collision / no rigid body)
        so that the VR hands do not generate phantom physics forces on
        experiment apparatus.  Grab logic is purely proximity-based.
        """
        import omni.usd
        from pxr import Gf, Sdf, UsdGeom, UsdShade

        stage = omni.usd.get_context().get_stage()
        if stage.GetPrimAtPath(prim_path).IsValid():
            return

        parent = Sdf.Path(prim_path).GetParentPath()
        if not stage.GetPrimAtPath(parent).IsValid():
            UsdGeom.Xform.Define(stage, parent)

        cube = UsdGeom.Cube.Define(stage, prim_path)
        cube.GetSizeAttr().Set(1.0)
        cube.AddScaleOp().Set(Gf.Vec3f(0.08, 0.04, 0.12))
        cube.AddTranslateOp().Set(Gf.Vec3d(0, 0, -5))  # off-screen initially

        mat_path = prim_path + "/material"
        mat = UsdShade.Material.Define(stage, mat_path)
        shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.7)
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI(cube.GetPrim()).Bind(mat)

    # -- per-tick update ---------------------------------------------------

    def tick(self, dt: float, graspable_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Advance VR state by one tick.  Returns a dict of VR telemetry."""
        if not self.enabled or not self._receiver:
            return {"vr_connected": False}

        from core.vr_hand_receiver import HandSnapshot
        left, right = self._receiver.get_snapshots()

        result: Dict[str, Any] = {
            "vr_connected": left.is_tracking or right.is_tracking,
            "vr_packets": self._receiver.packets_received,
        }

        if left.is_tracking:
            pos = self._transform(left.position)
            self._set_prim_translate(self.left_hand_path, pos)
            result["vr_left_pos"] = [round(float(v), 4) for v in pos]
            result["vr_left_pinch"] = round(left.pinch_strength, 3)
            if graspable_paths:
                self._handle_grasp("left", pos, left, graspable_paths, dt)
        else:
            self._set_prim_translate(self.left_hand_path, (0, 0, -5))

        if right.is_tracking:
            pos = self._transform(right.position)
            self._set_prim_translate(self.right_hand_path, pos)
            result["vr_right_pos"] = [round(float(v), 4) for v in pos]
            result["vr_right_pinch"] = round(right.pinch_strength, 3)
            if graspable_paths:
                self._handle_grasp("right", pos, right, graspable_paths, dt)
        else:
            self._set_prim_translate(self.right_hand_path, (0, 0, -5))

        if self._left_grasped_path:
            result["vr_left_grasped"] = self._left_grasped_path
        if self._right_grasped_path:
            result["vr_right_grasped"] = self._right_grasped_path

        return result

    def _transform(self, raw_pos: np.ndarray) -> np.ndarray:
        return raw_pos * self.scale + self.offset

    @staticmethod
    def _set_prim_translate(prim_path: str, pos) -> None:
        import omni.usd
        from pxr import Gf, UsdGeom
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return
        xformable = UsdGeom.Xformable(prim)
        for op in xformable.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                op.Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
                return

    @staticmethod
    def _get_prim_pos(prim_path: str) -> Optional[np.ndarray]:
        import omni.usd
        from pxr import UsdGeom
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return None
        xformable = UsdGeom.Xformable(prim)
        world = xformable.ComputeLocalToWorldTransform(0)
        t = world.ExtractTranslation()
        return np.array([t[0], t[1], t[2]], dtype=np.float64)

    # -- grab / release logic ----------------------------------------------

    def _handle_grasp(
        self,
        side: str,
        hand_pos: np.ndarray,
        snap,
        graspable_paths: List[str],
        dt: float,
    ) -> None:
        is_pinching = snap.pinch_strength > self.pinch_threshold

        grasped = self._left_grasped_path if side == "left" else self._right_grasped_path
        offset = self._left_grasp_offset if side == "left" else self._right_grasp_offset
        release_t = self._left_release_elapsed if side == "left" else self._right_release_elapsed

        if is_pinching:
            release_t = 0.0
        elif grasped is not None:
            release_t += dt

        if is_pinching and grasped is None:
            other_grasped = self._right_grasped_path if side == "left" else self._left_grasped_path
            closest_path = None
            min_dist = self.grasp_distance
            for p in graspable_paths:
                if p == other_grasped:
                    continue
                obj_pos = self._get_prim_pos(p)
                if obj_pos is None:
                    continue
                d = float(np.linalg.norm(hand_pos - obj_pos))
                if d < min_dist:
                    min_dist = d
                    closest_path = p
            if closest_path is not None:
                obj_pos = self._get_prim_pos(closest_path)
                offset = obj_pos - hand_pos if obj_pos is not None else np.zeros(3)
                if side == "left":
                    self._left_grasped_path = closest_path
                    self._left_grasp_offset = offset
                else:
                    self._right_grasped_path = closest_path
                    self._right_grasp_offset = offset
                release_t = 0.0
                self.emit("grasp", side=side, prim_path=closest_path)
                log.info("VR %s hand grasped %s", side, closest_path)

        elif grasped is not None and not is_pinching and release_t >= self.release_delay:
            released = grasped
            if side == "left":
                self._left_grasped_path = None
                self._left_grasp_offset = np.zeros(3)
            else:
                self._right_grasped_path = None
                self._right_grasp_offset = np.zeros(3)
            release_t = 0.0
            self.emit("release", side=side, prim_path=released)
            log.info("VR %s hand released %s", side, released)

        elif grasped is not None:
            target = hand_pos + offset
            self._set_prim_translate(grasped, target)

        if side == "left":
            self._left_release_elapsed = release_t
        else:
            self._right_release_elapsed = release_t

    # -- cleanup -----------------------------------------------------------

    def remove_hand_prims(self) -> None:
        """Delete VR hand prims from the stage."""
        if not self._hands_created:
            return
        try:
            import omni.usd
            stage = omni.usd.get_context().get_stage()
            for path in (self.left_hand_path, self.right_hand_path):
                prim = stage.GetPrimAtPath(path)
                if prim.IsValid():
                    stage.RemovePrim(path)
            parent = "/World/vr"
            if stage.GetPrimAtPath(parent).IsValid():
                stage.RemovePrim(parent)
            self._hands_created = False
        except Exception:
            log.exception("Failed to remove VR hand prims")
