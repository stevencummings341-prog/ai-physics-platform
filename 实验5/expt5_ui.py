import gradio as gr
import subprocess
import os
import shutil
from pathlib import Path

def run_simulation(m, L, x, theta0_deg, sim_time):
    cmd = [
        "python",
        "expt5_pendulum_sim.py",
        f"--m={m}",
        f"--L={L}",
        f"--x={x}",
        f"--theta0={theta0_deg}",
        f"--sim_time={sim_time}",
    ]
    subprocess.run(cmd, cwd=os.getcwd(), check=True)

    out_dirs = sorted(Path(".").glob("outputs_expt5_*"), reverse=True)
    latest_dir = out_dirs[0]

    zip_path = shutil.make_archive(str(latest_dir), "zip", root_dir=str(latest_dir))

    return (
        str(latest_dir / "angle_vs_time.png"),
        str(latest_dir / "angular_velocity_vs_time.png"),
        str(latest_dir / "angle_zoom.png"),
        zip_path,
    )

with gr.Blocks(title="Expt_5 Physical Pendulum") as demo:
    gr.Markdown("# Physical Pendulum - Auto Report (Rotational Inertia)")

    with gr.Row():
        m = gr.Slider(0.05, 1.0, value=0.28, step=0.01, label="Pendulum Bar Mass m (kg)")
        L = gr.Slider(0.1, 1.0, value=0.28, step=0.01, label="Bar Length L (m)")

    with gr.Row():
        x = gr.Slider(0.01, L.value/2, value=0.10, step=0.01, label="Pivot Distance from CM x (m)")
        theta0_deg = gr.Slider(1.0, 15.0, value=5.0, step=0.5, label="Initial Angle θ₀ (deg) - small angle")

    sim_time = gr.Slider(5.0, 30.0, value=15.0, step=1.0, label="Simulation Time (s)")

    btn = gr.Button("Run Pendulum Simulation", variant="primary", size="large")

    with gr.Row():
        angle_plot = gr.Image(label="Angle θ vs Time")
        angvel_plot = gr.Image(label="Angular Velocity vs Time")

    with gr.Row():
        angle_zoom = gr.Image(label="Angle - One Period Zoom")

    download_zip = gr.File(label="Download All Outputs (.zip)")

    btn.click(
        run_simulation,
        inputs=[m, L, x, theta0_deg, sim_time],
        outputs=[angle_plot, angvel_plot, angle_zoom, download_zip],
    )

demo.launch(server_name="0.0.0.0", server_port=7865, share=False)