"""
Isaac Sim 相机设置脚本 - 实验2 (Large Amplitude Pendulum)
"""

import omni.usd
from pxr import UsdGeom, Gf
import omni.kit.viewport.utility as vp_util

def set_camera():
    stage = omni.usd.get_context().get_stage()

    # 自动获取当前活动的相机路径
    try:
        viewport = vp_util.get_active_viewport()
        if viewport:
            camera_path = viewport.get_active_camera()
            if camera_path:
                print(f" 使用活动相机: {camera_path}")
            else:
                camera_path = "/OmniverseKit_Persp"
                print(f"⚠️ 无法获取活动相机路径，使用默认: {camera_path}")
        else:
            camera_path = "/OmniverseKit_Persp"
            print(f"⚠️ 无法获取viewport，使用默认相机: {camera_path}")
    except Exception as e:
        camera_path = "/OmniverseKit_Persp"
        print(f"⚠️ 获取相机时出错: {e}，使用默认: {camera_path}")

    camera_prim = stage.GetPrimAtPath(camera_path)

    if not camera_prim.IsValid():
        print(f"❌ 相机未找到: {camera_path}")
        return

    camera = UsdGeom.Camera(camera_prim)
    xform = UsdGeom.Xformable(camera_prim)

    # 获取现有的 xformOp，如果不存在则创建
    xform_ops = xform.GetOrderedXformOps()
    translate_op = None
    orient_op = None

    for op in xform_ops:
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
        elif op.GetOpType() == UsdGeom.XformOp.TypeOrient:
            orient_op = op

    # 如果操作不存在，则创建
    if not translate_op:
        translate_op = xform.AddTranslateOp()
    if not orient_op:
        orient_op = xform.AddOrientOp()

    # 设置位置
    translate_op.Set(Gf.Vec3d(1.169913776980235, 5.384567671926622, 2.5526077469676727))

    # 设置旋转（四元数 w, x, y, z）
    orient_op.Set(Gf.Quatd(0.014359612064957861, 0.009788101829553237, 0.5631514231667778, 0.8261709684981379))

    # 设置裁剪范围（近裁剪面, 远裁剪面）
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.009999999776482582, 10000000.0))

    # 设置焦距
    camera.GetFocalLengthAttr().Set(18.14756202697754)

    print("✅ 实验2相机设置已应用!")
    print(f"   相机路径: {camera_path}")
    print(f"   位置: (1.170, 5.385, 2.553)")
    print(f"   旋转(四元数): (0.014, 0.010, 0.563, 0.826)")
    print(f"   焦距: 18.15mm")

# 运行设置
set_camera()
