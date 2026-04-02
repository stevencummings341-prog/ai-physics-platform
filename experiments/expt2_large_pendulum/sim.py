"""Experiment 2 — Large Amplitude Pendulum.

Ported from classmate's standalone simulation into the ExperimentBase
framework.  Uses RK4 integration for a physical compound pendulum
with two bobs.  Isaac Sim provides the visual rendering only (gravity=0,
no PhysX joints); the physics is entirely Python-side for maximum accuracy
at large angles.

Key outputs:
  - Qualitative: small-amp vs large-amp overlay plot
  - Quantitative: period vs amplitude sweep with series-expansion comparison
  - Lab report in Markdown
"""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from isaacsim import SimulationApp

log = logging.getLogger(__name__)

_app: SimulationApp | None = None


def _get_app(cfg: dict) -> SimulationApp:
    global _app
    if _app is None:
        _app = SimulationApp({"headless": cfg.get("headless", False)})
    return _app


from core.experiment_base import ExperimentBase
from core.exp2_analysis import (
    compute_pendulum_properties, theoretical_T0, period_series,
    pendulum_rhs, rk4_step, simulate_pure_rk4,
    find_positive_peaks, zero_crossings_time,
    measure_period_zero, measure_period_two_cycles_zero_cross,
    save_three_curve_plot, save_overlay_plot,
    save_period_comparison_plot, save_error_plot,
    generate_pendulum_report,
)

_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.yaml")


# ═══════════════════════════════════════════════════════════════════
# Experiment class
# ═══════════════════════════════════════════════════════════════════

