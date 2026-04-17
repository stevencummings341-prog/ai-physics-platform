"""Isaac Sim camera preset — Experiment 3 (Ballistic Pendulum).

Matches the procedural scene built by core/webrtc_server.py
(_setup_exp3_scene). The pendulum swings in the XZ plane (y≈0), the stand
is offset to +Y, and the launcher sits on −X. Camera is placed on the
−X −Y side at modest elevation to see both the barrel and the swing arc.
"""

import omni.usd
from pxr import UsdGeom, Gf


def _build_lookat(eye: Gf.Vec3d, target: Gf.Vec3d,
                  up: Gf.Vec3d = Gf.Vec3d(0, 0, 1)) -> Gf.Matrix4d:
    backward = (eye - target).GetNormalized()
    right = (up ^ backward).GetNormalized()
    cam_up = (backward ^ right).GetNormalized()
    m = Gf.Matrix4d(1)
    m[0, 0], m[0, 1], m[0, 2] = right[0], right[1], right[2]
    m[1, 0], m[1, 1], m[1, 2] = cam_up[0], cam_up[1], cam_up[2]
    m[2, 0], m[2, 1], m[2, 2] = backward[0], backward[1], backward[2]
    m[3, 0], m[3, 1], m[3, 2] = eye[0], eye[1], eye[2]
    return m


def set_camera():
    stage = omni.usd.get_context().get_stage()
    cam_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
    if not cam_prim or not cam_prim.IsValid():
        print("exp3 camera: /OmniverseKit_Persp not found")
        return

    eye = Gf.Vec3d(-0.75, -1.35, 0.70)
    target = Gf.Vec3d(0.0, 0.0, 0.55)

    camera = UsdGeom.Camera(cam_prim)
    xform = UsdGeom.Xformable(cam_prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(_build_lookat(eye, target))
    camera.GetFocalLengthAttr().Set(22.0)
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10_000_000.0))

    print(f"exp3 camera applied  eye={eye}  target={target}")


set_camera()
