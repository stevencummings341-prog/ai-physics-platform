"""Experiment 1 — Conservation of Angular Momentum.

Loads the teammate-provided apparatus model (Experiment/exp1/exp1.usd)
as visual geometry.  Hidden DynamicCuboid proxy bodies drive the physics
simulation, and their poses are synced to the model's disk and ring
prims every frame.  Colored rotation markers on the disk guarantee
visible spinning even if visual sync encounters edge cases.

If the model file is missing, the experiment falls back to procedural
geometry built entirely from Isaac Sim primitives.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from isaacsim import SimulationApp

log = logging.getLogger(__name__)

_app: SimulationApp | None = None


def _get_app(cfg: dict) -> SimulationApp:
    global _app
    if _app is None:
        _app = SimulationApp({"headless": cfg.get("headless", False)})
    return _app


from core.experiment_base import ExperimentBase
from core.reporter import ReportGenerator

_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.yaml")

MODEL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "Experiment", "exp1")
)
MODEL_USD = os.path.join(MODEL_DIR, "exp1.usd")


def I_solid_disk(mass: float, radius: float) -> float:
    return 0.5 * mass * radius ** 2


def I_ring(mass: float, r_inner: float, r_outer: float, offset: float = 0.0) -> float:
    return 0.5 * mass * (r_inner ** 2 + r_outer ** 2) + mass * offset ** 2


class Experiment(ExperimentBase):
    """Drop a ring (or disk) onto a spinning disk — with teammate 3D model."""

    name = "expt1_angular_momentum"

    def __init__(self, config_path: str | None = None, overrides: dict | None = None):
        if config_path is None:
            config_path = _DEFAULT_CONFIG
        self.app = _get_app(overrides or {})
        super().__init__(config_path, overrides)

        self.disk = None
        self.drop_body = None
        self.visual_disk = None
        self.visual_ring = None
        self._markers: list = []
        self._marker_offsets: list[np.ndarray] = []

        self._I_disk = 0.0
        self._I_pulley = 0.0
        self._I_drop = 0.0
        self._I_initial = 0.0
        self._I_final = 0.0

        self._ring_hold_pos: np.ndarray | None = None
        self._ring_hold_rot: np.ndarray | None = None
        self._disk_center_z = 0.0
        self._disk_height = 0.01

    # ================================================================ scene
    def build_scene(self) -> None:
        import omni
        from isaacsim.core.api import World
        from isaacsim.core.api.materials import PhysicsMaterial
        from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid, VisualCuboid
        from pxr import UsdPhysics, UsdGeom, Gf, UsdLux, Usd

        cfg = self.cfg
        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=cfg.get("physics_dt", 1 / 240),
            rendering_dt=cfg.get("render_dt", 1 / 60),
        )
        self.world.scene.clear()
        self.world.get_physics_context().set_gravity(-9.81)

        stage = omni.usd.get_context().get_stage()
        UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1500.0)

        self.world.scene.add(FixedCuboid(
            prim_path="/World/Ground", name="ground",
            position=np.array([0.0, 0.0, -0.01]),
            scale=np.array([2.0, 2.0, 0.02]),
            color=np.array([0.12, 0.12, 0.15]),
        ))

        contact_mat = PhysicsMaterial(
            prim_path="/World/Materials/ContactMat",
            static_friction=cfg.get("contact_static_friction", 0.8),
            dynamic_friction=cfg.get("contact_dynamic_friction", 0.6),
            restitution=0.0,
        )

        disk_r = float(cfg.get("disk_radius", 0.125))
        disk_h = float(cfg.get("disk_height", 0.01))
        self._disk_height = disk_h
        disk_side = 2.0 * disk_r

        # ---- try loading teammate model ----
        model_path = cfg.get("model_usd", MODEL_USD)
        has_model = os.path.isfile(model_path)
        disk_prim = None
        ring_prim = None

        if has_model:
            apparatus_prim = stage.DefinePrim("/World/Apparatus", "Xform")
            apparatus_prim.GetReferences().AddReference(model_path)
            log.info("Loaded teammate model from %s", model_path)

            model_scale = float(cfg.get("model_scale", 1.0))
            if model_scale != 1.0:
                xform = UsdGeom.Xformable(apparatus_prim)
                xform.AddScaleOp().Set(Gf.Vec3f(model_scale, model_scale, model_scale))

            disk_prim, ring_prim = self._discover_visual_prims(stage)
            self._strip_embedded_physics(stage, apparatus_prim)
        else:
            log.warning("Model not found at %s — using procedural fallback", model_path)

        # ---- determine proxy positions ----
        support_h = float(cfg.get("support_height", 0.15))
        drop_height = float(cfg.get("drop_height", 0.003))
        drop_type = str(cfg.get("drop_object", "ring"))
        ring_offset_x = float(cfg.get("ring_offset_x", 0.005))

        if drop_type == "ring":
            ring_r_out = float(cfg.get("ring_r_outer", 0.064))
            ring_h = float(cfg.get("ring_height", 0.02))
            ring_side = 2.0 * ring_r_out
            ring_mass_val = float(cfg.get("ring_mass", 0.470))
        else:
            ring_r_out = float(cfg.get("disk2_radius", 0.125))
            ring_h = float(cfg.get("disk2_height", 0.01))
            ring_side = 2.0 * ring_r_out
            ring_mass_val = float(cfg.get("disk2_mass", 0.120))

        if has_model and disk_prim is not None:
            disk_pos, disk_rot = self._get_world_pose(stage, disk_prim)
            ring_pos, ring_rot = self._get_world_pose(stage, ring_prim)

            if abs(disk_pos[2]) < 0.001 and abs(ring_pos[2]) < 0.001:
                log.info("Model prims at origin — computing positions from config")
                disk_pos = np.array([0.0, 0.0, support_h + disk_h / 2])
                ring_pos = np.array([ring_offset_x, 0.0,
                                     support_h + disk_h + ring_h / 2 + drop_height])
        else:
            disk_pos = np.array([0.0, 0.0, support_h + disk_h / 2])
            ring_pos = np.array([ring_offset_x, 0.0,
                                 support_h + disk_h + ring_h / 2 + drop_height])

            self.world.scene.add(FixedCuboid(
                prim_path="/World/Support", name="support",
                position=np.array([0.0, 0.0, support_h / 2]),
                scale=np.array([0.03, 0.03, support_h]),
                color=np.array([0.4, 0.4, 0.45]),
            ))

        self._disk_center_z = float(disk_pos[2])
        self._ring_hold_pos = np.array(ring_pos, dtype=float).copy()
        self._ring_hold_rot = np.array([0.0, 0.0, 0.0, 1.0])
        log.info("Proxy positions: disk=%s  ring=%s", disk_pos, ring_pos)

        # ---- physics proxy bodies ----
        self.world.scene.add(DynamicCuboid(
            prim_path="/World/SimDiskProxy", name="sim_disk_proxy",
            position=np.array(disk_pos, dtype=float),
            scale=np.array([disk_side, disk_side, disk_h]),
            color=np.array([0.8, 0.1, 0.1]),
            mass=float(cfg.get("disk_mass", 0.120)),
            physics_material=contact_mat,
        ))
        self.world.scene.add(DynamicCuboid(
            prim_path="/World/SimRingProxy", name="sim_ring_proxy",
            position=np.array(ring_pos, dtype=float),
            scale=np.array([ring_side, ring_side, ring_h]),
            color=np.array([0.1, 0.8, 0.1]),
            mass=ring_mass_val,
            physics_material=contact_mat,
        ))

        if has_model:
            UsdGeom.Imageable(stage.GetPrimAtPath("/World/SimDiskProxy")).MakeInvisible()
            UsdGeom.Imageable(stage.GetPrimAtPath("/World/SimRingProxy")).MakeInvisible()

        # ---- revolute joint ----
        axle = UsdPhysics.RevoluteJoint.Define(stage, "/World/SimDiskAxle")
        axle.CreateAxisAttr("Z")
        axle.CreateBody1Rel().SetTargets(["/World/SimDiskProxy"])
        axle.CreateLocalPos0Attr(Gf.Vec3f(
            float(disk_pos[0]), float(disk_pos[1]), float(disk_pos[2])))
        axle.CreateLocalPos1Attr(Gf.Vec3f(0, 0, 0))

        # ---- override inertia ----
        disk_Iz = I_solid_disk(float(cfg.get("disk_mass", 0.120)), disk_r)
        disk_Ixy = disk_Iz / 2
        mass_api_d = UsdPhysics.MassAPI.Apply(stage.GetPrimAtPath("/World/SimDiskProxy"))
        mass_api_d.CreateMassAttr(float(cfg.get("disk_mass", 0.120)))
        mass_api_d.CreateDiagonalInertiaAttr(
            Gf.Vec3f(float(disk_Ixy), float(disk_Ixy), float(disk_Iz)))

        if drop_type == "ring":
            ring_Iz = I_ring(
                float(cfg.get("ring_mass", 0.470)),
                float(cfg.get("ring_r_inner", 0.054)),
                float(cfg.get("ring_r_outer", 0.064)),
                float(cfg.get("ring_offset_x", 0.0)),
            )
        else:
            ring_Iz = I_solid_disk(
                float(cfg.get("disk2_mass", 0.120)),
                float(cfg.get("disk2_radius", 0.125)))
        ring_Ixy = ring_Iz / 2
        mass_api_r = UsdPhysics.MassAPI.Apply(stage.GetPrimAtPath("/World/SimRingProxy"))
        mass_api_r.CreateMassAttr(ring_mass_val)
        mass_api_r.CreateDiagonalInertiaAttr(
            Gf.Vec3f(float(ring_Ixy), float(ring_Ixy), float(ring_Iz)))

        # ---- wrappers ----
        try:
            from isaacsim.core.prims import RigidPrim, XFormPrim
        except ImportError:
            from omni.isaac.core.prims import RigidPrim, XFormPrim

        self.disk = self.world.scene.add(
            RigidPrim(prim_path="/World/SimDiskProxy", name="sim_disk_rigid"))
        self.drop_body = self.world.scene.add(
            RigidPrim(prim_path="/World/SimRingProxy", name="sim_ring_rigid"))

        if has_model and disk_prim is not None:
            self.visual_disk = self.world.scene.add(
                XFormPrim(prim_path=str(disk_prim.GetPath()), name="visual_disk"))
        if has_model and ring_prim is not None:
            self.visual_ring = self.world.scene.add(
                XFormPrim(prim_path=str(ring_prim.GetPath()), name="visual_ring"))

        # ---- rotation markers (always visible) ----
        marker_colors = [np.array([0.9, 0.1, 0.1]), np.array([0.1, 0.1, 0.9])]
        marker_r = disk_r * 0.6
        self._markers = []
        self._marker_offsets = []
        for i, mc in enumerate(marker_colors):
            angle = i * np.pi
            offset = np.array([marker_r * np.cos(angle), marker_r * np.sin(angle)])
            self._marker_offsets.append(offset)
            m = self.world.scene.add(VisualCuboid(
                prim_path=f"/World/RotMarker{i}", name=f"rot_marker_{i}",
                position=np.array([
                    float(disk_pos[0]) + offset[0],
                    float(disk_pos[1]) + offset[1],
                    self._disk_center_z + disk_h / 2 + 0.002,
                ]),
                scale=np.array([0.02, 0.02, 0.004]),
                color=mc,
            ))
            self._markers.append(m)

        # ---- camera ----
        from core.scene import set_camera
        set_camera(
            eye=np.array([0.4, -0.4, self._disk_center_z + 0.3]),
            target=np.array([0.0, 0.0, self._disk_center_z]),
        )
        log.info("Scene built successfully (model=%s)", has_model)

    # ======================================================= prim discovery
    def _discover_visual_prims(self, stage):
        from pxr import Usd

        root = stage.GetPrimAtPath("/World/Apparatus")
        if not root.IsValid():
            raise RuntimeError("/World/Apparatus not found after loading USD")

        all_prims = []
        for prim in Usd.PrimRange(root):
            name = prim.GetName()
            ptype = prim.GetTypeName()
            path = str(prim.GetPath())
            all_prims.append((name, ptype, path))

        log.info("Model hierarchy (%d prims):", len(all_prims))
        for name, ptype, path in all_prims:
            log.info("  %-25s type=%-12s %s", name, ptype, path)

        disk_prim = None
        ring_prim = None

        for name, ptype, path in all_prims:
            nl = name.lower()
            if disk_prim is None and nl == "disk":
                disk_prim = stage.GetPrimAtPath(path)
            if ring_prim is None and nl in ("ring", "1_ring", "__ring"):
                ring_prim = stage.GetPrimAtPath(path)

        if disk_prim is None:
            for name, _, path in all_prims:
                if "disk" in name.lower():
                    disk_prim = stage.GetPrimAtPath(path)
                    break
        if ring_prim is None:
            for name, _, path in all_prims:
                if "ring" in name.lower():
                    ring_prim = stage.GetPrimAtPath(path)
                    break

        if disk_prim is None or ring_prim is None:
            raise RuntimeError(
                f"Could not find disk/ring in model hierarchy. "
                f"disk={disk_prim}, ring={ring_prim}. "
                f"See log output above for available prims."
            )

        log.info("Selected visual prims: disk=%s  ring=%s",
                 disk_prim.GetPath(), ring_prim.GetPath())
        return disk_prim, ring_prim

    @staticmethod
    def _strip_embedded_physics(stage, root_prim):
        from pxr import Usd, UsdPhysics

        disabled_joints = 0
        disabled_rigid = 0
        for prim in Usd.PrimRange(root_prim):
            if prim.IsA(UsdPhysics.Joint):
                prim.SetActive(False)
                disabled_joints += 1
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rb = UsdPhysics.RigidBodyAPI(prim)
                rb.CreateRigidBodyEnabledAttr(False)
                disabled_rigid += 1
        log.info("Stripped embedded physics: joints=%d rigid_bodies=%d",
                 disabled_joints, disabled_rigid)

    @staticmethod
    def _get_world_pose(stage, prim):
        from pxr import UsdGeom, Usd

        xf = UsdGeom.Xformable(prim)
        tf = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        t = tf.ExtractTranslation()
        return (
            np.array([float(t[0]), float(t[1]), float(t[2])]),
            np.array([0.0, 0.0, 0.0, 1.0]),
        )

    # ======================================================= visual sync
    def _sync_visuals(self) -> None:
        if self.disk is None:
            return

        dp, dq = self.disk.get_world_pose()
        dp = np.array(dp, dtype=float)
        dq = np.array(dq, dtype=float)

        if self.visual_disk is not None:
            try:
                self.visual_disk.set_world_pose(dp, dq)
            except Exception:
                pass

        angle = 2.0 * np.arctan2(float(dq[2]), float(dq[3]))
        ca, sa = np.cos(angle), np.sin(angle)
        for marker, offset in zip(self._markers, self._marker_offsets):
            rx = ca * offset[0] - sa * offset[1]
            ry = sa * offset[0] + ca * offset[1]
            marker.set_world_pose(
                np.array([dp[0] + rx, dp[1] + ry,
                          dp[2] + self._disk_height / 2 + 0.002]),
                dq,
            )

        if self.drop_body is not None and self.visual_ring is not None:
            rp, rq = self.drop_body.get_world_pose()
            try:
                self.visual_ring.set_world_pose(
                    np.array(rp, dtype=float), np.array(rq, dtype=float))
            except Exception:
                pass

    # ======================================================= lifecycle
    def warmup(self) -> None:
        dt = self.cfg.get("physics_dt", 1.0 / 240.0)
        warmup_s = self.cfg.get("warmup_seconds", 0.5)
        steps = int(warmup_s / dt)
        log.info("Warmup: %d steps (%.2f s) — ring held in place", steps, warmup_s)
        for _ in range(steps):
            self.world.step(render=True)
            if self.drop_body is not None and self._ring_hold_pos is not None:
                self.drop_body.set_world_pose(
                    self._ring_hold_pos, self._ring_hold_rot)
                self.drop_body.set_linear_velocity(np.zeros(3))
                self.drop_body.set_angular_velocity(np.zeros(3))
            self._sync_visuals()

    def apply_initial_conditions(self) -> None:
        omega = float(self.cfg.get("omega_init", 25.0))
        self.disk.set_angular_velocity(np.array([0.0, 0.0, omega]))

        if self._ring_hold_pos is not None:
            self.drop_body.set_world_pose(self._ring_hold_pos, self._ring_hold_rot)
        self.drop_body.set_linear_velocity(np.zeros(3))
        self.drop_body.set_angular_velocity(np.zeros(3))
        self._sync_visuals()

        actual = self.disk.get_angular_velocity()
        log.info("Initial conditions: disk omega_z=%.2f (requested %.2f), "
                 "ring at z=%.4f",
                 float(actual[2]), omega, float(self._ring_hold_pos[2]))

    # ======================================================= prepare run
    def prepare_run(self) -> None:
        cfg = self.cfg
        drop_type = str(cfg.get("drop_object", "ring"))

        self._I_disk = I_solid_disk(cfg["disk_mass"], cfg["disk_radius"])
        self._I_pulley = I_solid_disk(
            cfg.get("pulley_mass", 0.0), cfg.get("pulley_radius", 0.0))

        if drop_type == "ring":
            self._I_drop = I_ring(
                cfg["ring_mass"], cfg["ring_r_inner"],
                cfg["ring_r_outer"], cfg.get("ring_offset_x", 0.0))
        else:
            self._I_drop = I_solid_disk(cfg["disk2_mass"], cfg["disk2_radius"])

        self._I_initial = self._I_disk + self._I_pulley
        self._I_final = self._I_initial + self._I_drop

        pre_t = float(cfg.get("pre_collision_time", 2.0))
        post_t = float(cfg.get("post_collision_time", 3.0))
        cfg["sim_time"] = pre_t + post_t

        omega_f_theory = self._I_initial * cfg["omega_init"] / self._I_final
        cfg["omega_f_theory"] = omega_f_theory

        log.info("I_initial=%.6f, I_drop=%.6f, I_final=%.6f, omega_f_theory=%.3f",
                 self._I_initial, self._I_drop, self._I_final, omega_f_theory)

    # ======================================================= step loop
    def step_callback(self, step: int, t: float) -> dict:
        pre_t = float(self.cfg.get("pre_collision_time", 2.0))

        if t < pre_t and self._ring_hold_pos is not None:
            self.drop_body.set_world_pose(self._ring_hold_pos, self._ring_hold_rot)
            self.drop_body.set_linear_velocity(np.zeros(3))
            self.drop_body.set_angular_velocity(np.zeros(3))

        self._sync_visuals()

        omega_disk = float(self.disk.get_angular_velocity()[2])
        omega_drop = float(self.drop_body.get_angular_velocity()[2])
        drop_z = float(self.drop_body.get_world_pose()[0][2])

        L_disk = self._I_initial * omega_disk
        L_drop = self._I_drop * omega_drop
        L_total = L_disk + L_drop

        KE_disk = 0.5 * self._I_initial * omega_disk ** 2
        KE_drop = 0.5 * self._I_drop * omega_drop ** 2
        KE_total = KE_disk + KE_drop

        phase = "pre_collision" if t < pre_t else "post_drop"

        return {
            "time": t,
            "omega_disk": omega_disk,
            "omega_drop": omega_drop,
            "L_disk": L_disk,
            "L_drop": L_drop,
            "L_total": L_total,
            "KE_disk": KE_disk,
            "KE_drop": KE_drop,
            "KE_total": KE_total,
            "drop_z": drop_z,
            "phase": phase,
        }

    # ======================================================= analyze
    def analyze(self, df: pd.DataFrame) -> dict:
        cfg = self.cfg
        dt = float(cfg.get("physics_dt", 1 / 240))
        window = max(10, int(0.3 / dt))

        pre_df = df[df["phase"] == "pre_collision"]
        post_df = df[df["phase"] == "post_drop"]

        pre_tail = pre_df.iloc[-window:] if len(pre_df) >= window else pre_df
        post_tail = post_df.iloc[-window:] if len(post_df) >= window else post_df

        omega_i = float(pre_tail["omega_disk"].mean()) if len(pre_tail) > 0 else 0.0
        omega_f_disk = float(post_tail["omega_disk"].mean()) if len(post_tail) > 0 else 0.0
        omega_f_drop = float(post_tail["omega_drop"].mean()) if len(post_tail) > 0 else 0.0

        L_initial = self._I_initial * omega_i
        L_final = self._I_initial * omega_f_disk + self._I_drop * omega_f_drop
        L_pct_diff = (abs((L_final - L_initial) / L_initial * 100)
                      if L_initial != 0 else 0.0)

        KE_initial = 0.5 * self._I_initial * omega_i ** 2
        KE_final = (0.5 * self._I_initial * omega_f_disk ** 2
                     + 0.5 * self._I_drop * omega_f_drop ** 2)
        KE_pct_loss = (max(0.0, (KE_initial - KE_final) / KE_initial * 100)
                       if KE_initial != 0 else 0.0)

        omega_f_theory = float(cfg.get("omega_f_theory", 0.0))
        omega_f_measured = (omega_f_disk + omega_f_drop) / 2
        omega_pct_err = (abs(omega_f_measured - omega_f_theory) / omega_f_theory * 100
                         if omega_f_theory != 0 else 0.0)

        contact_time = None
        if len(post_df) > 0 and self._ring_hold_pos is not None:
            contact_z = self._ring_hold_pos[2] - 0.005
            landed = post_df[post_df["drop_z"] <= contact_z]
            if len(landed) > 0:
                contact_time = float(landed.iloc[0]["time"])

        return {
            "drop_object": str(cfg.get("drop_object", "ring")),
            "I_disk": self._I_disk,
            "I_pulley": self._I_pulley,
            "I_drop": self._I_drop,
            "I_initial": self._I_initial,
            "I_final": self._I_final,
            "omega_i": omega_i,
            "omega_f_disk": omega_f_disk,
            "omega_f_drop": omega_f_drop,
            "omega_f_measured": omega_f_measured,
            "omega_f_theory": omega_f_theory,
            "omega_pct_err": omega_pct_err,
            "L_initial": L_initial,
            "L_final": L_final,
            "L_pct_diff": L_pct_diff,
            "KE_initial": KE_initial,
            "KE_final": KE_final,
            "KE_pct_loss": KE_pct_loss,
            "contact_time_s": contact_time,
        }

    # ======================================================= plots
    def plot(self, df: pd.DataFrame) -> None:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        pre_t = float(self.cfg.get("pre_collision_time", 2.0))

        fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

        axs[0].plot(df["time"], df["omega_disk"], color="royalblue", lw=2, label="Disk")
        axs[0].plot(df["time"], df["omega_drop"], color="firebrick", lw=2, label="Ring")
        axs[0].axvline(pre_t, color="gray", ls="--", lw=1, label="Released")
        axs[0].set_ylabel("Angular Velocity (rad/s)")
        axs[0].set_title("Angular Velocity vs Time")
        axs[0].legend()
        axs[0].grid(True, alpha=0.3)

        axs[1].plot(df["time"], df["L_disk"], color="royalblue", lw=1.5, label="L disk")
        axs[1].plot(df["time"], df["L_drop"], color="firebrick", lw=1.5, label="L ring")
        axs[1].plot(df["time"], df["L_total"], color="green", lw=2.5, label="L total")
        axs[1].axvline(pre_t, color="gray", ls="--", lw=1)
        axs[1].set_ylabel(u"Angular Momentum (kg\u00b7m\u00b2/s)")
        axs[1].set_title("Angular Momentum vs Time")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)

        axs[2].plot(df["time"], df["KE_disk"], color="royalblue", lw=1.5, label="KE disk")
        axs[2].plot(df["time"], df["KE_drop"], color="firebrick", lw=1.5, label="KE ring")
        axs[2].plot(df["time"], df["KE_total"], color="orange", lw=2.5, label="KE total")
        axs[2].axvline(pre_t, color="gray", ls="--", lw=1)
        axs[2].set_xlabel("Time (s)")
        axs[2].set_ylabel("Rotational KE (J)")
        axs[2].set_title("Rotational Kinetic Energy vs Time")
        axs[2].legend()
        axs[2].grid(True, alpha=0.3)

        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "angular_momentum.png"), dpi=200)
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(df["time"], df["drop_z"], color="firebrick", lw=2)
        ax2.axvline(pre_t, color="gray", ls="--", lw=1, label="Released")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Ring Z Position (m)")
        ax2.set_title("Drop Object Height vs Time")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(os.path.join(self.out_dir, "drop_height.png"), dpi=200)
        plt.close(fig2)

        log.info("Plots saved to %s", self.out_dir)

    # ======================================================= report
    def generate_report(self, summary: dict, df: pd.DataFrame) -> str | None:
        try:
            rg = ReportGenerator()
            context = {
                "summary": summary,
                "cfg": self.cfg,
                "out_dir": self.out_dir,
                "num_steps": len(df),
            }
            return rg.render(
                "expt1_angular_momentum.md.j2",
                os.path.join(self.out_dir, "report.md"),
                context,
            )
        except Exception:
            log.warning("Report generation skipped (template or jinja2 missing).")
            return None

    # ======================================================= display
    def print_summary(self, summary: dict) -> None:
        s = summary
        print("\n========== Experiment 1: Angular Momentum Conservation ==========")
        print(f"  Drop object:            {s['drop_object']}")
        print(f"  I_disk + I_pulley:      {s['I_initial']:.6f} kg*m^2")
        print(f"  I_drop:                 {s['I_drop']:.6f} kg*m^2")
        print(f"  I_final:                {s['I_final']:.6f} kg*m^2")
        print(f"  omega_initial:          {s['omega_i']:.2f} rad/s")
        print(f"  omega_final (measured): {s['omega_f_measured']:.2f} rad/s")
        print(f"  omega_final (theory):   {s['omega_f_theory']:.2f} rad/s")
        print(f"  omega error:            {s['omega_pct_err']:.2f} %")
        if s["contact_time_s"] is not None:
            print(f"  Contact time:           {s['contact_time_s']:.3f} s")
        print(f"  L_initial:              {s['L_initial']:.6f} kg*m^2/s")
        print(f"  L_final:                {s['L_final']:.6f} kg*m^2/s")
        print(f"  L % difference:         {s['L_pct_diff']:.3f} %")
        print(f"  KE_initial:             {s['KE_initial']:.6f} J")
        print(f"  KE_final:               {s['KE_final']:.6f} J")
        print(f"  KE loss:                {s['KE_pct_loss']:.2f} %")
        ctype = "inelastic" if s["KE_pct_loss"] > 1.0 else "near-elastic"
        print(f"  Collision type:         {ctype}")
        print(f"  Output:                 {self.out_dir}")
        print("=================================================================\n")

    # ======================================================= cleanup
    def shutdown(self) -> None:
        global _app
        if _app is not None:
            _app.close()
            _app = None
