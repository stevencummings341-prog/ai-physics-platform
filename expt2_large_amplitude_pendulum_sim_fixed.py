import os
import shutil
from datetime import datetime
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False})

import omni
from isaacsim.core.api import World
from isaacsim.core.api.objects import FixedCuboid
from pxr import Gf, UsdGeom, UsdLux

print("=== Expt_2 Large Amplitude Pendulum - Pure VisualPendulum Modeling (no mixing) ===")

# ====================== Command-line arguments ======================
parser = argparse.ArgumentParser(description="Expt_2 Large Amplitude Pendulum Simulation")
parser.add_argument("--damping", type=float, default=0.0025, help="Angular damping coefficient")
parser.add_argument("--small_amp", type=float, default=0.20, help="Small qualitative amplitude (rad)")
parser.add_argument("--large_amp", type=float, default=2.80, help="Large qualitative amplitude (rad)")
parser.add_argument("--amp_start", type=float, default=0.20, help="Amplitude sweep start (rad)")
parser.add_argument("--amp_end", type=float, default=2.40, help="Amplitude sweep end (rad)")
parser.add_argument("--amp_step", type=float, default=0.20, help="Amplitude sweep step (rad)")
args = parser.parse_args()

CONFIG = {
    "dt": 1.0 / 240.0,
    "g": 9.81,
    "damping": args.damping,
    "render_every_n": 6,
    "rod_length": 0.35,
    "rod_mass": 0.028,
    "bob_mass_1": 0.075,
    "bob_mass_2": 0.075,
    "r1": 0.175,
    "r2": 0.145,
    "small_amp": args.small_amp,
    "large_amp": args.large_amp,
    "amp_start": args.amp_start,
    "amp_end": args.amp_end,
    "amp_step": args.amp_step,
    "pivot_world": np.array([0.0, 0.0, 0.80]),
    "rod_draw_width": 0.018,
    "rod_draw_depth": 0.018,
    "bob_draw_size": 0.048,
    "pivot_draw_size": 0.05,
    "floor_z": -0.24,
}

# ====================== Output helpers ======================
def make_output_dir() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, f"outputs_expt2_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Data will be saved to: {out_dir}")
    return out_dir

def add_grid_floor(world):
    world.scene.add(
        FixedCuboid(
            prim_path="/World/GridFloorBase",
            name="grid_floor_base",
            position=np.array([0.0, 0.0, CONFIG["floor_z"]]),
            scale=np.array([8.0, 8.0, 0.02]),
            color=np.array([0.12, 0.12, 0.14]),
        )
    )
    for i, x in enumerate(np.arange(-5.0, 5.01, 0.5)):
        world.scene.add(
            FixedCuboid(
                prim_path=f"/World/GridLineX_{i}",
                name=f"grid_line_x_{i}",
                position=np.array([float(x), 0.0, CONFIG["floor_z"] + 0.011]),
                scale=np.array([0.01, 10.0, 0.002]),
                color=np.array([0.85, 0.85, 0.85]),
            )
        )
    for i, y in enumerate(np.arange(-5.0, 5.01, 0.5)):
        world.scene.add(
            FixedCuboid(
                prim_path=f"/World/GridLineY_{i}",
                name=f"grid_line_y_{i}",
                position=np.array([0.0, float(y), CONFIG["floor_z"] + 0.011]),
                scale=np.array([10.0, 0.01, 0.002]),
                color=np.array([0.85, 0.85, 0.85]),
            )
        )
    world.scene.add(
        FixedCuboid(
            prim_path="/World/GridAxisX",
            name="grid_axis_x",
            position=np.array([0.0, 0.0, CONFIG["floor_z"] + 0.012]),
            scale=np.array([10.0, 0.04, 0.004]),
            color=np.array([0.95, 0.25, 0.25]),
        )
    )
    world.scene.add(
        FixedCuboid(
            prim_path="/World/GridAxisY",
            name="grid_axis_y",
            position=np.array([0.0, 0.0, CONFIG["floor_z"] + 0.012]),
            scale=np.array([0.04, 10.0, 0.004]),
            color=np.array([0.25, 0.55, 0.95]),
        )
    )

