"""Experiment 2 — Large Amplitude Pendulum: analysis, plots, and report.

Shared between the web interactive server (core/webrtc_server.py) and the
batch CLI mode (experiments/expt2_large_pendulum/sim.py).  All functions
are pure Python — no Isaac Sim dependency.

Ported faithfully from the classmate's expt2_large_amplitude_pendulum_sim_fixed.py.
"""

from __future__ import annotations

import math
import os
import shutil
from datetime import datetime

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ═══════════════════════════════════════════════════════════════════
# Physics
# ═══════════════════════════════════════════════════════════════════

def compute_pendulum_properties(cfg: dict) -> dict:
    m_rod = cfg.get("rod_mass", 0.028)
    L = cfg.get("rod_length", 0.35)
    m1 = cfg.get("bob_mass_1", 0.075)
    m2 = cfg.get("bob_mass_2", 0.075)
    r1 = cfg.get("r1", 0.175)
    r2 = cfg.get("r2", 0.145)
    m_total = m_rod + m1 + m2
    d = (m1 * r1 - m2 * r2) / m_total
    I_rod = (1.0 / 12.0) * m_rod * L ** 2
    I = I_rod + m1 * r1 ** 2 + m2 * r2 ** 2
    return {"m_total": m_total, "d": d, "I": I}


def theoretical_T0(props: dict, g: float = 9.81) -> float:
    return 2.0 * math.pi * math.sqrt(props["I"] / (props["m_total"] * g * props["d"]))


def period_series(T0: float, amplitude_rad: float, n_terms: int = 5) -> float:
    k2 = math.sin(amplitude_rad / 2.0) ** 2
    coeffs = [1.0, 1.0 / 4.0, 9.0 / 64.0, 25.0 / 256.0, 1225.0 / 16384.0]
    value = sum(coeffs[i] * (k2 ** i) for i in range(min(n_terms, len(coeffs))))
    return T0 * value


def pendulum_rhs(theta: float, omega: float, props: dict, damping: float, g: float = 9.81):
    I = props["I"]
    m_total = props["m_total"]
    d = props["d"]
    alpha = -(damping / I) * omega - (m_total * g * d / I) * math.sin(theta)
    return omega, alpha


def rk4_step(theta, omega, dt, props, damping, g=9.81):
    k1t, k1o = pendulum_rhs(theta, omega, props, damping, g)
    k2t, k2o = pendulum_rhs(theta + 0.5 * dt * k1t, omega + 0.5 * dt * k1o, props, damping, g)
    k3t, k3o = pendulum_rhs(theta + 0.5 * dt * k2t, omega + 0.5 * dt * k2o, props, damping, g)
    k4t, k4o = pendulum_rhs(theta + dt * k3t, omega + dt * k3o, props, damping, g)
    theta_new = theta + (dt / 6.0) * (k1t + 2 * k2t + 2 * k3t + k4t)
    omega_new = omega + (dt / 6.0) * (k1o + 2 * k2o + 2 * k3o + k4o)
    _, alpha_new = pendulum_rhs(theta_new, omega_new, props, damping, g)
    return theta_new, omega_new, alpha_new


def simulate_pure_rk4(props: dict, amplitude_rad: float, damping: float,
                       dt: float = 1.0 / 240.0, n_cycles: float = 3.0,
                       T0: float = 1.0, g: float = 9.81) -> pd.DataFrame:
    """Run a pure-Python RK4 simulation (no Isaac Sim).  Returns DataFrame."""
    sim_time = max(n_cycles * T0 * 1.35, 5.0)
    theta = amplitude_rad
    omega = 0.0
    _, alpha = pendulum_rhs(theta, omega, props, damping, g)

    records = []
    for i in range(int(sim_time / dt)):
        t = i * dt
        records.append({"time": t, "theta": theta, "omega": omega, "alpha": alpha})
        theta, omega, alpha = rk4_step(theta, omega, dt, props, damping, g)

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════
# Analysis helpers
# ═══════════════════════════════════════════════════════════════════

