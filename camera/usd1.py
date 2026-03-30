"""
Camera preset for Experiment 1 — Conservation of Angular Momentum.

Sets a 45-degree isometric overhead view looking DOWN at the turntable.
Uses the Isaac Sim Viewport API (set_camera_view) as the primary method.
"""
import math
import omni.usd
from pxr import UsdGeom, Gf
import omni.kit.viewport.utility as vp_util


def _find_exp1_center():
    """Locate the turntable center in the scene."""
    try:
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return [0.0, 0.0, 0.0]
        for path in ["/World/exp1/disk", "/World/exp1/ring",
                     "/World/exp1", "/World/exp1/bracket1"]:
            prim = stage.GetPrimAtPath(path)
            if prim and prim.IsValid():
                try:
                    xf = UsdGeom.Xformable(prim)
                    t = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                    return [float(t[0]), float(t[1]), float(t[2])]
                except Exception:
                    pass
    except Exception:
        pass
    return [0.0, 0.0, 0.0]


def _build_lookat_matrix(eye, target):
    """Build a 4x4 lookAt matrix for a USD camera."""
    e = Gf.Vec3d(*eye)
    t = Gf.Vec3d(*target)
    backward = (e - t).GetNormalized()
    world_up = Gf.Vec3d(0, 0, 1)
    right = (world_up ^ backward).GetNormalized()
    cam_up = (backward ^ right).GetNormalized()
    m = Gf.Matrix4d(1)
    m[0, 0], m[0, 1], m[0, 2] = right[0], right[1], right[2]
    m[1, 0], m[1, 1], m[1, 2] = cam_up[0], cam_up[1], cam_up[2]
    m[2, 0], m[2, 1], m[2, 2] = backward[0], backward[1], backward[2]
    m[3, 0], m[3, 1], m[3, 2] = e[0], e[1], e[2]
    return m


def set_my_camera():
    center = _find_exp1_center()
    dist = 0.8
    eye = [center[0] + dist * 0.70,
           center[1] - dist * 0.70,
           center[2] + dist]
    target = [center[0], center[1], center[2] + 0.03]

    # Strategy 1: Isaac Sim Viewport API
    api_ok = False
    for mod_path in ["omni.isaac.core.utils.viewports",
                     "isaacsim.core.utils.viewports"]:
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            mod.set_camera_view(eye=eye, target=target)
            api_ok = True
            print(f"Exp1 camera set via {mod_path}: eye={eye}")
            break
        except (ImportError, AttributeError, Exception):
            continue

    # Strategy 2: direct USD xform ops
    if not api_ok:
        try:
            stage = omni.usd.get_context().get_stage()
            viewport = vp_util.get_active_viewport()
            camera_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
            cam_prim = stage.GetPrimAtPath(camera_path)
            if cam_prim and cam_prim.IsValid():
                mtx = _build_lookat_matrix(eye, target)
                xform = UsdGeom.Xformable(cam_prim)
                xform.ClearXformOpOrder()
                xform.AddTransformOp().Set(mtx)
                print(f"Exp1 camera set via USD xform: eye={eye}")
        except Exception as exc:
            print(f"Camera fallback failed: {exc}")

    # Set focal length and clipping on the camera prim
    try:
        stage = omni.usd.get_context().get_stage()
        viewport = vp_util.get_active_viewport()
        camera_path = viewport.get_active_camera() if viewport else "/OmniverseKit_Persp"
        cam_prim = stage.GetPrimAtPath(camera_path)
        if cam_prim and cam_prim.IsValid():
            camera = UsdGeom.Camera(cam_prim)
            camera.GetFocalLengthAttr().Set(18.0)
            camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000000.0))
    except Exception:
        pass

    print(f"Exp1 camera: 45-deg isometric overhead, center={center}")


set_my_camera()