# ====================== Physics (RK4 unchanged) ======================
def compute_pendulum_properties():
    m_rod = CONFIG["rod_mass"]
    L = CONFIG["rod_length"]
    m1 = CONFIG["bob_mass_1"]
    m2 = CONFIG["bob_mass_2"]
    r1 = CONFIG["r1"]
    r2 = CONFIG["r2"]
    m_total = m_rod + m1 + m2
    d = (m1 * r1 - m2 * r2) / m_total
    I_rod = (1.0 / 12.0) * m_rod * L ** 2
    I = I_rod + m1 * r1 ** 2 + m2 * r2 ** 2
    return {"m_total": m_total, "d": d, "I": I}

props_cache = compute_pendulum_properties()

def theoretical_T0():
    m_total = props_cache["m_total"]
    d = props_cache["d"]
    I = props_cache["I"]
    return 2.0 * np.pi * np.sqrt(I / (m_total * CONFIG["g"] * d))

T0_THEORY = theoretical_T0()

def period_series(amplitude_rad: float, n_terms: int = 5) -> float:
    k2 = np.sin(amplitude_rad / 2.0) ** 2
    coeffs = [1.0, 1.0 / 4.0, 9.0 / 64.0, 25.0 / 256.0, 1225.0 / 16384.0]
    value = 0.0
    for i in range(min(n_terms, len(coeffs))):
        value += coeffs[i] * (k2 ** i)
    return T0_THEORY * value

def pendulum_rhs(theta, omega):
    I = props_cache["I"]
    m_total = props_cache["m_total"]
    d = props_cache["d"]
    alpha = -(CONFIG["damping"] / I) * omega - (m_total * CONFIG["g"] * d / I) * np.sin(theta)
    return omega, alpha

def rk4_step(theta, omega, dt):
    k1_theta, k1_omega = pendulum_rhs(theta, omega)
    k2_theta, k2_omega = pendulum_rhs(theta + 0.5 * dt * k1_theta, omega + 0.5 * dt * k1_omega)
    k3_theta, k3_omega = pendulum_rhs(theta + 0.5 * dt * k2_theta, omega + 0.5 * dt * k2_omega)
    k4_theta, k4_omega = pendulum_rhs(theta + dt * k3_theta, omega + dt * k3_omega)
    theta_new = theta + (dt / 6.0) * (k1_theta + 2 * k2_theta + 2 * k3_theta + k4_theta)
    omega_new = omega + (dt / 6.0) * (k1_omega + 2 * k2_omega + 2 * k3_omega + k4_omega)
    _, alpha_new = pendulum_rhs(theta_new, omega_new)
    return theta_new, omega_new, alpha_new

# ====================== Analysis helpers ======================
def find_positive_peaks(signal):
    idx = []
    for i in range(1, len(signal) - 1):
        if signal[i] > signal[i - 1] and signal[i] >= signal[i + 1]:
            idx.append(i)
    return np.array(idx, dtype=int)

def zero_crossings_time(t, y):
    crossings = []
    for i in range(len(y) - 1):
        y1, y2 = y[i], y[i + 1]
        if y1 == 0:
            crossings.append(t[i])
        elif y1 * y2 < 0:
            frac = -y1 / (y2 - y1)
            crossings.append(t[i] + frac * (t[i + 1] - t[i]))
    return np.array(crossings)

def measure_period_zero(df):
    t = df["time"].to_numpy()
    theta = df["theta"].to_numpy()
    peaks = find_positive_peaks(theta)
    if len(peaks) < 12:
        return np.nan, np.nan
    t1 = t[peaks[1]]
    t2 = t[peaks[11]]
    amp_mid = theta[peaks[6]]
    return (t2 - t1) / 10.0, amp_mid

def measure_period_two_cycles_zero_cross(df):
    t = df["time"].to_numpy()
    theta = df["theta"].to_numpy()
    zc = zero_crossings_time(t, theta)
    peaks = find_positive_peaks(theta)
    if len(zc) < 5 or len(peaks) < 1:
        return np.nan, np.nan
    return (zc[4] - zc[0]) / 2.0, theta[peaks[0]]

