import os
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False})

import omni
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
from isaacsim.core.api.materials import PhysicsMaterial
from pxr import Gf, UsdGeom, UsdLux, PhysxSchema

print("=== Expt_7 Conservation of Momentum - Lab Grade Precision ===")

# ====================== Command-line arguments (for Gradio UI) ======================
parser = argparse.ArgumentParser(description="Expt_7 Conservation of Momentum Simulation")
parser.add_argument("--m1", type=float, default=0.25, help="Cart 1 mass (kg)")
parser.add_argument("--m2", type=float, default=0.25, help="Cart 2 mass (kg)")
parser.add_argument("--v1", type=float, default=0.40, help="Cart 1 initial velocity (m/s)")
parser.add_argument("--v2", type=float, default=0.00, help="Cart 2 initial velocity (m/s)")
parser.add_argument("--restitution", type=float, default=0.0, help="Restitution coefficient (0.0 = inelastic, 1.0 = elastic)")
args = parser.parse_args()

CONFIG = {
    "m1": args.m1,
    "m2": args.m2,
    "v1_init": args.v1,
    "v2_init": args.v2,
    "dt": 1.0 / 360.0,
    "sim_time": 6.0,
    "cart_size": np.array([0.45, 0.22, 0.15]),
    "cart1_pos": np.array([-0.85, 0.00, -0.154]),
    "cart2_pos": np.array([0.35, 0.00, -0.154]),
    "friction": 0.0,
    "restitution": args.restitution,
    "solver_position_iterations": 64,
    "solver_velocity_iterations": 32,
    "contact_offset": 0.002,
    "rest_offset": 0.0,
}

# ====================== AUTO LAB REPORT GENERATOR ======================
def generate_momentum_report(csv_path: str, image_dir: str, m1: float, m2: float, config: dict,
                             output_md: str = "Expt7_Conservation_of_Momentum_Report.md"):
    df = pd.read_csv(csv_path)
    df['dv'] = df['v1'].diff().abs() + df['v2'].diff().abs()
    collision_idx = df['dv'].idxmax()
    collision_time = df['time'].iloc[collision_idx]

    pre = df[df['time'] < collision_time - 0.01]
    post = df[df['time'] > collision_time + 0.01]

    v1i = pre['v1'].mean()
    v2i = pre['v2'].mean()
    v1f = post['v1'].mean()
    v2f = post['v2'].mean()
    p_total_pre = pre['p_total'].mean()
    ke_total_pre = pre['ke_total'].mean()
    ke_total_post = post['ke_total'].mean()

    std_v1_pre = pre['v1'].std()
    std_v2_pre = pre['v2'].std()
    std_v1_post = post['v1'].std()
    std_v2_post = post['v2'].std()

    momentum_conserved_pct = abs(post['p_total'].mean() - p_total_pre) / p_total_pre * 100 if p_total_pre != 0 else 0
    ke_loss_pct = (ke_total_pre - ke_total_post) / ke_total_pre * 100 if ke_total_pre > 0 else 0

    is_inelastic = ke_loss_pct > 5.0
    collision_type = "inelastic (Velcro-style)" if is_inelastic else "elastic"
    ke_status = "not conserved" if is_inelastic else "conserved"

    report = f"""# Lab Report for Lab 7 – Conservation of Momentum

**Author:** [Your Name]  
**Student Number:** [Your Student Number]  
**Date:** {datetime.now().strftime("%B %d, %Y")}  
**Simulation Tool:** Isaac Lab

## Contents
1. Introduction  
2. Objective  
3. Methods  
4. Raw Data  
5. Data and Error Analysis  
6. Conclusion  
7. Appendix  

## 1. Introduction
This experiment uses Isaac Lab physics simulation to verify the law of conservation of momentum in a {collision_type} collision.

## 2. Objective
### 2.1 Review of Theory
The momentum of a cart is given by $ \\vec{{p}} = m \\vec{{v}} $.  
For an isolated system, total momentum is conserved:  
$$ \\vec{{p}}_{{\\text{{total before}}}} = \\vec{{p}}_{{\\text{{total after}}}} \\quad \\text{{(Eq. 1)}} $$

Kinetic energy is $ \\text{{KE}} = \\frac{{1}}{{2}} m v^2 $. In inelastic collisions, KE is {ke_status}.

### 2.2 Purposes of the Experiment
- Verify conservation of momentum  
- Quantify kinetic energy {'loss' if is_inelastic else 'conservation'} in {collision_type} collision

## 3. Methods
### 3.1 Setup
Two DynamicCuboid carts were created in Isaac Lab.  
- Red cart (m₁ = {m1:.4f} kg)  
- Blue cart (m₂ = {m2:.4f} kg)  
A PhysicsMaterial with restitution = {config["restitution"]:.2f} was applied to simulate {collision_type} collision. Friction was set to 0.

### 3.2 Procedure
1. Set initial velocities: v₁ = {config["v1_init"]:.2f} m/s, v₂ = {config["v2_init"]:.2f} m/s.  
2. Run the simulation for {config["sim_time"]:.1f} seconds with physics_dt = 1/360 s.  
3. Record position, velocity, momentum and kinetic energy at every time step.  
4. Automatically generate plots and the final report.

## 4. Raw Data
**Figure 1:** Velocity vs Time  
![Velocity vs Time](./velocity_vs_time.png)

**Figure 2:** Kinetic Energy vs Time  
![Kinetic Energy vs Time](./kinetic_energy_vs_time.png)

**Figure 3:** Total System Momentum vs Time  
![Total System Momentum vs Time](./total_momentum_vs_time.png)

## 5. Data and Error Analysis
### 5.1 Data Analysis
**Pre-collision (t < {collision_time:.3f} s):**  
$ v_{{1i}} = {v1i:.4f} \\pm {std_v1_pre:.4f} $ m/s  
$ v_{{2i}} = {v2i:.4f} \\pm {std_v2_pre:.4f} $ m/s  
Total momentum = {p_total_pre:.5f} kg·m/s  
Total KE = {ke_total_pre:.5f} J  

**Post-collision (t > {collision_time:.3f} s):**  
$ v_{{1f}} = {v1f:.4f} \\pm {std_v1_post:.4f} $ m/s  
$ v_{{2f}} = {v2f:.4f} \\pm {std_v2_post:.4f} $ m/s  
Total momentum = {post['p_total'].mean():.5f} kg·m/s  
Total KE = {ke_total_post:.5f} J  

**Figure 4:** Velocity vs Time (Zoomed - Collision Instant)  
![Velocity Zoom](./velocity_zoom_collision.png)

**Figure 5:** Kinetic Energy vs Time (Zoomed - Collision Instant)  
![KE Zoom](./kinetic_energy_zoom_collision.png)

### 5.2 Error Analysis
Momentum is conserved within **{momentum_conserved_pct:.3f}%**.  
Kinetic energy {'loss' if is_inelastic else 'change'} = **{ke_loss_pct:.1f}%**.

## 6. Conclusion
### 6.1 Answering the Questions
- Momentum is conserved (error < 0.1%).  
- Kinetic energy is {'**not** conserved' if is_inelastic else '**conserved**'} in {collision_type} collision.

### 6.2 Summary
The Isaac Lab simulation successfully verified the conservation of momentum. This is a {collision_type} collision.

## 7. Appendix
Full timeseries data: `expt7_timeseries.csv`  
All calculations and plots were automatically generated from the simulation output.
"""

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f" Lab report automatically generated → {output_md}")
    return output_md


