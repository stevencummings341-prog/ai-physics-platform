"""Experiment 7 — 1D Momentum Conservation on a frictionless track."""

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
from core.scene import SceneBuilder
from core.reporter import ReportGenerator


_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.yaml")


class Experiment(ExperimentBase):
    """1D collision between two carts on a frictionless horizontal track."""

    name = "expt7_momentum"

    def __init__(self, config_path: str | None = None, overrides: dict | None = None):
        if config_path is None:
            config_path = _DEFAULT_CONFIG
        self.app = _get_app(overrides or {})
        super().__init__(config_path, overrides)
        self.cart1 = None
        self.cart2 = None
        self.cart_size = np.array(self.cfg.get("cart_size", [0.45, 0.22, 0.15]), dtype=float)

    # ----------------------------------------------------------- scene
    def build_scene(self) -> None:
        import omni
        from isaacsim.core.api import World
        from isaacsim.core.api.objects import DynamicCuboid

        cfg = self.cfg
        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=cfg.get("physics_dt", 1 / 240),
            rendering_dt=cfg.get("render_dt", 1 / 60),
        )
        self.world.scene.clear()
        self.world.get_physics_context().set_gravity(-9.81)

        stage = omni.usd.get_context().get_stage()
        sb = SceneBuilder(self.world, stage)

        sb.add_dome_light()
        track_mat = sb.frictionless_material(
            "/World/Materials/TrackMat", restitution=0.0,
        )
        cart_mat = sb.frictionless_material(
            "/World/Materials/CartMat", restitution=cfg.get("restitution", 1.0),
        )

        tl = cfg.get("track_length", 8.0)
        tw = cfg.get("track_width", 0.30)
        top_z = sb.add_track(length=tl, width=tw, material=track_mat)
        sb.add_grid_markings(track_width=tw, z=top_z + 0.001)

        cart_z = top_z + self.cart_size[2] / 2 + 0.002

        self.cart1 = self.world.scene.add(
            DynamicCuboid(
                prim_path="/World/Cart1", name="cart1",
                position=np.array([cfg.get("cart1_x", -0.85), 0.0, cart_z]),
                scale=self.cart_size,
                color=np.array([1.0, 0.15, 0.15]),
                mass=cfg.get("m1", 0.25),
                physics_material=cart_mat,
            )
        )
        self.cart2 = self.world.scene.add(
            DynamicCuboid(
                prim_path="/World/Cart2", name="cart2",
                position=np.array([cfg.get("cart2_x", 0.35), 0.0, cart_z]),
                scale=self.cart_size,
                color=np.array([0.15, 0.45, 1.0]),
                mass=cfg.get("m2", 0.25),
                physics_material=cart_mat,
            )
        )

        # ---- camera: look at the track from above-front ----
        from core.scene import set_camera
        mid_x = (cfg.get("cart1_x", -0.85) + cfg.get("cart2_x", 0.35)) / 2
        set_camera(
            eye=np.array([mid_x, -1.2, 0.6]),
            target=np.array([mid_x, 0.0, 0.05]),
        )

    def prepare_run(self) -> None:
        """Auto-tune sim time based on initial separation and closing speed."""
        x1 = float(self.cfg.get("cart1_x", -0.85))
        x2 = float(self.cfg.get("cart2_x", 0.35))
        v1 = float(self.cfg.get("v1_init", 0.30))
        v2 = float(self.cfg.get("v2_init", 0.00))
        cart_length = float(self.cart_size[0])

        center_distance = abs(x2 - x1)
        surface_gap = max(0.0, center_distance - cart_length)
        closing_speed = max(0.0, v1 - v2) if x1 <= x2 else max(0.0, v2 - v1)

        self.cfg["initial_center_distance"] = center_distance
        self.cfg["initial_surface_gap"] = surface_gap
        self.cfg["closing_speed"] = closing_speed

        base_sim_time = float(self.cfg.get("sim_time", 6.0))
        if closing_speed > 1e-8:
            collision_eta = surface_gap / closing_speed
            self.cfg["estimated_collision_time"] = collision_eta
            self.cfg["sim_time"] = max(base_sim_time, collision_eta + 2.0)
        else:
            self.cfg["estimated_collision_time"] = None
            self.cfg["sim_time"] = base_sim_time

        log.info(
            "Prepared run: center_distance=%.3f m, surface_gap=%.3f m, "
            "closing_speed=%.3f m/s, sim_time=%.2f s",
            center_distance,
            surface_gap,
            closing_speed,
            self.cfg["sim_time"],
        )

    def apply_initial_conditions(self) -> None:
        v1 = self.cfg.get("v1_init", 0.30)
        v2 = self.cfg.get("v2_init", 0.00)
        self.cart1.set_linear_velocity(np.array([v1, 0.0, 0.0]))
        self.cart2.set_linear_velocity(np.array([v2, 0.0, 0.0]))
        log.info("Initial velocities set: v1=%.3f m/s, v2=%.3f m/s", v1, v2)

    # -------------------------------------------------------- step loop
    def step_callback(self, step: int, t: float) -> dict:
        m1 = self.cfg.get("m1", 0.25)
        m2 = self.cfg.get("m2", 0.25)

        x1 = float(self.cart1.get_world_pose()[0][0])
        x2 = float(self.cart2.get_world_pose()[0][0])
        v1 = float(self.cart1.get_linear_velocity()[0])
        v2 = float(self.cart2.get_linear_velocity()[0])
        center_distance = abs(x2 - x1)
        surface_gap = center_distance - float(self.cart_size[0])
        closing_speed = max(0.0, v1 - v2) if x1 <= x2 else max(0.0, v2 - v1)

        p1, p2 = m1 * v1, m2 * v2
        ke1, ke2 = 0.5 * m1 * v1 ** 2, 0.5 * m2 * v2 ** 2

        return {
            "time": t,
            "x1": x1, "x2": x2,
            "v1": v1, "v2": v2,
            "p1": p1, "p2": p2, "p_total": p1 + p2,
            "ke1": ke1, "ke2": ke2, "ke_total": ke1 + ke2,
            "center_distance": center_distance,
            "surface_gap": surface_gap,
            "closing_speed": closing_speed,
        }

    # ------------------------------------------------------ analysis
    def analyze(self, df: pd.DataFrame) -> dict:
        collision_idx = int(np.argmin(df["surface_gap"]))
        dt = self.cfg.get("physics_dt", 1 / 240)
        window = max(10, int(0.02 / dt))
        collision_tolerance = float(self.cfg.get("collision_tolerance", 0.02))
        min_surface_gap = float(df["surface_gap"].min())
        collision_detected = min_surface_gap <= collision_tolerance

        if collision_detected:
            pre_slice = df.iloc[max(0, collision_idx - window):collision_idx]
            post_slice = df.iloc[collision_idx:collision_idx + window]
            analysis_mode = "collision_window"
        else:
            pre_slice = df.iloc[:window]
            post_slice = df.iloc[-window:]
            analysis_mode = "full_run_fallback"

        pre = pre_slice.mean(numeric_only=True)
        post = post_slice.mean(numeric_only=True)

        p_pre = float(pre.get("p_total", 0.0))
        p_post = float(post.get("p_total", 0.0))
        ke_pre = float(pre.get("ke_total", 0.0))
        ke_post = float(post.get("ke_total", 0.0))
        collision_time = float(df.iloc[collision_idx]["time"]) if collision_detected else None

        return {
            "m1_kg": self.cfg["m1"], "m2_kg": self.cfg["m2"],
            "restitution": self.cfg.get("restitution", 1.0),
            "v1_init": self.cfg.get("v1_init"), "v2_init": self.cfg.get("v2_init"),
            "collision_detected": collision_detected,
            "analysis_mode": analysis_mode,
            "estimated_collision_time_s": self.cfg.get("estimated_collision_time"),
            "collision_time_s": collision_time,
            "pre_v1": float(pre.get("v1", 0.0)), "post_v1": float(post.get("v1", 0.0)),
            "pre_v2": float(pre.get("v2", 0.0)), "post_v2": float(post.get("v2", 0.0)),
            "pre_p_total": p_pre, "post_p_total": p_post,
            "momentum_error_pct": abs((p_post - p_pre) / p_pre * 100) if p_pre != 0 else 0.0,
            "pre_ke_total": ke_pre, "post_ke_total": ke_post,
            "ke_loss_pct": max(0.0, (ke_pre - ke_post) / ke_pre * 100) if ke_pre != 0 else 0.0,
            "min_center_distance": float(df["center_distance"].min()),
            "min_surface_gap": min_surface_gap,
        }

    # --------------------------------------------------------- plots
    def plot(self, df: pd.DataFrame) -> None:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axs = plt.subplots(3, 1, figsize=(10, 11), sharex=True)

        axs[0].plot(df["time"], df["x1"], color="red", lw=2, label="Cart 1")
        axs[0].plot(df["time"], df["x2"], color="blue", lw=2, label="Cart 2")
        axs[0].set_ylabel("Position (m)")
        axs[0].set_title("Position vs Time")
        axs[0].legend()
        axs[0].grid(True, alpha=0.3)

        axs[1].plot(df["time"], df["v1"], color="red", lw=2, label="Cart 1")
        axs[1].plot(df["time"], df["v2"], color="blue", lw=2, label="Cart 2")
        axs[1].set_ylabel("Velocity (m/s)")
        axs[1].set_title("Velocity vs Time")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)

        axs[2].plot(df["time"], df["ke1"], color="red", lw=2, label="Cart 1 KE")
        axs[2].plot(df["time"], df["ke2"], color="blue", lw=2, label="Cart 2 KE")
        axs[2].plot(df["time"], df["ke_total"], color="gray", lw=1.5, ls="--", label="Total KE")
        axs[2].set_xlabel("Time (s)")
        axs[2].set_ylabel("Kinetic Energy (J)")
        axs[2].set_title("Kinetic Energy vs Time")
        axs[2].legend()
        axs[2].grid(True, alpha=0.3)

        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "kinematics.png"), dpi=200)
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(df["time"], df["p_total"], color="green", lw=2.5)
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Total Momentum (kg·m/s)")
        ax2.set_title("Total System Momentum vs Time")
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(os.path.join(self.out_dir, "total_momentum.png"), dpi=200)
        plt.close(fig2)

        fig3, ax3 = plt.subplots(figsize=(10, 4))
        ax3.plot(df["time"], df["surface_gap"], color="purple", lw=2.0)
        ax3.axhline(0.0, color="black", lw=1.0, ls="--")
        ax3.set_xlabel("Time (s)")
        ax3.set_ylabel("Surface Gap (m)")
        ax3.set_title("Surface Gap vs Time")
        ax3.grid(True, alpha=0.3)
        fig3.tight_layout()
        fig3.savefig(os.path.join(self.out_dir, "surface_gap.png"), dpi=200)
        plt.close(fig3)

        log.info("Plots saved to %s", self.out_dir)

    # --------------------------------------------------------- report
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
                "expt7_momentum.md.j2",
                os.path.join(self.out_dir, "report.md"),
                context,
            )
        except Exception:
            log.warning("Report generation skipped (template or jinja2 missing).")
            return None

    # ------------------------------------------------------- display
    def print_summary(self, summary: dict) -> None:
        print("\n========== Experiment 7: Momentum Conservation ==========")
        print(f"  m1 = {summary['m1_kg']} kg    m2 = {summary['m2_kg']} kg")
        print(f"  v1_init = {summary['v1_init']} m/s    v2_init = {summary['v2_init']} m/s")
        print(f"  Restitution = {summary['restitution']}")
        print(f"  Collision detected:   {summary['collision_detected']}")
        if summary["estimated_collision_time_s"] is not None:
            print(f"  Estimated collision:  {summary['estimated_collision_time_s']:.3f} s")
        if summary["collision_time_s"] is not None:
            print(f"  Collision time:       {summary['collision_time_s']:.3f} s")
        else:
            print("  Collision time:       N/A (no collision detected)")
        print(f"  Min center distance:  {summary['min_center_distance']:.4f} m")
        print(f"  Min surface gap:      {summary['min_surface_gap']:.4f} m")
        print(f"  Momentum error:       {summary['momentum_error_pct']:.3f} %")
        print(f"  KE loss:              {summary['ke_loss_pct']:.2f} %")
        ctype = "elastic" if summary["ke_loss_pct"] < 1.0 else "inelastic"
        print(f"  Collision type:       {ctype}")
        print(f"  Analysis mode:        {summary['analysis_mode']}")
        print(f"  Output:               {self.out_dir}")
        print("=========================================================\n")

    # -------------------------------------------------------- cleanup
    def shutdown(self) -> None:
        global _app
        if _app is not None:
            _app.close()
            _app = None
