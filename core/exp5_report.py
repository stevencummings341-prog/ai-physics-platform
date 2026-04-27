"""Experiment 5 (rotational inertia / physical pendulum) report data builder.

This module turns the raw web-run telemetry samples into the artifacts the
PHY1002 lab report needs:

    - Cleaned raw time-series CSV
    - Cycle-by-cycle period CSV
    - Four PNG figures (time series, period curve, inertia comparison,
      cycle periods)
    - A Markdown sidecar (rendered by ReportGenerator at the call site)
    - A ZIP archive of the above

The actual lab report PDF is composed in the browser by
``frontend/src/components/Exp5ReportPDF.tsx`` using @react-pdf/renderer so
the layout matches the Experiment 1 report (cover page, sections, LaTeX
equations, tabular data, figure captions). This file therefore only owns
data preparation and matplotlib plotting; it deliberately does *not* try
to render a full PDF on the Python side.
"""
from __future__ import annotations

import math
import os
import zipfile
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


G = 9.81


def theoretical_period(length_m: float, pivot_distance_m: float, g: float = G) -> float:
    """Small-amplitude physical-pendulum period for a uniform bar."""
    length_m = max(1e-9, float(length_m))
    pivot_distance_m = max(1e-9, float(pivot_distance_m))
    return 2.0 * math.pi * math.sqrt(
        ((length_m * length_m / 12.0) + pivot_distance_m * pivot_distance_m)
        / (g * pivot_distance_m)
    )


def minimum_period_distance(length_m: float) -> float:
    """Distance from center of mass that minimises T(x): x = L / sqrt(12)."""
    return float(length_m) / math.sqrt(12.0)


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _estimate_period_from_zero_crossings(
    df: pd.DataFrame,
) -> tuple[float, float, list[dict[str, float]]]:
    """Estimate period using positive-going zero crossings in theta(t)."""
    if len(df) < 4:
        return float("nan"), float("nan"), []

    t = df["time_s"].to_numpy(dtype=float)
    theta = df["theta_rad"].to_numpy(dtype=float)
    crossings: list[float] = []

    for i in range(1, len(theta)):
        y0, y1 = theta[i - 1], theta[i]
        if y0 <= 0.0 < y1:
            dt = t[i] - t[i - 1]
            dy = y1 - y0
            frac = 0.0 if abs(dy) < 1e-12 else -y0 / dy
            crossings.append(float(t[i - 1] + frac * dt))

    periods = np.diff(crossings)
    periods = periods[(periods > 0.1) & (periods < 20.0)]
    if len(periods) == 0:
        return float("nan"), float("nan"), []

    period_rows = [
        {"cycle": float(i + 1), "period_s": float(periods[i])}
        for i in range(len(periods))
    ]
    std = float(np.std(periods, ddof=1)) if len(periods) > 1 else 0.0
    return float(np.mean(periods)), std, period_rows


def _safe_pct_error(measured: float, reference: float) -> float:
    if not math.isfinite(measured) or not math.isfinite(reference) or abs(reference) < 1e-12:
        return float("nan")
    return (measured - reference) / reference * 100.0


