import os
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from isaacsim import SimulationApp

CONFIG = {
    # Masses (kg)
    "m1": 0.25,
    "m2": 0.25,
    # Initial velocities along X (m/s)
    "v1_init": 0.30,
    "v2_init": 0.00,
    # 1.0 = perfectly elastic, 0.0 = perfectly inelastic
    "restitution": 1.0,
    # Timing
    "physics_dt": 1.0 / 240.0,
    "render_dt": 1.0 / 60.0,
    "sim_time": 6.0,
    "warmup_seconds": 0.5,
    # Geometry
    "cart_size": np.array([0.45, 0.22, 0.15]),
    "cart1_x": -0.85,
    "cart2_x": 0.35,
    "track_length": 8.0,
    "track_width": 0.30,
    # Display / VR
    "headless": False,
    "enable_livestream": False,
}

TRACK_HEIGHT = 0.10
TRACK_TOP_Z = 0.0

simulation_app = SimulationApp({"headless": CONFIG["headless"]})

if CONFIG["enable_livestream"]:
    from omni.isaac.core.utils.extensions import enable_extension
    enable_extension("omni.kit.livestream.native")
    print("LiveStream extension enabled — connect your VR headset.")

import omni
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid, VisualCuboid
from isaacsim.core.api.materials import PhysicsMaterial
from pxr import UsdLux