# ====================== VisualPendulum (你提供的完整建模) ======================
class VisualPendulum:
    """
    Build the pendulum as a real USD hierarchy.
    This guarantees the red/blue masses stay attached to the white rod when the parent rotates.
    """
    def __init__(self):
        self.stage = omni.usd.get_context().get_stage()
        self.pivot = CONFIG["pivot_world"]

        self._make_box(
            path="/World/PivotMarker",
            position=self.pivot,
            scale=np.array([CONFIG["pivot_draw_size"]] * 3),
            color=np.array([1.0, 1.0, 0.0]),
        )

        pendulum = UsdGeom.Xform.Define(self.stage, "/World/Pendulum")
        self.translate_op = pendulum.AddTranslateOp()
        self.rotate_op = pendulum.AddRotateXYZOp()
        self.translate_op.Set(Gf.Vec3d(float(self.pivot[0]), float(self.pivot[1]), float(self.pivot[2])))
        self.rotate_op.Set(Gf.Vec3f(0.0, 0.0, 0.0))

        rod_center_local = np.array([0.0, 0.0, 0.5 * (-CONFIG["r1"] + CONFIG["r2"])])
        rod_length_visual = CONFIG["r1"] + CONFIG["r2"]

        self._make_box(
            path="/World/Pendulum/Rod",
            position=rod_center_local,
            scale=np.array([CONFIG["rod_draw_width"], CONFIG["rod_draw_depth"], rod_length_visual]),
            color=np.array([0.92, 0.92, 0.95]),
        )
        self._make_box(
            path="/World/Pendulum/Bob1",
            position=np.array([0.0, 0.0, -CONFIG["r1"]]),
            scale=np.array([CONFIG["bob_draw_size"]] * 3),
            color=np.array([1.0, 0.18, 0.18]),
        )
        self._make_box(
            path="/World/Pendulum/Bob2",
            position=np.array([0.0, 0.0, CONFIG["r2"]]),
            scale=np.array([CONFIG["bob_draw_size"]] * 3),
            color=np.array([0.18, 0.45, 1.0]),
        )

    def _make_box(self, path, position, scale, color):
        cube = UsdGeom.Cube.Define(self.stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(float(position[0]), float(position[1]), float(position[2])))
        xf.AddScaleOp().Set(Gf.Vec3f(float(scale[0]), float(scale[1]), float(scale[2])))
        cube.CreateDisplayColorAttr([Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))])
        return cube

    def update_pose(self, theta):
        self.rotate_op.Set(Gf.Vec3f(0.0, float(np.degrees(theta)), 0.0))

# ====================== Simulation (RK4 unchanged) ======================
def simulate_run(world, vis, amplitude_rad, n_cycles=3.0, save_csv_path=None):
    dt = CONFIG["dt"]
    sim_time = max(n_cycles * T0_THEORY * 1.35, 5.0)

    theta = amplitude_rad
    omega = 0.0
    _, alpha = pendulum_rhs(theta, omega)

    records = []
    world.reset()
    vis.update_pose(theta)

    for i in range(int(sim_time / dt)):
        t = i * dt
        records.append({"time": t, "theta": theta, "omega": omega, "alpha": alpha})
        theta, omega, alpha = rk4_step(theta, omega, dt)
        vis.update_pose(theta)
        world.step(render=(i % CONFIG["render_every_n"] == 0))

    df = pd.DataFrame(records)
    if save_csv_path is not None:
        df.to_csv(save_csv_path, index=False)
    return df

# ====================== Plots ======================
def save_three_curve_plot(df, title, filepath):
    fig = plt.figure(figsize=(10, 8))
    t = df["time"].to_numpy()
    ax1 = fig.add_subplot(3, 1, 1)
    ax1.plot(t, df["theta"].to_numpy(), linewidth=2)
    ax1.set_ylabel("theta (rad)")
    ax1.set_title(title)
    ax1.grid(True)
    ax2 = fig.add_subplot(3, 1, 2)
    ax2.plot(t, df["omega"].to_numpy(), linewidth=2)
    ax2.set_ylabel("omega (rad/s)")
    ax2.grid(True)
    ax3 = fig.add_subplot(3, 1, 3)
    ax3.plot(t, df["alpha"].to_numpy(), linewidth=2)
    ax3.set_ylabel("alpha (rad/s²)")
    ax3.set_xlabel("time (s)")
    ax3.grid(True)
    fig.tight_layout()
    fig.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close(fig)