def generate_exp5_report(
    samples: list[dict[str, Any]],
    params: dict[str, float],
    out_dir: str,
    markdown_template: str | None = None,
) -> dict[str, Any]:
    """Generate Experiment 5 CSV + plots + Markdown + ZIP artifacts.

    Returns a dict with summary numbers, period rows and absolute paths to
    every artifact. The caller (``core/webrtc_server.py``) wraps these
    artifacts in base64 and ships them to the browser, where Exp5ReportPDF
    composes the actual PDF.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)

    mass = max(1e-9, _finite_float(params.get("mass_kg"), 0.28))
    length = max(1e-9, _finite_float(params.get("length_m"), 0.28))
    x = max(1e-9, _finite_float(params.get("pivot_distance_m"), 0.10))
    theta0_deg = _finite_float(params.get("theta0_deg"), 5.0)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df = pd.DataFrame(samples).copy()
    if df.empty:
        raise RuntimeError("No Experiment 5 samples were provided.")
    df = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["time_s", "theta_rad", "omega_rad_s"]
    )
    if len(df) < 20:
        raise RuntimeError(
            "Not enough Experiment 5 data. "
            "Run the pendulum for a few seconds before exporting."
        )
    df = df.sort_values("time_s")
    csv_path = os.path.join(out_dir, "exp5_raw_timeseries.csv")
    df.to_csv(csv_path, index=False)

    measured_period, period_std, period_rows = _estimate_period_from_zero_crossings(df)
    rolling_periods = df.get("period_s")
    rolling_period = float("nan")
    if rolling_periods is not None:
        positive = rolling_periods.replace([np.inf, -np.inf], np.nan).dropna()
        positive = positive[positive > 0.0]
        if len(positive) > 0:
            rolling_period = float(positive.iloc[-1])
    if not math.isfinite(measured_period) and math.isfinite(rolling_period):
        measured_period = rolling_period
        period_std = 0.0

    T_theory = theoretical_period(length, x)
    x_min = minimum_period_distance(length)
    T_min = theoretical_period(length, x_min)
    I_cm_geom = mass * length * length / 12.0
    I_pivot_geom = I_cm_geom + mass * x * x
    I_pivot_period = (
        measured_period * measured_period * mass * G * x / (4.0 * math.pi * math.pi)
        if math.isfinite(measured_period) else float("nan")
    )
    I_cm_period = (
        I_pivot_period - mass * x * x if math.isfinite(I_pivot_period) else float("nan")
    )

    theta_peak_deg = float(
        np.max(np.abs(df["theta_rad"].to_numpy(dtype=float))) * 180.0 / math.pi
    )
    t_duration = float(df["time_s"].max() - df["time_s"].min())
    dt_median = float(df["time_s"].diff().dropna().median()) if len(df) > 1 else 0.0
    period_unc = max(period_std if math.isfinite(period_std) else 0.0, dt_median)

    summary = {
        "generated_at": generated_at,
        "n_samples": int(len(df)),
        "duration_s": t_duration,
        "mass_kg": mass,
        "length_m": length,
        "pivot_distance_m": x,
        "theta0_deg": theta0_deg,
        "theta_peak_deg": theta_peak_deg,
        "period_measured_s": measured_period,
        "period_std_s": period_std if math.isfinite(period_std) else 0.0,
        "period_unc_s": period_unc if math.isfinite(period_unc) else 0.0,
        "period_theory_s": T_theory,
        "period_error_pct": _safe_pct_error(measured_period, T_theory),
        "x_min_theory_m": x_min,
        "T_min_theory_s": T_min,
        "x_vs_xmin_pct": _safe_pct_error(x, x_min),
        "I_cm_geom_kg_m2": I_cm_geom,
        "I_pivot_geom_kg_m2": I_pivot_geom,
        "I_pivot_period_kg_m2": I_pivot_period,
        "I_cm_period_kg_m2": I_cm_period,
        "I_pivot_error_pct": _safe_pct_error(I_pivot_period, I_pivot_geom),
        "I_cm_error_pct": _safe_pct_error(I_cm_period, I_cm_geom),
        "mass_unc_kg": max(0.0001, 0.001 * mass),
        "length_unc_m": 0.0005,
        "pivot_unc_m": 0.0005,
        "theta_unc_deg": 0.05,
    }

    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False

    plots = {
        "timeseries": os.path.join(out_dir, "exp5_angle_omega_timeseries.png"),
        "period_curve": os.path.join(out_dir, "exp5_period_vs_pivot_distance.png"),
        "inertia": os.path.join(out_dir, "exp5_inertia_comparison.png"),
        "cycle_periods": os.path.join(out_dir, "exp5_cycle_periods.png"),
    }

    fig, axs = plt.subplots(2, 1, figsize=(9.0, 6.4), sharex=True)
    axs[0].plot(df["time_s"], np.degrees(df["theta_rad"]), lw=1.6, color="#7c3aed")
    axs[0].set_ylabel("Angle theta (deg)")
    axs[0].set_title("Experiment 5: Angle and Angular Velocity vs. Time")
    axs[0].grid(True, alpha=0.3)
    axs[1].plot(df["time_s"], df["omega_rad_s"], lw=1.5, color="#2563eb")
    axs[1].set_xlabel("Time (s)")
    axs[1].set_ylabel("Angular velocity omega (rad/s)")
    axs[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plots["timeseries"], dpi=220, bbox_inches="tight")
    plt.close(fig)

    x_values = np.linspace(
        max(0.005, length * 0.04), max(length * 0.5, x * 1.15), 240
    )
    T_values = np.array([theoretical_period(length, xv) for xv in x_values])
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    ax.plot(x_values, T_values, color="#111827", lw=1.8, label="Theory T(x)")
    ax.axvline(
        x_min, color="#16a34a", ls="--", lw=1.2,
        label=f"x_min = {x_min:.4f} m",
    )
    ax.scatter([x], [T_theory], color="#f59e0b", s=70, zorder=3,
               label="Selected pivot, theory")
    if math.isfinite(measured_period):
        ax.scatter([x], [measured_period], color="#dc2626", s=70, zorder=4,
                   label="Selected pivot, measured")
    ax.set_xlabel("Pivot-to-CM distance x (m)")
    ax.set_ylabel("Period T (s)")
    ax.set_title("Period of a Physical Pendulum vs. Pivot Distance")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(plots["period_curve"], dpi=220, bbox_inches="tight")
    plt.close(fig)

    bar_labels = ["I_pivot theory", "I_pivot from T", "I_cm theory", "I_cm from T"]
    bar_vals = [I_pivot_geom, I_pivot_period, I_cm_geom, I_cm_period]
    bar_safe = [0.0 if not math.isfinite(v) else v for v in bar_vals]
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    bars = ax.bar(
        bar_labels, bar_safe,
        color=["#2563eb", "#f97316", "#10b981", "#ef4444"],
    )
    for rect, value in zip(bars, bar_vals):
        if not math.isfinite(value):
            continue
        ax.text(
            rect.get_x() + rect.get_width() / 2.0,
            rect.get_height(),
            f"{value:.6f}",
            ha="center", va="bottom", fontsize=9,
        )
    ax.set_ylabel("Rotational inertia (kg m^2)")
    ax.set_title("Rotational Inertia: Geometry vs. From Measured Period")
    ax.grid(True, axis="y", alpha=0.3)
    fig.autofmt_xdate(rotation=14)
    fig.tight_layout()
    fig.savefig(plots["inertia"], dpi=220, bbox_inches="tight")
    plt.close(fig)

    period_df = pd.DataFrame(period_rows)
    period_csv_path = os.path.join(out_dir, "exp5_cycle_periods.csv")
    period_df.to_csv(period_csv_path, index=False)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    if len(period_df) > 0:
        ax.plot(
            period_df["cycle"], period_df["period_s"], marker="o", lw=1.4,
            color="#dc2626", label="Measured cycle period",
        )
    ax.axhline(T_theory, color="#111827", ls="--", lw=1.2, label="Theory T(x)")
    ax.set_xlabel("Cycle number")
    ax.set_ylabel("Period (s)")
    ax.set_title("Cycle-by-Cycle Period Estimate")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(plots["cycle_periods"], dpi=220, bbox_inches="tight")
    plt.close(fig)

    md_path = os.path.join(out_dir, "Expt5_Rotational_Inertia_Report.md")
    if markdown_template:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_template)
    elif not os.path.exists(md_path):
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                "# Lab Report for Lab 5 -- Rotational Inertia (Physical Pendulum)\n\n"
                "Markdown template rendering was unavailable; the formal lab "
                "report PDF is generated in the browser by Exp5ReportPDF.tsx.\n"
            )

    zip_path = os.path.join(
        os.path.dirname(out_dir), f"{os.path.basename(out_dir)}.zip"
    )
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(out_dir):
            zf.write(os.path.join(out_dir, fname), fname)

    return {
        "summary": summary,
        "period_rows": period_rows,
        "paths": {
            "csv": csv_path,
            "period_csv": period_csv_path,
            "markdown": md_path,
            "zip": zip_path,
            **plots,
        },
        "plot_files": {k: os.path.basename(v) for k, v in plots.items()},
    }
