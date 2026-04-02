import gradio as gr
import subprocess
import os
import shutil
from pathlib import Path


def run_simulation(m1, m2, v1, v2, restitution):
    cmd = [
        "python",
        "expt7_momentum_sim.py",
        f"--m1={m1}",
        f"--m2={m2}",
        f"--v1={v1}",
        f"--v2={v2}",
        f"--restitution={restitution}",
    ]
    subprocess.run(cmd, cwd=os.getcwd(), check=True)

    out_dirs = sorted(Path(".").glob("outputs_expt7_*"), reverse=True)
    latest_dir = out_dirs[0]

    zip_path = shutil.make_archive(str(latest_dir), "zip", root_dir=str(latest_dir))

    return (
        str(latest_dir / "velocity_vs_time.png"),
        str(latest_dir / "kinetic_energy_vs_time.png"),
        str(latest_dir / "total_momentum_vs_time.png"),
        str(latest_dir / "velocity_zoom_collision.png"),
        str(latest_dir / "kinetic_energy_zoom_collision.png"),
        zip_path,
    )


with gr.Blocks(title="Expt_7 Conservation of Momentum") as demo:
    gr.Markdown("# Conservation of Momentum - Auto Report")

    with gr.Row():
        m1 = gr.Slider(0.1, 2.0, value=0.25, step=0.05, label="Cart 1 Mass m1 (kg)")
        m2 = gr.Slider(0.1, 2.0, value=0.25, step=0.05, label="Cart 2 Mass m2 (kg)")

    with gr.Row():
        v1 = gr.Slider(-2.0, 2.0, value=0.40, step=0.05, label="Cart 1 Initial Velocity v1 (m/s)")
        v2 = gr.Slider(-2.0, 2.0, value=0.00, step=0.05, label="Cart 2 Initial Velocity v2 (m/s)")

    restitution = gr.Slider(
        0.0,
        1.0,
        value=0.0,
        step=0.05,
        label="Restitution Coefficient (0.0 = inelastic, 1.0 = elastic)",
    )

    btn = gr.Button("Run Collision Simulation", variant="primary", size="large")

    with gr.Row():
        vel = gr.Image(label="Velocity vs Time")
        ke = gr.Image(label="Kinetic Energy vs Time")

    with gr.Row():
        p_tot = gr.Image(label="Total System Momentum vs Time")
        vel_zoom = gr.Image(label="Velocity - Collision Instant (Zoomed)")
        ke_zoom = gr.Image(label="Kinetic Energy - Collision Instant (Zoomed)")

    download_zip = gr.File(label="Download All Outputs (.zip)")

    btn.click(
        run_simulation,
        inputs=[m1, m2, v1, v2, restitution],
        outputs=[vel, ke, p_tot, vel_zoom, ke_zoom, download_zip],
    )

demo.launch(server_name="0.0.0.0", server_port=7860, share=False)