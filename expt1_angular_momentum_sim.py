"""Interactive launcher for Experiment 1: Conservation of Angular Momentum.

Usage:
    python expt1_angular_momentum_sim.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

from experiments.expt1_angular_momentum.sim import Experiment


DEFAULT_CONFIG_PATH = Path(__file__).parent / "experiments" / "expt1_angular_momentum" / "config.yaml"


def load_defaults() -> dict:
    with open(DEFAULT_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}


def ask_float(prompt: str, default: float) -> float:
    while True:
        raw = input(f"  {prompt} [default {default}]: ").strip()
        if not raw:
            return float(default)
        normalized = raw.replace("\uff0c", ",").replace(",", ".").replace(" ", "")
        try:
            return float(normalized)
        except ValueError:
            print(f"    Invalid number: '{raw}'. Examples: 0.3, 1, 25")


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    opts_str = "/".join(options)
    while True:
        raw = input(f"  {prompt} [{opts_str}, default {default}]: ").strip().lower()
        if not raw:
            return default
        if raw in [o.lower() for o in options]:
            return raw
        print(f"    Invalid choice: '{raw}'. Options: {opts_str}")


def prompt_user_overrides(defaults: dict) -> dict:
    print("\n" + "=" * 60)
    print("  Experiment 1: Conservation of Angular Momentum")
    print("  PASCO EX-5517 — Isaac Sim Simulation")
    print("=" * 60)
    print()
    print("  A non-rotating object is dropped onto a spinning disk.")
    print("  Angular momentum L = I*omega should be conserved.")
    print("  Kinetic energy KE = 0.5*I*omega^2 will decrease (inelastic).")
    print()
    print("  Press Enter to keep each default value.")
    print("-" * 60)

    drop_obj = ask_choice(
        "Drop object type",
        ["ring", "disk2"],
        str(defaults.get("drop_object", "ring")),
    )

    print()
    print("  --- Spinning Disk (mounted on axle) ---")
    disk_mass = ask_float("Disk mass (kg)", defaults["disk_mass"])
    disk_radius = ask_float("Disk radius (m)", defaults["disk_radius"])

    print()
    if drop_obj == "ring":
        print("  --- Ring (dropped onto disk) ---")
        ring_mass = ask_float("Ring mass (kg)", defaults["ring_mass"])
        ring_r_inner = ask_float("Ring inner radius (m)", defaults["ring_r_inner"])
        ring_r_outer = ask_float("Ring outer radius (m)", defaults["ring_r_outer"])
        ring_offset = ask_float("Ring center offset from axis (m)", defaults.get("ring_offset_x", 0.005))
    else:
        print("  --- Second Disk (dropped onto spinning disk) ---")
        d2_mass = ask_float("Disk 2 mass (kg)", defaults.get("disk2_mass", 0.120))
        d2_radius = ask_float("Disk 2 radius (m)", defaults.get("disk2_radius", 0.125))

    print()
    print("  --- Initial Conditions ---")
    omega_init = ask_float("Initial angular speed of disk (rad/s)", defaults["omega_init"])
    omega_init = max(0.1, abs(omega_init))

    print()
    print("  --- Timing ---")
    pre_t = ask_float("Pre-collision recording time (s)", defaults.get("pre_collision_time", 2.0))
    post_t = ask_float("Post-collision recording time (s)", defaults.get("post_collision_time", 3.0))

    overrides: dict = {
        "drop_object": drop_obj,
        "disk_mass": max(1e-6, disk_mass),
        "disk_radius": max(0.01, disk_radius),
        "omega_init": omega_init,
        "pre_collision_time": max(0.5, pre_t),
        "post_collision_time": max(1.0, post_t),
    }

    if drop_obj == "ring":
        overrides["ring_mass"] = max(1e-6, ring_mass)
        overrides["ring_r_inner"] = max(0.001, ring_r_inner)
        overrides["ring_r_outer"] = max(overrides["ring_r_inner"] + 0.001, ring_r_outer)
        overrides["ring_offset_x"] = max(0.0, ring_offset)
    else:
        overrides["disk2_mass"] = max(1e-6, d2_mass)
        overrides["disk2_radius"] = max(0.01, d2_radius)

    # Preview theoretical prediction
    I_disk = 0.5 * overrides["disk_mass"] * overrides["disk_radius"] ** 2
    if drop_obj == "ring":
        I_drop = (0.5 * overrides["ring_mass"]
                  * (overrides["ring_r_inner"] ** 2 + overrides["ring_r_outer"] ** 2)
                  + overrides["ring_mass"] * overrides.get("ring_offset_x", 0.0) ** 2)
    else:
        I_drop = 0.5 * overrides["disk2_mass"] * overrides["disk2_radius"] ** 2

    omega_f_theory = I_disk * omega_init / (I_disk + I_drop)

    print()
    print("-" * 60)
    print("  Parameter Summary:")
    print(f"    Drop object:        {drop_obj}")
    print(f"    Disk:               m={overrides['disk_mass']} kg, R={overrides['disk_radius']} m")
    if drop_obj == "ring":
        print(f"    Ring:               m={overrides['ring_mass']} kg, "
              f"R_in={overrides['ring_r_inner']} m, R_out={overrides['ring_r_outer']} m")
    else:
        print(f"    Disk 2:             m={overrides['disk2_mass']} kg, "
              f"R={overrides['disk2_radius']} m")
    print(f"    omega_init:         {omega_init:.2f} rad/s  ({omega_init / (2 * 3.14159):.1f} rev/s)")
    print(f"    I_disk:             {I_disk:.6f} kg*m^2")
    print(f"    I_drop:             {I_drop:.6f} kg*m^2")
    print(f"    omega_f (theory):   {omega_f_theory:.2f} rad/s")
    print(f"    Sim time:           {overrides['pre_collision_time'] + overrides['post_collision_time']:.1f} s")
    print("-" * 60)
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
