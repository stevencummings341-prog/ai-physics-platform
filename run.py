#!/usr/bin/env python3
"""CLI entry point for the AI Physics Experiment Platform.

Usage:
    python run.py expt1_angular_momentum              # angular momentum conservation
    python run.py expt7_momentum                     # linear momentum conservation
    python run.py expt7_momentum --headless           # no GUI
    python run.py expt7_momentum --vr                 # enable VR streaming
    python run.py expt7_momentum --config path.yaml   # custom config
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("run")

EXPERIMENT_REGISTRY: dict[str, str] = {
    "expt1_angular_momentum": "experiments.expt1_angular_momentum.sim",
    "expt7_momentum": "experiments.expt7_momentum.sim",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI Physics Experiment Platform")
    p.add_argument("experiment", choices=list(EXPERIMENT_REGISTRY.keys()),
                   help="Experiment identifier")
    p.add_argument("--config", type=str, default=None,
                   help="Path to YAML config override file")
    p.add_argument("--headless", action="store_true",
                   help="Run without GUI window")
    p.add_argument("--vr", action="store_true",
                   help="Enable VR LiveStream")
    return p.parse_args()


def main():
    args = parse_args()

    module_path = EXPERIMENT_REGISTRY[args.experiment]
    log.info("Loading experiment module: %s", module_path)

    mod = importlib.import_module(module_path)
    experiment_cls = getattr(mod, "Experiment", None)
    if experiment_cls is None:
        log.error("Module %s does not expose an 'Experiment' class.", module_path)
        sys.exit(1)

    overrides = {}
    if args.headless:
        overrides["headless"] = True
    if args.vr:
        overrides["enable_livestream"] = True
        overrides["render_dt"] = 1.0 / 90.0

    expt = experiment_cls(config_path=args.config, overrides=overrides)
    try:
        summary = expt.execute()
        expt.print_summary(summary)
        if getattr(expt, "artifacts", None):
            for name, path in expt.artifacts.items():
                log.info("Artifact [%s]: %s", name, path)
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    finally:
        expt.shutdown()


if __name__ == "__main__":
    main()
