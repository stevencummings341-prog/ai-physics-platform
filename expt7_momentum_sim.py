"""Compatibility launcher for the standardized Experiment 7 workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

from experiments.expt7_momentum.sim import Experiment


DEFAULT_CONFIG_PATH = Path(__file__).parent / "experiments" / "expt7_momentum" / "config.yaml"


def load_defaults() -> dict:
    with open(DEFAULT_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def prompt_user_overrides(defaults: dict) -> dict:
    """Interactive CLI wrapper. The simulation module itself stays non-blocking."""
    print("\n=== Experiment 7: Momentum Conservation ===")
    print("This file is a compatibility entrypoint for the standardized platform.")
    print("X-axis convention: +X = right, -X = left.")
    print("Tip: for head-on collision use Cart 1 -> right, Cart 2 -> left.")
    print("Press Enter to keep each default value.\n")

    def ask_float(prompt: str, default: float) -> float:
        while True:
            raw = input(f"  {prompt} [default {default}]: ").strip()
            if not raw:
                return float(default)

            # Accept common locale formats like "0,3" and full-width commas.
            normalized = raw.replace("，", ",").replace(",", ".").replace(" ", "")
            try:
                return float(normalized)
            except ValueError:
                print(f"    Invalid number: '{raw}'. Examples: 0.3, 1, -0.25")

    def ask_direction(prompt: str, default_sign: int) -> int:
        default_label = "R" if default_sign >= 0 else "L"
        while True:
            raw = input(f"  {prompt} [R/L, default {default_label}]: ").strip().lower()
            if not raw:
                return 1 if default_sign >= 0 else -1

            if raw in {"r", "right", "+", "+x", "1"}:
                return 1
            if raw in {"l", "left", "-", "-x", "-1"}:
                return -1
            print(f"    Invalid direction: '{raw}'. Use R (right) or L (left).")

    def ask_velocity(name: str, default_velocity: float) -> float:
        default_speed = abs(float(default_velocity))
        default_sign = 1 if float(default_velocity) >= 0 else -1
        speed = ask_float(f"{name} speed magnitude (m/s)", default_speed)
        speed = max(0.0, speed)
        direction = ask_direction(f"{name} direction", default_sign)
        return direction * speed

    overrides = {
        "m1": ask_float("Cart 1 mass (kg)", defaults["m1"]),
        "m2": ask_float("Cart 2 mass (kg)", defaults["m2"]),
        "v1_init": ask_velocity("Cart 1", defaults["v1_init"]),
        "v2_init": ask_velocity("Cart 2", defaults["v2_init"]),
        "restitution": ask_float("Restitution (1.0=elastic, 0.0=inelastic)", defaults["restitution"]),
    }
    overrides["m1"] = max(1e-6, overrides["m1"])
    overrides["m2"] = max(1e-6, overrides["m2"])
    overrides["restitution"] = min(1.0, max(0.0, overrides["restitution"]))

    if overrides["v1_init"] <= overrides["v2_init"]:
        print("  Warning: current velocities may not produce a collision.")
        print("  Recommendation: set Cart 1 speed > Cart 2 speed in opposite directions.")

    print("\nUsing standardized experiment module:")
    for key, value in overrides.items():
        print(f"  {key} = {value}")
    print()
    return overrides


def main() -> None:
    defaults = load_defaults()
    overrides = prompt_user_overrides(defaults)

    expt = Experiment(config_path=str(DEFAULT_CONFIG_PATH), overrides=overrides)
    try:
        summary = expt.execute()
        expt.print_summary(summary)
        if "report_md" in expt.artifacts:
            print(f"Report generated: {expt.artifacts['report_md']}")
    finally:
        try:
            input("Press Enter to close Isaac Sim ...")
        except EOFError:
            pass
        expt.shutdown()


if __name__ == "__main__":
    main()