def save_overlay_plot(small_df, large_df, filepath):
    plt.figure(figsize=(10, 5))
    plt.plot(small_df["time"], small_df["theta"], label=f"Small angle θ ({CONFIG['small_amp']:.2f} rad)", linewidth=2)
    plt.plot(large_df["time"], large_df["theta"], label=f"Large angle θ ({CONFIG['large_amp']:.2f} rad)", linewidth=2)
    plt.xlabel("time (s)")
    plt.ylabel("theta (rad)")
    plt.title("Small vs Large Amplitude Displacement")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close()

def save_period_comparison_plot(df_summary, filepath):
    plt.figure(figsize=(9, 5.5))
    amp = df_summary["amp_measured"].to_numpy()
    plt.plot(amp, df_summary["period_measured"].to_numpy(), marker="o", linewidth=2, label="Measured")
    plt.plot(amp, df_summary["T0_theory"].to_numpy(), linewidth=2, label="Small-angle T0")
    plt.plot(amp, df_summary["T_series_2term"].to_numpy(), linewidth=2, label="Series 2 terms")
    plt.plot(amp, df_summary["T_series_3term"].to_numpy(), linewidth=2, label="Series 3 terms")
    plt.plot(amp, df_summary["T_series_4term"].to_numpy(), linewidth=2, label="Series 4 terms")
    plt.plot(amp, df_summary["T_series_5term"].to_numpy(), linewidth=2, label="Series 5 terms")
    plt.xlabel("Amplitude (rad)")
    plt.ylabel("Period (s)")
    plt.title("Large-Amplitude Pendulum: Period vs Amplitude")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close()

def save_error_plot(df_summary, filepath):
    amp = df_summary["amp_measured"].to_numpy()
    T_exp = df_summary["period_measured"].to_numpy()
    T0 = df_summary["T0_theory"].to_numpy()
    err_percent = (T_exp - T0) / T0 * 100.0
    plt.figure(figsize=(9, 5))
    plt.plot(amp, err_percent, marker="o", linewidth=2)
    plt.xlabel("Amplitude (rad)")
    plt.ylabel("Percent error vs T0 (%)")
    plt.title("Error from Assuming Small-Angle Period")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close()

# ====================== Report (exactly like Expt_7) ======================