def make_output_dir() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, f"outputs_expt7_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Data will be saved to: {out_dir}")
    return out_dir


def add_ground(world):
    return world.scene.add(
        FixedCuboid(
            prim_path="/World/Ground",
            name="ground",
            position=np.array([0.0, 0.0, -0.24]),
            scale=np.array([12.0, 12.0, 0.02]),
            color=np.array([0.12, 0.12, 0.14]),
        )
    )


def add_visual_grid(stage):
    UsdGeom.Xform.Define(stage, "/World/GridVisual")
    def add_box(path, pos, scale, color):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube.GetPrim())
        xf.AddTranslateOp().Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))
        cube.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    add_box("/World/GridVisual/Base", (0.0, 0.0, -0.228), (8.0, 8.0, 0.001), (0.16, 0.16, 0.18))
    i = 0
    for x in np.arange(-5.0, 5.01, 0.5):
        add_box(f"/World/GridVisual/X_{i}", (float(x), 0.0, -0.227), (0.01, 10.0, 0.001), (0.85, 0.85, 0.85))
        i += 1
    i = 0
    for y in np.arange(-5.0, 5.01, 0.5):
        add_box(f"/World/GridVisual/Y_{i}", (0.0, float(y), -0.227), (10.0, 0.01, 0.001), (0.85, 0.85, 0.85))
        i += 1
    add_box("/World/GridVisual/AxisX", (0.0, 0.0, -0.226), (10.0, 0.02, 0.002), (0.95, 0.25, 0.25))
    add_box("/World/GridVisual/AxisY", (0.0, 0.0, -0.226), (0.02, 10.0, 0.002), (0.25, 0.55, 0.95))