class Experiment(ExperimentBase):
    name = "expt2_large_pendulum"

    def __init__(self, config_path: str | None = None, overrides: dict | None = None):
        if config_path is None:
            config_path = _DEFAULT_CONFIG
        super().__init__(config_path, overrides)
        self.props = compute_pendulum_properties(self.cfg)
        self.T0 = theoretical_T0(self.props, self.cfg.get("g", 9.81))
        self.vis = None
        self._sim_app = None

    def build_scene(self) -> None:
        self._sim_app = _get_app(self.cfg)

        import omni
        from isaacsim.core.api import World
        from pxr import Gf, UsdGeom, UsdLux

        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=self.cfg.get("physics_dt", 1.0 / 240.0),
            rendering_dt=self.cfg.get("physics_dt", 1.0 / 240.0),
        )
        self.world.scene.clear()
        self.world.get_physics_context().set_gravity(0.0)

        stage = omni.usd.get_context().get_stage()
        UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1200.0)

        self._add_grid_floor(stage)
        self.vis = _VisualPendulum(stage, self.cfg)

    def apply_initial_conditions(self) -> None:
        pass

    def step_callback(self, step: int, t: float) -> dict:
        return {}

    def analyze(self, df: pd.DataFrame) -> dict:
        return {}

    def plot(self, df: pd.DataFrame) -> None:
        pass

    def shutdown(self) -> None:
        if self._sim_app is not None:
            self._sim_app.close()

    # ── Override execute to run the full multi-phase experiment ──

    def execute(self) -> dict:
        self.setup()
        cfg = self.cfg
        dt = cfg.get("physics_dt", 1.0 / 240.0)
        g = cfg.get("g", 9.81)

        log.info("Physical pendulum: m=%.4f kg, d=%.4f m, I=%.6f kg·m², T0=%.6f s",
                 self.props["m_total"], self.props["d"], self.props["I"], self.T0)

        # Phase 1: Qualitative small amplitude
        log.info("Qualitative small-amplitude run (A=%.2f rad)", cfg["small_amp"])
        small_df = self._simulate_run(cfg["small_amp"], cfg.get("qualitative_cycles", 4.0))
        small_df.to_csv(os.path.join(self.out_dir, "small_amp.csv"), index=False)
        save_three_curve_plot(small_df,
                              f"Small-Amplitude (A₀={cfg['small_amp']:.2f} rad)",
                              os.path.join(self.out_dir, "small_amp_plot.png"))

        # Phase 2: Qualitative large amplitude
        log.info("Qualitative large-amplitude run (A=%.2f rad)", cfg["large_amp"])
        large_df = self._simulate_run(cfg["large_amp"], cfg.get("qualitative_cycles", 4.0))
        large_df.to_csv(os.path.join(self.out_dir, "large_amp.csv"), index=False)
        save_three_curve_plot(large_df,
                              f"Large-Amplitude (A₀={cfg['large_amp']:.2f} rad)",
                              os.path.join(self.out_dir, "large_amp_plot.png"))
        save_overlay_plot(small_df, large_df, cfg["small_amp"], cfg["large_amp"],
                          os.path.join(self.out_dir, "small_vs_large_theta.png"))

        # Phase 3: Period-zero measurement
        pz_amp = cfg.get("period_zero_amp", 0.10)
        pz_cycles = cfg.get("period_zero_cycles", 14.0)
        log.info("Period-zero measurement (A=%.2f rad, %d cycles)", pz_amp, pz_cycles)
        pz_df = self._simulate_run(pz_amp, pz_cycles)
        pz_df.to_csv(os.path.join(self.out_dir, "period_zero.csv"), index=False)
        T0_measured, amp_mid = measure_period_zero(pz_df)
        log.info("Measured T0 = %.6f s (theory = %.6f s)", T0_measured, self.T0)

        # Phase 4: Amplitude sweep
        log.info("Amplitude sweep %.2f → %.2f rad (step %.2f)",
                 cfg["amp_start"], cfg["amp_end"], cfg["amp_step"])
        amps = np.arange(cfg["amp_start"], cfg["amp_end"] + 1e-12, cfg["amp_step"])
        rows = []
        for A in amps:
            log.info("  → amplitude = %.2f rad", A)
            df = self._simulate_run(float(A), cfg.get("sweep_cycles", 3.5))
            df.to_csv(os.path.join(self.out_dir, f"amp_{A:.2f}_timeseries.csv"), index=False)
            T_meas, A_meas = measure_period_two_cycles_zero_cross(df)
            rows.append({
                "amp_set": A,
                "amp_measured": A_meas,
                "period_measured": T_meas,
                "T0_theory": self.T0,
                "T0_measured": T0_measured,
                "T_series_2term": period_series(self.T0, A_meas, 2) if np.isfinite(A_meas) else np.nan,
                "T_series_3term": period_series(self.T0, A_meas, 3) if np.isfinite(A_meas) else np.nan,
                "T_series_4term": period_series(self.T0, A_meas, 4) if np.isfinite(A_meas) else np.nan,
                "T_series_5term": period_series(self.T0, A_meas, 5) if np.isfinite(A_meas) else np.nan,
            })

        summary_df = pd.DataFrame(rows)
        summary_df.to_csv(os.path.join(self.out_dir, "period_summary.csv"), index=False)
        save_period_comparison_plot(summary_df,
                                    os.path.join(self.out_dir, "period_vs_amplitude.png"))
        save_error_plot(summary_df, os.path.join(self.out_dir, "small_angle_error.png"))

        report_path = generate_pendulum_report(
            self.out_dir, self.props, self.T0,
            cfg.get("damping", 0.0025),
            cfg["small_amp"], cfg["large_amp"],
            cfg["amp_start"], cfg["amp_end"], cfg["amp_step"],
            cfg.get("physics_dt", 1.0 / 240.0),
            summary_df, T0_measured, amp_mid,
        )

        summary = {
            "T0_theory": self.T0,
            "T0_measured": T0_measured,
            "amp_mid": amp_mid,
            "sweep_points": len(rows),
            "report": report_path,
        }
        return summary

    def print_summary(self, summary: dict) -> None:
        print("\n========== Experiment 2: Large Amplitude Pendulum ==========")
        print(f"  m_total:          {self.props['m_total']:.4f} kg")
        print(f"  COM offset d:     {self.props['d']:.4f} m")
        print(f"  Inertia I:        {self.props['I']:.6f} kg·m²")
        print(f"  T₀ (theory):      {summary.get('T0_theory', 0):.6f} s")
        print(f"  T₀ (measured):    {summary.get('T0_measured', 0):.6f} s")
        print(f"  Sweep points:     {summary.get('sweep_points', 0)}")
        print(f"  Report:           {summary.get('report', 'N/A')}")
        print("=" * 56)

    # ── Simulation driver ──

    def _simulate_run(self, amplitude_rad: float, n_cycles: float) -> pd.DataFrame:
        cfg = self.cfg
        dt = cfg.get("physics_dt", 1.0 / 240.0)
        g = cfg.get("g", 9.81)
        damping = cfg.get("damping", 0.0025)
        render_n = cfg.get("render_every_n", 6)
        sim_time = max(n_cycles * self.T0 * 1.35, 5.0)

        theta = amplitude_rad
        omega = 0.0
        _, alpha = pendulum_rhs(theta, omega, self.props, damping, g)

        records = []
        self.world.reset()
        if self.vis:
            self.vis.update_pose(theta)

        for i in range(int(sim_time / dt)):
            t = i * dt
            records.append({"time": t, "theta": theta, "omega": omega, "alpha": alpha})
            theta, omega, alpha = rk4_step(theta, omega, dt, self.props, damping, g)
            if self.vis:
                self.vis.update_pose(theta)
            self.world.step(render=(i % render_n == 0))

        return pd.DataFrame(records)

    # ── Grid floor ──

    def _add_grid_floor(self, stage):
        from isaacsim.core.api.objects import FixedCuboid
        fz = self.cfg.get("floor_z", -0.24)
        self.world.scene.add(FixedCuboid(
            prim_path="/World/GridFloorBase", name="grid_floor_base",
            position=np.array([0.0, 0.0, fz]),
            scale=np.array([8.0, 8.0, 0.02]),
            color=np.array([0.12, 0.12, 0.14]),
        ))
        for i, x in enumerate(np.arange(-5.0, 5.01, 0.5)):
            self.world.scene.add(FixedCuboid(
                prim_path=f"/World/GridLineX_{i}", name=f"grid_line_x_{i}",
                position=np.array([float(x), 0.0, fz + 0.011]),
                scale=np.array([0.01, 10.0, 0.002]),
                color=np.array([0.85, 0.85, 0.85]),
            ))
        for i, y in enumerate(np.arange(-5.0, 5.01, 0.5)):
            self.world.scene.add(FixedCuboid(
                prim_path=f"/World/GridLineY_{i}", name=f"grid_line_y_{i}",
                position=np.array([0.0, float(y), fz + 0.011]),
                scale=np.array([10.0, 0.01, 0.002]),
                color=np.array([0.85, 0.85, 0.85]),
            ))

    


