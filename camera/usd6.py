"""Isaac Sim camera preset for Experiment 6 — Centripetal Force.

Matches the procedural PhysX scene built by `core/webrtc_server.py`:
a rotor carrying a horizontal arm, with a red bob orbiting around it.
The camera looks diagonally down onto the rotating apparatus so the
orbital motion of the bob and the green spring rod are both clearly
visible.
"""

import omni.usd
from pxr import UsdGeom, Gf


def set_camera():
    stage = omni.usd.get_context().get_stage()
    camera_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")

    if not camera_prim.IsValid():
        print("[exp6] perspective camera not found!")
        return

    camera = UsdGeom.Camera(camera_prim)
    xform = UsdGeom.Xformable(camera_prim)
    xform.ClearXformOpOrder()

    eye = Gf.Vec3d(0.95, -0.95, 1.40)
    target = Gf.Vec3d(0.0, 0.0, 0.75)
    up = Gf.Vec3d(0, 0, 1)

    backward = (eye - target).GetNormalized()
    right = (up ^ backward).GetNormalized()
    cam_up = (backward ^ right).GetNormalized()

    m = Gf.Matrix4d(1)
    m[0, 0], m[0, 1], m[0, 2] = right[0], right[1], right[2]
    m[1, 0], m[1, 1], m[1, 2] = cam_up[0], cam_up[1], cam_up[2]
    m[2, 0], m[2, 1], m[2, 2] = backward[0], backward[1], backward[2]
    m[3, 0], m[3, 1], m[3, 2] = eye[0], eye[1], eye[2]
    xform.AddTransformOp().Set(m)

    camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100000.0))
    camera.GetFocalLengthAttr().Set(22.0)

    print("[exp6] camera set for centripetal-force rig")


set_camera()