class MomentumExperiment:
    """1D momentum conservation experiment on a frictionless track with real gravity."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.out_dir = self._make_output_dir()
        self.world = None
        self.cart1 = None
        self.cart2 = None
        self.records: list[dict] = []
        self._setup_world()

    # ------------------------------------------------------------------ io ---
    @staticmethod
    def _make_output_dir() -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(os.getcwd(), f"outputs_expt7_{ts}")
        os.makedirs(out_dir, exist_ok=True)
        print(f"Output directory: {out_dir}")
        return out_dir

    # -------------------------------------------------------------- world ---
    def _setup_world(self):
        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=self.cfg["physics_dt"],
            rendering_dt=self.cfg["render_dt"],
        )
        self.world.scene.clear()
        self.world.get_physics_context().set_gravity(-9.81)

        stage = omni.usd.get_context().get_stage()
        UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1500.0)

        self._create_materials()
        self._build_track()
        self._build_grid_markings()
        self._build_carts()

    def _create_materials(self):
        self.track_material = PhysicsMaterial(
            prim_path="/World/Materials/TrackMat",
            static_friction=0.0,
            dynamic_friction=0.0,
            restitution=0.0,
        )
        self.cart_material = PhysicsMaterial(
            prim_path="/World/Materials/CartMat",
            static_friction=0.0,
            dynamic_friction=0.0,
            restitution=self.cfg["restitution"],
        )

    def _build_track(self):
        tl = self.cfg["track_length"]
        tw = self.cfg["track_width"]

        self.world.scene.add(
            FixedCuboid(
                prim_path="/World/Track",
                name="track",
                position=np.array([0.0, 0.0, TRACK_TOP_Z - TRACK_HEIGHT / 2]),
                scale=np.array([tl, tw, TRACK_HEIGHT]),
                color=np.array([0.15, 0.15, 0.18]),
                physics_material=self.track_material,
            )
        )

        rail_h = 0.04
        for sign, tag in [(1, "Left"), (-1, "Right")]:
            self.world.scene.add(
                FixedCuboid(
                    prim_path=f"/World/Rail{tag}",
                    name=f"rail_{tag.lower()}",
                    position=np.array([0.0, sign * tw / 2, TRACK_TOP_Z + rail_h / 2]),
                    scale=np.array([tl, 0.01, rail_h]),
                    color=np.array([0.30, 0.30, 0.35]),
                    physics_material=self.track_material,
                )
            )

    def _build_grid_markings(self):
        """VisualCuboid grid lines — zero collision, purely cosmetic."""
        tw = self.cfg["track_width"]
        z = TRACK_TOP_Z + 0.001

        for i, x in enumerate(np.arange(-4.0, 4.01, 0.5)):
            color = np.array([0.95, 0.85, 0.2]) if x == 0.0 else np.array([0.50, 0.50, 0.50])
            width = 0.01 if x == 0.0 else 0.005
            self.world.scene.add(
                VisualCuboid(
                    prim_path=f"/World/GridMark_{i}",
                    name=f"grid_mark_{i}",
                    position=np.array([float(x), 0.0, z]),
                    scale=np.array([width, tw, 0.001]),
                    color=color,
                )
            )

    def _build_carts(self):
        cart_z = TRACK_TOP_Z + self.cfg["cart_size"][2] / 2 + 0.002

        self.cart1 = self.world.scene.add(
            DynamicCuboid(
                prim_path="/World/Cart1",
                name="cart1",
                position=np.array([self.cfg["cart1_x"], 0.0, cart_z]),
                scale=self.cfg["cart_size"],
                color=np.array([1.0, 0.15, 0.15]),
                mass=self.cfg["m1"],
                physics_material=self.cart_material,
            )
        )
        self.cart2 = self.world.scene.add(
            DynamicCuboid(
                prim_path="/World/Cart2",
                name="cart2",
                position=np.array([self.cfg["cart2_x"], 0.0, cart_z]),
                scale=self.cfg["cart_size"],
                color=np.array([0.15, 0.45, 1.0]),
                mass=self.cfg["m2"],
                physics_material=self.cart_material,
            )
        )

    # --------------------------------------------------------------- run ---
    def reset(self):
        """Reset world and let carts settle on track before applying velocity."""
        self.records.clear()
        self.world.reset()

        warmup_steps = int(self.cfg["warmup_seconds"] / self.cfg["physics_dt"])
        for _ in range(warmup_steps):
            self.world.step(render=True)

        self.cart1.set_linear_velocity(np.array([self.cfg["v1_init"], 0.0, 0.0]))
        self.cart2.set_linear_velocity(np.array([self.cfg["v2_init"], 0.0, 0.0]))

    def run(self) -> pd.DataFrame:
        self.reset()

        steps = int(self.cfg["sim_time"] / self.cfg["physics_dt"])
        m1, m2 = self.cfg["m1"], self.cfg["m2"]
        dt = self.cfg["physics_dt"]
        print(f"Running {steps} steps ({self.cfg['sim_time']:.1f} s) ...")

        for step in range(steps):
            self.world.step(render=True)
            t = step * dt

            x1 = float(self.cart1.get_world_pose()[0][0])
            x2 = float(self.cart2.get_world_pose()[0][0])
            v1 = float(self.cart1.get_linear_velocity()[0])
            v2 = float(self.cart2.get_linear_velocity()[0])

            p1, p2 = m1 * v1, m2 * v2
            ke1, ke2 = 0.5 * m1 * v1 ** 2, 0.5 * m2 * v2 ** 2

            self.records.append({
                "time": t,
                "x1": x1, "x2": x2,
                "v1": v1, "v2": v2,
                "p1": p1, "p2": p2, "p_total": p1 + p2,
                "ke1": ke1, "ke2": ke2, "ke_total": ke1 + ke2,
                "gap": abs(x2 - x1),
            })

        print("Simulation complete.")
        return pd.DataFrame(self.records)

    # ---------------------------------------------------------- analysis ---
    def analyze(self, df: pd.DataFrame) -> dict:
        collision_idx = int(np.argmin(df["gap"]))
        window = max(10, int(0.02 / self.cfg["physics_dt"]))

        pre = df.iloc[max(0, collision_idx - window):collision_idx].mean(numeric_only=True)
        post = df.iloc[collision_idx:collision_idx + window].mean(numeric_only=True)

        p_pre = float(pre["p_total"])
        p_post = float(post["p_total"])
        ke_pre = float(pre["ke_total"])
        ke_post = float(post["ke_total"])

        return {
            "m1_kg": self.cfg["m1"],
            "m2_kg": self.cfg["m2"],
            "restitution": self.cfg["restitution"],
            "collision_time_s": float(df.iloc[collision_idx]["time"]),
            "pre_v1": float(pre["v1"]),
            "post_v1": float(post["v1"]),
            "pre_v2": float(pre["v2"]),
            "post_v2": float(post["v2"]),
            "pre_p_total": p_pre,
            "post_p_total": p_post,
            "momentum_error_pct": abs((p_post - p_pre) / p_pre * 100) if p_pre != 0 else 0.0,
            "pre_ke_total": ke_pre,
            "post_ke_total": ke_post,
            "ke_loss_pct": max(0.0, (ke_pre - ke_post) / ke_pre * 100) if ke_pre != 0 else 0.0,
            "min_gap": float(df["gap"].min()),
        }

    # ------------------------------------------------------------ plots ---
    def save_plots(self, df: pd.DataFrame):
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        # Velocity + Kinetic Energy
        fig, axs = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

        axs[0].plot(df["time"], df["v1"], label="Cart 1 (red)", color="red", lw=2)
        axs[0].plot(df["time"], df["v2"], label="Cart 2 (blue)", color="blue", lw=2)
        axs[0].set_ylabel("Velocity (m/s)")
        axs[0].legend()
        axs[0].grid(True, alpha=0.3)
        axs[0].set_title("Velocity vs Time")

        axs[1].plot(df["time"], df["ke1"], label="Cart 1 KE", color="red", lw=2)
        axs[1].plot(df["time"], df["ke2"], label="Cart 2 KE", color="blue", lw=2)
        axs[1].plot(df["time"], df["ke_total"], label="Total KE", color="gray", lw=1.5, ls="--")
        axs[1].set_xlabel("Time (s)")
        axs[1].set_ylabel("Kinetic Energy (J)")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)
        axs[1].set_title("Kinetic Energy vs Time")

        fig.tight_layout()
        fig.savefig(os.path.join(self.out_dir, "velocity_and_ke.png"), dpi=200)
        plt.close(fig)

        # Total momentum
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(df["time"], df["p_total"], color="green", lw=2.5)
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Total Momentum (kg·m/s)")
        ax2.set_title("Total System Momentum vs Time")
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(os.path.join(self.out_dir, "total_momentum.png"), dpi=200)
        plt.close(fig2)

        # Position
        fig3, ax3 = plt.subplots(figsize=(10, 4))
        ax3.plot(df["time"], df["x1"], label="Cart 1", color="red", lw=2)
        ax3.plot(df["time"], df["x2"], label="Cart 2", color="blue", lw=2)
        ax3.set_xlabel("Time (s)")
        ax3.set_ylabel("X Position (m)")
        ax3.set_title("Position vs Time")
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        fig3.tight_layout()
        fig3.savefig(os.path.join(self.out_dir, "position.png"), dpi=200)
        plt.close(fig3)

        print(f"Plots saved to {self.out_dir}")

    def save_data(self, df: pd.DataFrame, summary: dict):
        df.to_csv(os.path.join(self.out_dir, "timeseries.csv"), index=False)
        pd.DataFrame([summary]).to_csv(os.path.join(self.out_dir, "summary.csv"), index=False)
        print(f"CSV data saved to {self.out_dir}")

    def print_summary(self, summary: dict):
        print("\n========== Results ==========")
        print(f"  Collision time:            {summary['collision_time_s']:.3f} s")
        print(f"  Min gap at collision:      {summary['min_gap']:.4f} m")
        print(f"  Pre-collision  momentum:   {summary['pre_p_total']:.4f} kg·m/s")
        print(f"  Post-collision momentum:   {summary['post_p_total']:.4f} kg·m/s")
        print(f"  Momentum conservation err: {summary['momentum_error_pct']:.3f} %")
        print(f"  KE loss:                   {summary['ke_loss_pct']:.2f} %")
        ctype = "elastic" if summary["ke_loss_pct"] < 1.0 else "inelastic"
        print(f"  Collision type:            {ctype} (restitution={summary['restitution']})")
        print("=============================\n")

    def shutdown(self):
        simulation_app.close()


# ---------------------------------------------------------------- CLI ---
def prompt_user_config():
    """Interactive parameter input — press Enter to keep defaults."""
    print("\n=== Momentum Conservation Experiment ===")
    print("Press Enter to keep default values.\n")

    def ask(prompt, default):
        val = input(f"  {prompt} [default {default}]: ").strip()
        return float(val) if val else default

    CONFIG["m1"] = ask("Cart 1 mass (kg)", CONFIG["m1"])
    CONFIG["m2"] = ask("Cart 2 mass (kg)", CONFIG["m2"])
    CONFIG["v1_init"] = ask("Cart 1 initial velocity (m/s)", CONFIG["v1_init"])
    CONFIG["v2_init"] = ask("Cart 2 initial velocity (m/s)", CONFIG["v2_init"])
    CONFIG["restitution"] = ask("Restitution (1.0=elastic, 0.0=inelastic)", CONFIG["restitution"])

    dx = abs(CONFIG["cart2_x"] - CONFIG["cart1_x"])
    v_rel = abs(CONFIG["v1_init"] - CONFIG["v2_init"])
    if v_rel > 0:
        CONFIG["sim_time"] = dx / v_rel + 3.0
    else:
        CONFIG["sim_time"] = 6.0

    print(f"\n  m1={CONFIG['m1']} kg, m2={CONFIG['m2']} kg")
    print(f"  v1={CONFIG['v1_init']} m/s, v2={CONFIG['v2_init']} m/s")
    print(f"  restitution={CONFIG['restitution']}, sim_time={CONFIG['sim_time']:.1f} s\n")


def main():
    prompt_user_config()

    expt = MomentumExperiment(CONFIG)
    df = expt.run()
    summary = expt.analyze(df)
    expt.save_plots(df)
    expt.save_data(df, summary)
    expt.print_summary(summary)

    input("Press Enter to close Isaac Sim ...")
    expt.shutdown()


if __name__ == "__main__":
    main()
