"""Abstract base class that every physics experiment must subclass."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd
import yaml

log = logging.getLogger(__name__)


class ExperimentBase(ABC):
    """
    Lifecycle: configure → build_scene → warmup → run → analyze → plot → report.

    Subclasses implement the abstract hooks; the base orchestrates sequencing,
    data recording, and output management.
    """

    name: str = "unnamed_experiment"

    def __init__(self, config_path: str | None = None, overrides: dict | None = None):
        self.cfg: dict[str, Any] = self._load_config(config_path, overrides)
        self.out_dir: str = self._make_output_dir()
        self.world = None
        self.records: list[dict] = []
        self.artifacts: dict[str, Any] = {}
        self._save_run_config()

    # ---------------------------------------------------------------- config
    def _load_config(self, path: str | None, overrides: dict | None) -> dict:
        cfg: dict[str, Any] = {}
        if path and os.path.isfile(path):
            with open(path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            log.info("Loaded config from %s", path)
        if overrides:
            cfg.update(overrides)
        return cfg

    def _save_run_config(self):
        """Persist the exact config used for this run (reproducibility)."""
        path = os.path.join(self.out_dir, "run_config.yaml")
        with open(path, "w") as f:
            yaml.dump(self.cfg, f, default_flow_style=False)

    # --------------------------------------------------------------- output
    def _make_output_dir(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join("outputs", f"{self.name}_{ts}")
        os.makedirs(out, exist_ok=True)
        log.info("Output directory: %s", out)
        return out

    # ------------------------------------------------------------ lifecycle
    @abstractmethod
    def build_scene(self) -> None:
        """Create USD stage, lighting, ground/track, physics objects."""

    @abstractmethod
    def apply_initial_conditions(self) -> None:
        """Set velocities, forces, or torques after warmup settling."""

    @abstractmethod
    def step_callback(self, step: int, t: float) -> dict:
        """Called every physics tick. Return a dict of measurements for this step."""

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> dict:
        """Post-sim analysis. Return a summary dict."""

    @abstractmethod
    def plot(self, df: pd.DataFrame) -> None:
        """Generate and save plots to self.out_dir."""

    def prepare_run(self) -> None:
        """Optional hook for derived classes to finalize config before run."""

    def generate_report(self, summary: dict, df: pd.DataFrame) -> str | None:
        """Optional hook for report generation."""
        return None

    # ---------------------------------------------------------- run engine
    def setup(self) -> None:
        """Full scene setup (called once before first run)."""
        self.build_scene()

    def warmup(self) -> None:
        """Step physics to let objects settle under gravity."""
        dt = self.cfg.get("physics_dt", 1.0 / 240.0)
        warmup_s = self.cfg.get("warmup_seconds", 0.5)
        steps = int(warmup_s / dt)
        log.info("Warmup: %d steps (%.2f s)", steps, warmup_s)
        for _ in range(steps):
            self.world.step(render=True)

    def reset(self) -> None:
        """Reset world and re-settle, then apply initial conditions.
        VR users call this to re-run without restarting Isaac Sim."""
        self.records.clear()
        self.world.reset()
        self.warmup()
        self.apply_initial_conditions()

    def run(self) -> pd.DataFrame:
        """Execute the simulation loop and return recorded data."""
        self.reset()
        dt = self.cfg.get("physics_dt", 1.0 / 240.0)
        sim_time = self.cfg.get("sim_time", 5.0)
        total_steps = int(sim_time / dt)
        log.info("Running %d steps (%.1f s) ...", total_steps, sim_time)

        for step in range(total_steps):
            self.world.step(render=True)
            t = step * dt
            row = self.step_callback(step, t)
            if row:
                row.setdefault("time", t)
                self.records.append(row)

        df = pd.DataFrame(self.records)
        df.to_csv(os.path.join(self.out_dir, "timeseries.csv"), index=False)
        log.info("Timeseries saved (%d rows).", len(df))
        return df

    def execute(self) -> dict:
        """Full pipeline: setup → run → analyze → plot. Returns summary."""
        self.setup()
        self.prepare_run()
        self._save_run_config()
        df = self.run()
        summary = self.analyze(df)
        summary_path = os.path.join(self.out_dir, "summary.csv")
        pd.DataFrame([summary]).to_csv(summary_path, index=False)
        self.artifacts["summary_csv"] = summary_path
        self.artifacts["timeseries_csv"] = os.path.join(self.out_dir, "timeseries.csv")
        self.plot(df)
        report_path = self.generate_report(summary, df)
        if report_path:
            self.artifacts["report_md"] = report_path
        return summary

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up Isaac Sim resources."""