def find_positive_peaks(signal):
    idx = []
    for i in range(1, len(signal) - 1):
        if signal[i] > signal[i - 1] and signal[i] >= signal[i + 1]:
            idx.append(i)
    return np.array(idx, dtype=int)


def zero_crossings_time(t, y):
    crossings = []
    for i in range(len(y) - 1):
        if y[i] == 0:
            crossings.append(t[i])
        elif y[i] * y[i + 1] < 0:
            frac = -y[i] / (y[i + 1] - y[i])
            crossings.append(t[i] + frac * (t[i + 1] - t[i]))
    return np.array(crossings)


def measure_period_zero(df: pd.DataFrame):
    t = df["time"].to_numpy()
    theta = df["theta"].to_numpy()
    peaks = find_positive_peaks(theta)
    if len(peaks) < 12:
        return np.nan, np.nan
    return (t[peaks[11]] - t[peaks[1]]) / 10.0, theta[peaks[6]]


def measure_period_two_cycles_zero_cross(df: pd.DataFrame):
    t = df["time"].to_numpy()
    theta = df["theta"].to_numpy()
    zc = zero_crossings_time(t, theta)
    peaks = find_positive_peaks(theta)
    if len(zc) < 5 or len(peaks) < 1:
        return np.nan, np.nan
    return (zc[4] - zc[0]) / 2.0, theta[peaks[0]]


# ═══════════════════════════════════════════════════════════════════
# Plot generators  (exact ports from classmate's code)
# ═══════════════════════════════════════════════════════════════════

def save_three_curve_plot(df: pd.DataFrame, title: str, filepath: str):
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


def save_overlay_plot(small_df: pd.DataFrame, large_df: pd.DataFrame,
                      small_amp: float, large_amp: float, filepath: str):
    plt.figure(figsize=(10, 5))
    plt.plot(small_df["time"], small_df["theta"],
             label=f"Small angle θ ({small_amp:.2f} rad)", linewidth=2)
    plt.plot(large_df["time"], large_df["theta"],
             label=f"Large angle θ ({large_amp:.2f} rad)", linewidth=2)
    plt.xlabel("time (s)")
    plt.ylabel("theta (rad)")
    plt.title("Small vs Large Amplitude Displacement")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close()


def save_period_comparison_plot(df_summary: pd.DataFrame, filepath: str):
    plt.figure(figsize=(9, 5.5))
    amp = df_summary["amp_measured"].to_numpy()
    plt.plot(amp, df_summary["period_measured"].to_numpy(),
             marker="o", linewidth=2, label="Measured")
    plt.plot(amp, df_summary["T0_theory"].to_numpy(),
             linewidth=2, label="Small-angle T0")
    plt.plot(amp, df_summary["T_series_2term"].to_numpy(),
             linewidth=2, label="Series 2 terms")
    plt.plot(amp, df_summary["T_series_3term"].to_numpy(),
             linewidth=2, label="Series 3 terms")
    plt.plot(amp, df_summary["T_series_4term"].to_numpy(),
             linewidth=2, label="Series 4 terms")
    plt.plot(amp, df_summary["T_series_5term"].to_numpy(),
             linewidth=2, label="Series 5 terms")
    plt.xlabel("Amplitude (rad)")
    plt.ylabel("Period (s)")
    plt.title("Large-Amplitude Pendulum: Period vs Amplitude")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath, dpi=250, bbox_inches="tight")
    plt.close()


def save_error_plot(df_summary: pd.DataFrame, filepath: str):
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


# ═══════════════════════════════════════════════════════════════════
# Report generator  (exact port from classmate's code)
# ═══════════════════════════════════════════════════════════════════