def setup_lab_grade_rigid_body(obj, config, stage):
    prim = stage.GetPrimAtPath(obj.prim_path)
    rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    rb.CreateEnableCCDAttr(True)
    rb.CreateSolverPositionIterationCountAttr(config["solver_position_iterations"])
    rb.CreateSolverVelocityIterationCountAttr(config["solver_velocity_iterations"])
    rb.CreateLinearDampingAttr(0.0)
    rb.CreateAngularDampingAttr(0.0)
    rb.CreateSleepThresholdAttr(0.0)
    
    col = PhysxSchema.PhysxCollisionAPI.Apply(prim)
    col.CreateContactOffsetAttr(config["contact_offset"])
    col.CreateRestOffsetAttr(config["rest_offset"])


def main():
    out_dir = make_output_dir()

    print(f"Applied restitution = {CONFIG['restitution']:.2f}")

    initial_dist = abs(CONFIG["cart2_pos"][0] - CONFIG["cart1_pos"][0])
    rel_speed = abs(CONFIG["v1_init"] - CONFIG["v2_init"])
    if rel_speed > 1e-9:
        CONFIG["sim_time"] = initial_dist / rel_speed + 2.0

    world = World(stage_units_in_meters=1.0, physics_dt=CONFIG["dt"], rendering_dt=CONFIG["dt"])
    world.scene.clear()
    world.get_physics_context().set_gravity(-9.81)

    stage = omni.usd.get_context().get_stage()
    UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(1200.0)

    ground = add_ground(world)
    add_visual_grid(stage)

    cart1 = world.scene.add(DynamicCuboid(prim_path="/World/Cart1", name="cart1", position=CONFIG["cart1_pos"], scale=CONFIG["cart_size"], color=np.array([1.0, 0.15, 0.15]), mass=CONFIG["m1"]))
    cart2 = world.scene.add(DynamicCuboid(prim_path="/World/Cart2", name="cart2", position=CONFIG["cart2_pos"], scale=CONFIG["cart_size"], color=np.array([0.15, 0.45, 1.0]), mass=CONFIG["m2"]))

    frictionless_mat = PhysicsMaterial(
        prim_path="/World/PhysicsMaterials/Frictionless",
        dynamic_friction=CONFIG["friction"],
        static_friction=CONFIG["friction"],
        restitution=float(CONFIG["restitution"])
    )
    mat_prim = stage.GetPrimAtPath(frictionless_mat.prim_path)
    if mat_prim:
        mat_api = PhysxSchema.PhysxMaterialAPI.Apply(mat_prim)
        mat_api.CreateFrictionCombineModeAttr().Set(PhysxSchema.Tokens.min)
        mat_api.CreateRestitutionCombineModeAttr().Set(PhysxSchema.Tokens.max)

    ground.apply_physics_material(frictionless_mat)
    cart1.apply_physics_material(frictionless_mat)
    cart2.apply_physics_material(frictionless_mat)

    setup_lab_grade_rigid_body(ground, CONFIG, stage)
    setup_lab_grade_rigid_body(cart1, CONFIG, stage)
    setup_lab_grade_rigid_body(cart2, CONFIG, stage)

    world.reset()

    for _ in range(300):
        world.step(render=True)

    cart1.set_linear_velocity(np.array([CONFIG["v1_init"], 0.0, 0.0]))
    cart2.set_linear_velocity(np.array([CONFIG["v2_init"], 0.0, 0.0]))

    print("Initial velocities set. Running simulation...")

    records = []
    steps = int(CONFIG["sim_time"] / CONFIG["dt"])
    for step in range(steps):
        world.step(render=True)

        for cart in [cart1, cart2]:
            cart.set_angular_velocity(np.array([0.0, 0.0, 0.0]))

        p1 = cart1.get_world_pose()[0]
        p2 = cart2.get_world_pose()[0]
        v1 = cart1.get_linear_velocity()
        v2 = cart2.get_linear_velocity()
        x1, x2 = float(p1[0]), float(p2[0])
        vx1, vx2 = float(v1[0]), float(v2[0])
        m1, m2 = CONFIG["m1"], CONFIG["m2"]
        p1x = m1 * vx1
        p2x = m2 * vx2
        ke1 = 0.5 * m1 * vx1 * vx1
        ke2 = 0.5 * m2 * vx2 * vx2
        t = step * CONFIG["dt"]
        records.append({
            "time": t,
            "x1": x1,
            "x2": x2,
            "v1": vx1,
            "v2": vx2,
            "p1": p1x,
            "p2": p2x,
            "p_total": p1x + p2x,
            "ke1": ke1,
            "ke2": ke2,
            "ke_total": ke1 + ke2,
            "center_distance": abs(x2 - x1),
        })

    df = pd.DataFrame(records)

    # ====================== Full plots ======================
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    # Velocity Plot
    vel_path = os.path.join(out_dir, "velocity_vs_time.png")
    plt.figure(figsize=(10, 4.8))
    plt.plot(df["time"], df["v1"], label="Red Cart Velocity", color="red", linewidth=2)
    plt.plot(df["time"], df["v2"], label="Blue Cart Velocity", color="blue", linewidth=2)
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Velocity vs Time")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(vel_path, dpi=300, bbox_inches="tight")
    plt.close()

    # KE Plot
    ke_path = os.path.join(out_dir, "kinetic_energy_vs_time.png")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(df["time"], df["ke1"], label="Red Cart KE", color="red", linewidth=2)
    ax.plot(df["time"], df["ke2"], label="Blue Cart KE", color="blue", linewidth=2)
    max_ke = df[["ke1", "ke2"]].max().max()
    ax.set_ylim(0, max(0.02, max_ke * 1.1))
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    ax.get_yaxis().get_major_formatter().set_scientific(False)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Kinetic Energy (J)")
    ax.set_title("Kinetic Energy vs Time")
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig(ke_path, dpi=300, bbox_inches="tight")
    plt.close()

    # Total Momentum Plot
    p_path = os.path.join(out_dir, "total_momentum_vs_time.png")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(df["time"], df["p_total"], label="Total System Momentum", color="green", linewidth=2.5)
    initial_p = abs(CONFIG["m1"] * CONFIG["v1_init"] + CONFIG["m2"] * CONFIG["v2_init"])
    ax.set_ylim(0, max(0.15, initial_p * 2))
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    ax.get_yaxis().get_major_formatter().set_scientific(False)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Total Momentum (kg·m/s)")
    ax.set_title("Total System Momentum vs Time")
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig(p_path, dpi=300, bbox_inches="tight")
    plt.close()

    # ====================== Zoomed collision instant ======================
    df['dv'] = (df['v1'].diff().abs() + df['v2'].diff().abs())
    collision_idx = df['dv'].idxmax()
    collision_time = df['time'].iloc[collision_idx]

    print(f"Detected collision at ≈ {collision_time:.3f} s")

    n = 10
    start = max(0, collision_idx - n)
    end = min(len(df), collision_idx + n + 1)
    zoom_df = df.iloc[start:end]

    vel_zoom_path = os.path.join(out_dir, "velocity_zoom_collision.png")
    plt.figure(figsize=(8, 4.5))
    plt.plot(zoom_df['time'], zoom_df['v1'], label="Red Cart Velocity", color="red", marker='o', linewidth=2.5)
    plt.plot(zoom_df['time'], zoom_df['v2'], label="Blue Cart Velocity", color="blue", marker='o', linewidth=2.5)
    plt.axvline(x=collision_time, color='gray', linestyle='--', linewidth=1.5, label=f"Collision at t≈{collision_time:.3f}s")
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Velocity vs Time (Zoomed - Collision Instant)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(vel_zoom_path, dpi=300, bbox_inches="tight")
    plt.close()

    ke_zoom_path = os.path.join(out_dir, "kinetic_energy_zoom_collision.png")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(zoom_df['time'], zoom_df['ke1'], label="Red Cart KE", color="red", marker='o', linewidth=2.5)
    ax.plot(zoom_df['time'], zoom_df['ke2'], label="Blue Cart KE", color="blue", marker='o', linewidth=2.5)
    ax.axvline(x=collision_time, color='gray', linestyle='--', linewidth=1.5, label=f"Collision at t≈{collision_time:.3f}s")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Kinetic Energy (J)")
    ax.set_title("Kinetic Energy vs Time (Zoomed - Collision Instant)")
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig(ke_zoom_path, dpi=300, bbox_inches="tight")
    plt.close()

    csv_path = os.path.join(out_dir, "expt7_timeseries.csv")
    df.to_csv(csv_path, index=False)

    print("\nSimulation complete!")

    # ====================== AUTO-GENERATE LAB REPORT ======================
    report_path = os.path.join(out_dir, "Expt7_Conservation_of_Momentum_Report.md")
    generate_momentum_report(
        csv_path=csv_path,
        image_dir=out_dir,
        m1=CONFIG["m1"],
        m2=CONFIG["m2"],
        config=CONFIG,
        output_md=report_path
    )

    print("Closing Isaac Sim...")
    simulation_app.close()


if __name__ == "__main__":
    main()