"""
Isaac Sim camera preset — Experiment 8: Resonance Air Column.

Looks slightly down the tube from the -Y side so the full length of the
120 cm PASCO resonance tube, speaker, and piston are all visible.  The
camera matches the runtime preset used by WebRTCServer._switch_camera.
"""

import omni.usd
from pxr import UsdGeom, Gf


def set_camera():
    stage = omni.usd.get_context().get_stage()
    camera_prim = stage.GetPrimAtPath("/OmniverseKit_Persp")

    if not camera_prim.IsValid():
        print("Camera not found!")
        return

    camera = UsdGeom.Camera(camera_prim)
    xform = UsdGeom.Xformable(camera_prim)
    xform.ClearXformOpOrder()

    # Eye & target — consistent with webrtc_server's _EXP8_CAM_*.
    eye = Gf.Vec3d(0.60, -1.40, 0.78)
    target = Gf.Vec3d(0.60, 0.0, 0.40)
    up = Gf.Vec3d(0.0, 0.0, 1.0)

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
    camera.GetFocalLengthAttr().Set(16.0)

    print("Camera set — experiment 8 (resonance air column).")


set_camera()