def generate_pendulum_report(
    out_dir: str,
    props: dict,
    T0_theory: float,
    damping: float,
    small_amp: float,
    large_amp: float,
    amp_start: float,
    amp_end: float,
    amp_step: float,
    dt: float,
    summary_df: pd.DataFrame,
    T0_measured: float,
    amp_mid: float,
) -> str:
    valid_summary = summary_df.dropna(subset=["amp_measured", "period_measured"])
    max_error = ((valid_summary["period_measured"] - valid_summary["T0_theory"])
                 / valid_summary["T0_theory"] * 100.0).max()
    avg_error = ((valid_summary["period_measured"] - valid_summary["T0_theory"])
                 / valid_summary["T0_theory"] * 100.0).mean()

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
where \\(I\\) is the moment of inertia about the pivot, \\(m\\) is total mass, \\(g = 9.81\\,\\text{{m/s}}^2\\), and \\(d\\) is the distance from pivot to center of mass.

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
- Physical pendulum parameters: rod length = 0.35 m, total mass = {props['m_total']:.4f} kg, COM offset \\(d\\) = {props['d']:.4f} m, moment of inertia \\(I\\) = {props['I']:.4f} kg·m².  
- Angular damping coefficient = {damping}.  
- All visual elements (rod + two bobs) are children of a single Xform prim with RotateXYZOp for perfect attachment.

### 3.2 Procedure
1. Run qualitative small-amplitude (\\({small_amp:.2f}\\) rad) and large-amplitude (\\({large_amp:.2f}\\) rad) cases.  
2. Perform amplitude sweep from {amp_start:.2f} rad to {amp_end:.2f} rad (step = {amp_step:.2f} rad).  
3. Record \\(\\theta(t)\\), \\(\\omega(t)\\), \\(\\alpha(t)\\) at physics_dt = {dt:.5f} s using RK4 integration.  
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
Theoretical small-angle period: **\\(T_0 = {T0_theory:.6f}\\) s**  
Measured small-angle period (from 10 cycles): **\\(T_0 = {T0_measured:.6f}\\) s**

Representative amplitude for period measurement: **{amp_mid:.4f} rad**

### 5.2 Error Analysis
Maximum error from small-angle approximation: **{max_error:.1f}%**  
Average error across sweep: **{avg_error:.1f}%**

The period clearly increases with amplitude, matching the series expansion prediction. At \\(\\theta_0 = {large_amp:.2f}\\) rad the error reaches approximately {max_error:.1f}%, confirming that the small-angle approximation is invalid for large swings.

## 6. Conclusion

The Isaac Sim VisualPendulum model successfully reproduces the large-amplitude pendulum behavior. The bobs remain perfectly attached to the rod at all tested amplitudes. Measured period increases with amplitude, and the small-angle approximation introduces up to **{max_error:.1f}%** error, consistent with theoretical predictions.

**Key takeaway:** For amplitudes greater than ~20°, the full series expansion (or numerical integration) must be used instead of the simple \\(T_0\\) formula.

## 7. Appendix
- Full timeseries data: `small_amp.csv`, `large_amp.csv`, `period_summary.csv`, and individual `amp_*.csv` files.  
- All plots and the Markdown report were generated automatically by the simulation script.  
- Simulation parameters and source code are included in the output folder.