# ═══════════════════════════════════════════════════════════════════
# Visual pendulum (USD hierarchy for Isaac Sim rendering)
# ═══════════════════════════════════════════════════════════════════

class _VisualPendulum:
    """Compound pendulum built as a USD Xform hierarchy so all parts
    rotate together when the parent Xform is updated."""

    def __init__(self, stage, cfg: dict):
        from pxr import Gf, UsdGeom

        pv = cfg.get("pivot_world", [0, 0, 0.80])
        r1 = cfg["r1"]
        r2 = cfg["r2"]

        self._make_box(stage, "/World/PivotMarker",
                        position=pv,
                        scale=[cfg.get("pivot_draw_size", 0.05)] * 3,
                        color=[1.0, 1.0, 0.0])

        pendulum = UsdGeom.Xform.Define(stage, "/World/Pendulum")
        self._translate_op = pendulum.AddTranslateOp()
        self._rotate_op = pendulum.AddRotateXYZOp()
        self._translate_op.Set(Gf.Vec3d(float(pv[0]), float(pv[1]), float(pv[2])))
        self._rotate_op.Set(Gf.Vec3f(0, 0, 0))

        rod_center_z = 0.5 * (-r1 + r2)
        rod_vis_len = r1 + r2
        self._make_box(stage, "/World/Pendulum/Rod",
                        position=[0, 0, rod_center_z],
                        scale=[cfg.get("rod_draw_width", 0.018),
                               cfg.get("rod_draw_depth", 0.018),
                               rod_vis_len],
                        color=[0.92, 0.92, 0.95])

        self._make_box(stage, "/World/Pendulum/Bob1",
                        position=[0, 0, -r1],
                        scale=[cfg.get("bob_draw_size", 0.048)] * 3,
                        color=[1.0, 0.18, 0.18])

        self._make_box(stage, "/World/Pendulum/Bob2",
                        position=[0, 0, r2],
                        scale=[cfg.get("bob_draw_size", 0.048)] * 3,
                        color=[0.18, 0.45, 1.0])

    @staticmethod
    def _make_box(stage, path, position, scale, color):
        from pxr import Gf, UsdGeom
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*[float(v) for v in position]))
        xf.AddScaleOp().Set(Gf.Vec3f(*[float(v) for v in scale]))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*[float(v) for v in color])])

    def update_pose(self, theta: float):
        from pxr import Gf
        self._rotate_op.Set(Gf.Vec3f(0.0, float(np.degrees(theta)), 0.0))
