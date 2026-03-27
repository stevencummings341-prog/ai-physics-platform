"""Experiment 1 — Conservation of Angular Momentum.

A non-rotating ring (or second disk) is dropped onto a spinning disk.
Angular speed is measured before the drop and after the objects reach
a common angular velocity.  Angular momentum should be conserved;
kinetic energy should decrease (inelastic rotational collision).

PASCO EX-5517 reference implementation for Isaac Sim / PhysX 5.
"""

from __future__ import annotations

import logging
import math
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


# ---------------------------------------------------------------------------
# Moment-of-inertia helpers (analytical, from PASCO theory section)
# ---------------------------------------------------------------------------

def I_solid_disk(mass: float, radius: float) -> float:
    """I = ½MR² for a solid disk about its symmetry axis."""
    return 0.5 * mass * radius ** 2


def I_ring(mass: float, r_inner: float, r_outer: float, offset: float = 0.0) -> float:
    """I = ½M(R₁² + R₂²) + Mx²  (Eq. 3 + 4 from PASCO manual)."""
    return 0.5 * mass * (r_inner ** 2 + r_outer ** 2) + mass * offset ** 2


# ---------------------------------------------------------------------------
# Experiment class
# ---------------------------------------------------------------------------

class Experiment(ExperimentBase):
    """Drop a ring (or disk) onto a spinning disk; verify L conservation."""

    name = "expt1_angular_momentum"

    def __init__(self, config_path: str | None = None, overrides: dict | None = None):
        if config_path is None:
            config_path = _DEFAULT_CONFIG
        self.app = _get_app(overrides or {})
        super().__init__(config_path, overrides)

        self.disk = None
        self.drop_body = None

        self._I_disk = 0.0
        self._I_pulley = 0.0
        self._I_drop = 0.0
        self._I_initial = 0.0
        self._I_final = 0.0

        self._ring_hold_pos: np.ndarray | None = None
        self._ring_hold_rot: np.ndarray | None = None
        self._disk_center_z = 0.0

    # ---------------------------------------------------------------- scene
    def build_scene(self) -> None:
        import omni
        from isaacsim.core.api import World
        from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid, VisualCuboid
        from isaacsim.core.api.materials import PhysicsMaterial
        from pxr import UsdPhysics, Gf

        cfg = self.cfg
        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=cfg.get("physics_dt", 1 / 240),
            rendering_dt=cfg.get("render_dt", 1 / 60),
        )
        self.world.scene.clear()
        self.world.get_physics_context().set_gravity(-9.81)

        stage = omni.usd.get_context().get_stage()

        from pxr import UsdLux
        UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1500.0)

        # ---- materials ----
        axle_mat = PhysicsMaterial(
            prim_path="/World/Materials/AxleMat",
            static_friction=0.0, dynamic_friction=0.0, restitution=0.0,
        )
        contact_mat = PhysicsMaterial(
            prim_path="/World/Materials/ContactMat",
            static_friction=cfg.get("contact_static_friction", 0.8),
            dynamic_friction=cfg.get("contact_dynamic_friction", 0.6),
            restitution=0.0,
        )

        # ---- table ----
        self.world.scene.add(FixedCuboid(
            prim_path="/World/Table", name="table",
            position=np.array([0.0, 0.0, -0.06]),
            scale=np.array([0.6, 0.6, 0.10]),
            color=np.array([0.12, 0.12, 0.15]),
        ))

        # ---- stand pillar ----
        stand_h = 0.30
        self.world.scene.add(FixedCuboid(
            prim_path="/World/Stand", name="stand",
            position=np.array([0.0, 0.0, -0.01 + stand_h / 2]),
            scale=np.array([0.03, 0.03, stand_h]),
            color=np.array([0.40, 0.40, 0.42]),
        ))

        # ---- disk (approximated as thin, wide cuboid) ----
        disk_r = float(cfg.get("disk_radius", 0.125))
        disk_h = float(cfg.get("disk_height", 0.01))
        disk_side = disk_r * 2
        self._disk_center_z = stand_h - 0.01 + disk_h / 2

        self.disk = self.world.scene.add(DynamicCuboid(
            prim_path="/World/Disk", name="disk",
            position=np.array([0.0, 0.0, self._disk_center_z]),
            scale=np.array([disk_side, disk_side, disk_h]),
            color=np.array([0.75, 0.75, 0.82]),
            mass=float(cfg.get("disk_mass", 0.120)),
            physics_material=contact_mat,
        ))

        # Override disk inertia to match a solid cylinder
        disk_prim = stage.GetPrimAtPath("/World/Disk")
        disk_Iz = I_solid_disk(cfg["disk_mass"], disk_r)
        disk_Ixy = disk_Iz / 2 + cfg["disk_mass"] * disk_h ** 2 / 12
        mass_api = UsdPhysics.MassAPI(disk_prim)
        mass_api.CreateDiagonalInertiaAttr(
            Gf.Vec3f(float(disk_Ixy), float(disk_Ixy), float(disk_Iz))
        )

        # ---- revolute joint: pin disk to world, allow only Z rotation ----
        axle_joint = UsdPhysics.RevoluteJoint.Define(stage, "/World/DiskAxle")
        axle_joint.CreateAxisAttr("Z")
        axle_joint.CreateBody1Rel().SetTargets(["/World/Disk"])
        axle_joint.CreateLocalPos0Attr(Gf.Vec3f(0, 0, float(self._disk_center_z)))
        axle_joint.CreateLocalPos1Attr(Gf.Vec3f(0, 0, 0))
        axle_joint.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0))
        axle_joint.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))

        # ---- drop body (ring or disk2) ----
        drop_type = str(cfg.get("drop_object", "ring"))
        drop_h_above = float(cfg.get("drop_height", 0.003))
        drop_z = self._disk_center_z + disk_h / 2 + drop_h_above

        if drop_type == "ring":
            ring_r_out = float(cfg.get("ring_r_outer", 0.064))
            ring_h = float(cfg.get("ring_height", 0.02))
            ring_side = ring_r_out * 2
            drop_z += ring_h / 2

            self.drop_body = self.world.scene.add(DynamicCuboid(
                prim_path="/World/Ring", name="ring",
                position=np.array([0.0, 0.0, drop_z]),
                scale=np.array([ring_side, ring_side, ring_h]),
                color=np.array([0.30, 0.30, 0.35]),
                mass=float(cfg.get("ring_mass", 0.470)),
                physics_material=contact_mat,
            ))

            ring_prim = stage.GetPrimAtPath("/World/Ring")
            ring_Iz = I_ring(
                cfg["ring_mass"], cfg["ring_r_inner"],
                cfg["ring_r_outer"], cfg.get("ring_offset_x", 0.0),
            )
            ring_Ixy = ring_Iz / 2
            ring_mass_api = UsdPhysics.MassAPI(ring_prim)
            ring_mass_api.CreateDiagonalInertiaAttr(
                Gf.Vec3f(float(ring_Ixy), float(ring_Ixy), float(ring_Iz))
            )
        else:
            d2_r = float(cfg.get("disk2_radius", 0.125))
            d2_h = float(cfg.get("disk2_height", 0.01))
            d2_side = d2_r * 2
            drop_z += d2_h / 2

            self.drop_body = self.world.scene.add(DynamicCuboid(
                prim_path="/World/Disk2", name="disk2",
                position=np.array([0.0, 0.0, drop_z]),
                scale=np.array([d2_side, d2_side, d2_h]),
                color=np.array([0.65, 0.55, 0.40]),
                mass=float(cfg.get("disk2_mass", 0.120)),
                physics_material=contact_mat,
            ))

            d2_prim = stage.GetPrimAtPath("/World/Disk2")
            d2_Iz = I_solid_disk(cfg["disk2_mass"], d2_r)
            d2_Ixy = d2_Iz / 2
            d2_mass_api = UsdPhysics.MassAPI(d2_prim)
            d2_mass_api.CreateDiagonalInertiaAttr(
                Gf.Vec3f(float(d2_Ixy), float(d2_Ixy), float(d2_Iz))
            )

        # ---- visual: axis marker at center ----
        self.world.scene.add(VisualCuboid(
            prim_path="/World/AxisMarker", name="axis_marker",
            position=np.array([0.0, 0.0, self._disk_center_z + disk_h / 2 + 0.001]),
            scale=np.array([0.004, 0.004, 0.002]),
            color=np.array([1.0, 0.2, 0.2]),
        ))

        # ---- visual: colored corner marker on disk so rotation is visible ----
        marker_offset = disk_r * 0.7
        self.world.scene.add(VisualCuboid(
            prim_path="/World/Disk/CornerMarkerA", name="disk_corner_a",
            position=np.array([marker_offset, 0.0, self._disk_center_z + disk_h / 2 + 0.0005]),
            scale=np.array([0.02, 0.02, 0.001]),
            color=np.array([1.0, 0.85, 0.0]),
        ))
        self.world.scene.add(VisualCuboid(
            prim_path="/World/Disk/CornerMarkerB", name="disk_corner_b",
            position=np.array([-marker_offset, 0.0, self._disk_center_z + disk_h / 2 + 0.0005]),
            scale=np.array([0.02, 0.02, 0.001]),
            color=np.array([0.2, 0.9, 0.3]),
        ))

        # ---- camera: look at the disk from a diagonal angle ----
        from core.scene import set_camera
        cam_z = self._disk_center_z + 0.15
        set_camera(
            eye=np.array([0.45, -0.45, cam_z + 0.20]),
            target=np.array([0.0, 0.0, self._disk_center_z]),
        )

    # --------------------------------------------------------- prepare run
    def prepare_run(self) -> None:
        cfg = self.cfg
        drop_type = str(cfg.get("drop_object", "ring"))

        self._I_disk = I_solid_disk(cfg["disk_mass"], cfg["disk_radius"])
        self._I_pulley = I_solid_disk(
            cfg.get("pulley_mass", 0.0), cfg.get("pulley_radius", 0.0),
        )

        if drop_type == "ring":
            self._I_drop = I_ring(
                cfg["ring_mass"], cfg["ring_r_inner"],
                cfg["ring_r_outer"], cfg.get("ring_offset_x", 0.0),
            )
        else:
            self._I_drop = I_solid_disk(cfg["disk2_mass"], cfg["disk2_radius"])

        self._I_initial = self._I_disk + self._I_pulley
        self._I_final = self._I_initial + self._I_drop

        pre_t = float(cfg.get("pre_collision_time", 2.0))
        post_t = float(cfg.get("post_collision_time", 3.0))
        cfg["sim_time"] = pre_t + post_t

        omega_f_theory = self._I_initial * cfg["omega_init"] / self._I_final
        cfg["omega_f_theory"] = omega_f_theory

        log.info(
            "I_disk=%.6f, I_drop=%.6f, I_initial=%.6f, I_final=%.6f, "
            "omega_f_theory=%.3f rad/s",
            self._I_disk, self._I_drop, self._I_initial, self._I_final,
            omega_f_theory,
        )

    # ------------------------------------------------ initial conditions
    def apply_initial_conditions(self) -> None:
        omega = float(self.cfg.get("omega_init", 25.0))
        self.disk.set_angular_velocity(np.array([0.0, 0.0, omega]))

        pos, rot = self.drop_body.get_world_pose()
        self._ring_hold_pos = pos.copy()
        self._ring_hold_rot = rot.copy()
        self.drop_body.set_linear_velocity(np.zeros(3))
        self.drop_body.set_angular_velocity(np.zeros(3))

        log.info("Disk angular velocity set to %.2f rad/s", omega)

    # --------------------------------------------------------- step loop
    def step_callback(self, step: int, t: float) -> dict:
        pre_t = float(self.cfg.get("pre_collision_time", 2.0))

        if t < pre_t and self._ring_hold_pos is not None:
            self.drop_body.set_world_pose(self._ring_hold_pos, self._ring_hold_rot)
            self.drop_body.set_linear_velocity(np.zeros(3))
            self.drop_body.set_angular_velocity(np.zeros(3))

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

    # ----------------------------------------------------------- analyze
    def analyze(self, df: pd.DataFrame) -> dict:
        cfg = self.cfg
        pre_t = float(cfg.get("pre_collision_time", 2.0))
        dt = float(cfg.get("physics_dt", 1 / 240))
        window = max(10, int(0.3 / dt))

        pre_df = df[df["phase"] == "pre_collision"]
        post_df = df[df["phase"] == "post_drop"]

        pre_tail = pre_df.iloc[-window:] if len(pre_df) >= window else pre_df
        post_tail = post_df.iloc[-window:] if len(post_df) >= window else post_df

        omega_i = float(pre_tail["omega_disk"].mean())
        omega_f_disk = float(post_tail["omega_disk"].mean())
        omega_f_drop = float(post_tail["omega_drop"].mean())

        L_initial = self._I_initial * omega_i
        L_final = self._I_initial * omega_f_disk + self._I_drop * omega_f_drop
        L_pct_diff = abs((L_final - L_initial) / L_initial * 100) if L_initial != 0 else 0.0

        KE_initial = 0.5 * self._I_initial * omega_i ** 2
        KE_final = (0.5 * self._I_initial * omega_f_disk ** 2
                     + 0.5 * self._I_drop * omega_f_drop ** 2)
        KE_pct_loss = max(0.0, (KE_initial - KE_final) / KE_initial * 100) if KE_initial != 0 else 0.0

        omega_f_theory = float(cfg.get("omega_f_theory", 0.0))
        omega_f_measured = (omega_f_disk + omega_f_drop) / 2
        omega_pct_err = (abs(omega_f_measured - omega_f_theory) / omega_f_theory * 100
                         if omega_f_theory != 0 else 0.0)

        drop_type = str(cfg.get("drop_object", "ring"))

        contact_time = None
        if len(post_df) > 0:
            disk_h = float(cfg.get("disk_height", 0.01))
            contact_z = self._disk_center_z + disk_h / 2
            if drop_type == "ring":
                contact_z += float(cfg.get("ring_height", 0.02)) / 2
            else:
                contact_z += float(cfg.get("disk2_height", 0.01)) / 2
            contact_z += 0.005
            landed = post_df[post_df["drop_z"] <= contact_z]
            if len(landed) > 0:
                contact_time = float(landed.iloc[0]["time"])

        return {
            "drop_object": drop_type,
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

    # ------------------------------------------------------------- plots
    def plot(self, df: pd.DataFrame) -> None:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        pre_t = float(self.cfg.get("pre_collision_time", 2.0))

        fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

        axs[0].plot(df["time"], df["omega_disk"], color="royalblue", lw=2, label="Disk")
        axs[0].plot(df["time"], df["omega_drop"], color="firebrick", lw=2, label="Ring/Disk2")
        axs[0].axvline(pre_t, color="gray", ls="--", lw=1, label="Ring released")
        axs[0].set_ylabel("Angular Velocity (rad/s)")
        axs[0].set_title("Angular Velocity vs Time")
        axs[0].legend()
        axs[0].grid(True, alpha=0.3)

        axs[1].plot(df["time"], df["L_disk"], color="royalblue", lw=1.5, label="L disk")
        axs[1].plot(df["time"], df["L_drop"], color="firebrick", lw=1.5, label="L ring/disk2")
        axs[1].plot(df["time"], df["L_total"], color="green", lw=2.5, label="L total")
        axs[1].axvline(pre_t, color="gray", ls="--", lw=1)
        axs[1].set_ylabel("Angular Momentum (kg·m²/s)")
        axs[1].set_title("Angular Momentum vs Time")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)

        axs[2].plot(df["time"], df["KE_disk"], color="royalblue", lw=1.5, label="KE disk")
        axs[2].plot(df["time"], df["KE_drop"], color="firebrick", lw=1.5, label="KE ring/disk2")
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
        ax2.set_ylabel("Ring/Disk2 Z Position (m)")
        ax2.set_title("Drop Object Height vs Time")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(os.path.join(self.out_dir, "drop_height.png"), dpi=200)
        plt.close(fig2)

        log.info("Plots saved to %s", self.out_dir)

    # ----------------------------------------------------------- report
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

    # ----------------------------------------------------------- display
    def print_summary(self, summary: dict) -> None:
        s = summary
        print("\n========== Experiment 1: Conservation of Angular Momentum ==========")
        print(f"  Drop object:            {s['drop_object']}")
        print(f"  I_disk + I_pulley:      {s['I_initial']:.6f} kg·m²")
        print(f"  I_drop:                 {s['I_drop']:.6f} kg·m²")
        print(f"  I_final:                {s['I_final']:.6f} kg·m²")
        print(f"  omega_initial:          {s['omega_i']:.2f} rad/s")
        print(f"  omega_final (measured): {s['omega_f_measured']:.2f} rad/s")
        print(f"  omega_final (theory):   {s['omega_f_theory']:.2f} rad/s")
        print(f"  omega error:            {s['omega_pct_err']:.2f} %")
        if s["contact_time_s"] is not None:
            print(f"  Contact time:           {s['contact_time_s']:.3f} s")
        print(f"  L_initial:              {s['L_initial']:.6f} kg·m²/s")
        print(f"  L_final:                {s['L_final']:.6f} kg·m²/s")
        print(f"  L % difference:         {s['L_pct_diff']:.3f} %")
        print(f"  KE_initial:             {s['KE_initial']:.6f} J")
        print(f"  KE_final:               {s['KE_final']:.6f} J")
        print(f"  KE loss:                {s['KE_pct_loss']:.2f} %")
        collision_type = "inelastic" if s["KE_pct_loss"] > 1.0 else "near-elastic"
        print(f"  Collision type:         {collision_type}")
        print(f"  Output:                 {self.out_dir}")
        print("=====================================================================\n")

    # ---------------------------------------------------------- cleanup
    def shutdown(self) -> None:
        global _app
        if _app is not None:
            _app.close()
            _app = None