---
**Note:** This report was automatically generated by the AI Physics Experiment Platform.
"""
    report_path = os.path.join(out_dir, "Expt2_Large_Amplitude_Pendulum_Report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report_path


# ═══════════════════════════════════════════════════════════════════
# Full experiment pipeline  (runs all phases, generates all outputs)
# ═══════════════════════════════════════════════════════════════════

def run_full_experiment(
    out_dir: str,
    props: dict,
    T0: float,
    damping: float = 0.0025,
    dt: float = 1.0 / 240.0,
    g: float = 9.81,
    small_amp: float = 0.20,
    large_amp: float = 2.80,
    amp_start: float = 0.20,
    amp_end: float = 2.40,
    amp_step: float = 0.20,
    on_progress=None,
) -> dict:
    """Run the complete multi-phase experiment and generate all outputs.

    Parameters
    ----------
    out_dir : str
        Directory for all outputs (CSVs, plots, report).
    props : dict
        Pendulum properties from compute_pendulum_properties().
    T0 : float
        Theoretical small-angle period.
    on_progress : callable, optional
        Callback(phase_name, phase_num, total_phases) for progress reporting.

    Returns
    -------
    dict with summary data and file paths.
    """
    os.makedirs(out_dir, exist_ok=True)

    def _progress(name, num, total):
        if on_progress:
            on_progress(name, num, total)

    # --- Phase 1: Qualitative small amplitude ---
    _progress("Small amplitude simulation", 1, 5)
    small_df = simulate_pure_rk4(props, small_amp, damping, dt, 4.0, T0, g)
    small_df.to_csv(os.path.join(out_dir, "small_amp.csv"), index=False)
    save_three_curve_plot(small_df,
                          f"Small-Amplitude Pendulum (A0={small_amp:.2f} rad)",
                          os.path.join(out_dir, "small_amp_plot.png"))

    # --- Phase 2: Qualitative large amplitude ---
    _progress("Large amplitude simulation", 2, 5)
    large_df = simulate_pure_rk4(props, large_amp, damping, dt, 4.0, T0, g)
    large_df.to_csv(os.path.join(out_dir, "large_amp.csv"), index=False)
    save_three_curve_plot(large_df,
                          f"Large-Amplitude Pendulum (A0={large_amp:.2f} rad)",
                          os.path.join(out_dir, "large_amp_plot.png"))
    save_overlay_plot(small_df, large_df, small_amp, large_amp,
                      os.path.join(out_dir, "small_vs_large_theta.png"))

    # --- Phase 3: Period-zero measurement ---
    _progress("Period-zero measurement", 3, 5)
    pz_df = simulate_pure_rk4(props, 0.10, damping, dt, 14.0, T0, g)
    pz_df.to_csv(os.path.join(out_dir, "period_zero.csv"), index=False)
    T0_measured, amp_mid = measure_period_zero(pz_df)

    # --- Phase 4: Amplitude sweep ---
    _progress("Amplitude sweep", 4, 5)
    amps = np.arange(amp_start, amp_end + 1e-12, amp_step)
    rows = []
    for A in amps:
        df = simulate_pure_rk4(props, float(A), damping, dt, 3.5, T0, g)
        df.to_csv(os.path.join(out_dir, f"amp_{A:.2f}_timeseries.csv"), index=False)
        T_meas, A_meas = measure_period_two_cycles_zero_cross(df)
        rows.append({
            "amp_set": A,
            "amp_measured": A_meas,
            "period_measured": T_meas,
            "T0_theory": T0,
            "T0_measured_from_period_zero": T0_measured,
            "T_series_2term": period_series(T0, A_meas, 2) if np.isfinite(A_meas) else np.nan,
            "T_series_3term": period_series(T0, A_meas, 3) if np.isfinite(A_meas) else np.nan,
            "T_series_4term": period_series(T0, A_meas, 4) if np.isfinite(A_meas) else np.nan,
            "T_series_5term": period_series(T0, A_meas, 5) if np.isfinite(A_meas) else np.nan,
        })

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(os.path.join(out_dir, "period_summary.csv"), index=False)
    save_period_comparison_plot(summary_df,
                                os.path.join(out_dir, "period_vs_amplitude.png"))
    save_error_plot(summary_df, os.path.join(out_dir, "small_angle_error.png"))

    # --- Phase 5: Generate report ---
    _progress("Generating report", 5, 5)
    report_path = generate_pendulum_report(
        out_dir, props, T0, damping,
        small_amp, large_amp, amp_start, amp_end, amp_step, dt,
        summary_df, T0_measured, amp_mid,
    )

    # --- ZIP archive ---
    zip_path = shutil.make_archive(out_dir, "zip", root_dir=out_dir)

    return {
        "T0_theory": T0,
        "T0_measured": T0_measured,
        "amp_mid": amp_mid,
        "sweep_points": len(rows),
        "out_dir": out_dir,
        "report_path": report_path,
        "zip_path": zip_path,
        "files": {
            "report": "Expt2_Large_Amplitude_Pendulum_Report.md",
            "small_amp_plot": "small_amp_plot.png",
            "large_amp_plot": "large_amp_plot.png",
            "overlay_plot": "small_vs_large_theta.png",
            "period_plot": "period_vs_amplitude.png",
            "error_plot": "small_angle_error.png",
            "period_summary": "period_summary.csv",
            "zip": os.path.basename(zip_path),
        },
    }