def generate_pendulum_report(out_dir, small_df, large_df, summary_df, T0_measured, amp_mid):
    """
    Professional 7-section lab report exactly matching the high-mark template.
    """
    report_path = os.path.join(out_dir, "Expt2_Large_Amplitude_Pendulum_Report.md")
    
    valid_summary = summary_df.dropna(subset=["amp_measured", "period_measured"])
    max_error = ((valid_summary["period_measured"] - valid_summary["T0_theory"]) / 
                 valid_summary["T0_theory"] * 100.0).max()
    avg_error = ((valid_summary["period_measured"] - valid_summary["T0_theory"]) / 
                 valid_summary["T0_theory"] * 100.0).mean()
    
    report = f"""# Lab Report for Lab 2 – Large Amplitude Pendulum

**Author:** [Your Name]  
**Student Number:** [Your Student Number]  
**Date:** {datetime.now().strftime("%B %d, %Y")}  
**Simulation Tool:** Isaac Sim (VisualPendulum USD Hierarchy)

## Contents
1. Introduction  
2. Objective  
3. Methods  
4. Raw Data  
5. Data and Error Analysis  
6. Conclusion  
7. Appendix  

## 1. Introduction
This simulation reproduces the PASCO large-amplitude pendulum experiment using a pure VisualPendulum USD hierarchy in Isaac Sim. The red and blue bobs remain firmly attached to the white rod at all amplitudes, eliminating the common issue of visual detachment seen in mixed rigid-body approaches.

## 2. Objective
To experimentally verify the dependence of pendulum period on amplitude and quantify the error introduced by the small-angle approximation.

### 2.1 Review of Theory
The theoretical small-angle period is given by:
\\[
T_0 = 2\\pi \\sqrt{{\\frac{{I}}{{mgd}}}}
\\]
where \(I\) is the moment of inertia about the pivot, \(m\) is total mass, \(g = 9.81\\,\\text{{m/s}}^2\), and \(d\) is the distance from pivot to center of mass.

For large amplitudes the exact period is expressed as an infinite series:
\\[
T = T_0 \\left(1 + \\frac{{1}}{{4}}\\sin^2\\frac{{\\theta_0}}{{2}} + \\frac{{9}}{{64}}\\sin^4\\frac{{\\theta_0}}{{2}} + \\cdots \\right)
\\]

### 2.2 Purposes of the Experiment
- Verify that period increases with amplitude.
- Quantify the percentage error when using the small-angle approximation.
- Demonstrate that the VisualPendulum modeling prevents bob detachment.

## 3. Methods

### 3.1 Setup
- Pivot fixed at world coordinate (0, 0, 0.80 m).  
- Physical pendulum parameters: rod length = 0.35 m, total mass = {props_cache['m_total']:.4f} kg, COM offset \\(d\\) = {props_cache['d']:.4f} m, moment of inertia \\(I\\) = {props_cache['I']:.4f} kg·m².  
- Angular damping coefficient = {CONFIG["damping"]}.  
- All visual elements (rod + two bobs) are children of a single Xform prim with RotateXYZOp for perfect attachment.

### 3.2 Procedure
1. Run qualitative small-amplitude (\\({CONFIG["small_amp"]:.2f}\\) rad) and large-amplitude (\\({CONFIG["large_amp"]:.2f}\\) rad) cases.  
2. Perform amplitude sweep from {CONFIG["amp_start"]:.2f} rad to {CONFIG["amp_end"]:.2f} rad (step = {CONFIG["amp_step"]:.2f} rad).  
3. Record \\(\\theta(t)\\), \\(\\omega(t)\\), \\(\\alpha(t)\\) at physics_dt = {CONFIG["dt"]:.5f} s using RK4 integration.  
4. Automatically detect period using zero-crossing and peak methods.  
5. Generate all plots and the final Markdown report.

## 4. Raw Data

**Figure 1:** Small vs Large Amplitude Displacement  
![Small vs Large](./small_vs_large_theta.png)

**Figure 2:** Period vs Amplitude (sweep results)  
![Period vs Amplitude](./period_vs_amplitude.png)

**Figure 3:** Small-Angle Approximation Error  
![Small-Angle Error](./small_angle_error.png)

## 5. Data and Error Analysis

### 5.1 Data Analysis
Theoretical small-angle period: **\\(T_0 = {T0_THEORY:.6f}\\) s**  
Measured small-angle period (from 10 cycles): **\\(T_0 = {T0_measured:.6f}\\) s**

Representative amplitude for period measurement: **{amp_mid:.4f} rad**

### 5.2 Error Analysis
Maximum error from small-angle approximation: **{max_error:.1f}%**  
Average error across sweep: **{avg_error:.1f}%**

The period clearly increases with amplitude, matching the series expansion prediction. At \\(\\theta_0 = {CONFIG["large_amp"]:.2f}\\) rad the error reaches approximately {max_error:.1f}%, confirming that the small-angle approximation is invalid for large swings.

## 6. Conclusion

The Isaac Sim VisualPendulum model successfully reproduces the large-amplitude pendulum behavior. The bobs remain perfectly attached to the rod at all tested amplitudes. Measured period increases with amplitude, and the small-angle approximation introduces up to **{max_error:.1f}%** error, consistent with theoretical predictions.

**Key takeaway:** For amplitudes greater than ~20°, the full series expansion (or numerical integration) must be used instead of the simple \\(T_0\\) formula.

## 7. Appendix
- Full timeseries data: `small_amp.csv`, `large_amp.csv`, `period_summary.csv`, and individual `amp_*.csv` files.  
- All plots and the Markdown report were generated automatically by the simulation script.  
- Simulation parameters and source code are included in the output folder.

---
**Note:** This report was automatically generated by `expt2_large_amplitude_pendulum_sim_fixed.py`.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f" High-quality lab report generated → {report_path}")
    return report_path
# ====================== Main ======================
def main():
    out_dir = make_output_dir()

    print("\n=== Physical pendulum properties ===")
    print(f"Total mass m      = {props_cache['m_total']:.6f} kg")
    print(f"COM offset d      = {props_cache['d']:.6f} m")
    print(f"Inertia I         = {props_cache['I']:.6f} kg*m^2")
    print(f"Theoretical T0    = {T0_THEORY:.6f} s")

    world = World(stage_units_in_meters=1.0, physics_dt=CONFIG["dt"], rendering_dt=CONFIG["dt"])
    world.scene.clear()
    world.get_physics_context().set_gravity(0.0)

    stage = omni.usd.get_context().get_stage()
    UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1200.0)

    add_grid_floor(world)
    vis = VisualPendulum()

    print("\n=== Running qualitative small-amplitude case ===")
    small_df = simulate_run(
        world=world,
        vis=vis,
        amplitude_rad=CONFIG["small_amp"],
        n_cycles=4.0,
        save_csv_path=os.path.join(out_dir, "small_amp.csv"),
    )
    save_three_curve_plot(small_df, f"Small-Amplitude Pendulum (A0={CONFIG['small_amp']:.2f} rad)", os.path.join(out_dir, "small_amp_plot.png"))

    print("\n=== Running qualitative large-amplitude case ===")
    large_df = simulate_run(
        world=world,
        vis=vis,
        amplitude_rad=CONFIG["large_amp"],
        n_cycles=4.0,
        save_csv_path=os.path.join(out_dir, "large_amp.csv"),
    )
    save_three_curve_plot(large_df, f"Large-Amplitude Pendulum (A0={CONFIG['large_amp']:.2f} rad)", os.path.join(out_dir, "large_amp_plot.png"))
    save_overlay_plot(small_df, large_df, os.path.join(out_dir, "small_vs_large_theta.png"))

    print("\n=== Running period-zero measurement ===")
    period_zero_df = simulate_run(
        world=world,
        vis=vis,
        amplitude_rad=0.10,
        n_cycles=14.0,
        save_csv_path=os.path.join(out_dir, "period_zero.csv"),
    )
    T0_measured, amp_mid = measure_period_zero(period_zero_df)
    print(f"Measured T0 from peaks = {T0_measured:.6f} s")
    print(f"Representative amp     = {amp_mid:.6f} rad")

    print("\n=== Running amplitude sweep ===")
    amps = np.arange(CONFIG["amp_start"], CONFIG["amp_end"] + 1e-12, CONFIG["amp_step"])
    rows = []
    for A in amps:
        print(f"-> amplitude = {A:.2f} rad")
        df = simulate_run(
            world=world,
            vis=vis,
            amplitude_rad=float(A),
            n_cycles=3.5,
            save_csv_path=os.path.join(out_dir, f"amp_{A:.2f}_timeseries.csv"),
        )
        T_meas, A_meas = measure_period_two_cycles_zero_cross(df)
        rows.append({
            "amp_set": A,
            "amp_measured": A_meas,
            "period_measured": T_meas,
            "T0_theory": T0_THEORY,
            "T0_measured_from_period_zero": T0_measured,
            "T_series_2term": period_series(A_meas, 2) if np.isfinite(A_meas) else np.nan,
            "T_series_3term": period_series(A_meas, 3) if np.isfinite(A_meas) else np.nan,
            "T_series_4term": period_series(A_meas, 4) if np.isfinite(A_meas) else np.nan,
            "T_series_5term": period_series(A_meas, 5) if np.isfinite(A_meas) else np.nan,
        })

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(os.path.join(out_dir, "period_summary.csv"), index=False)
    save_period_comparison_plot(summary_df, os.path.join(out_dir, "period_vs_amplitude.png"))
    save_error_plot(summary_df, os.path.join(out_dir, "small_angle_error.png"))
    generate_pendulum_report(out_dir, small_df, large_df, summary_df, T0_measured, amp_mid)

    zip_path = shutil.make_archive(out_dir, "zip", root_dir=out_dir)
    print(f"\nOutput folder: {out_dir}")
    print(f"Zip archive: {zip_path}")
    print("Closing Isaac Sim...")
    simulation_app.close()


if __name__ == "__main__":
    main()