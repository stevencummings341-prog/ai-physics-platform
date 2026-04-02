import gradio as gr
import subprocess
import os
from pathlib import Path


def run_simulation(damping, small_amp, large_amp, amp_start, amp_end, amp_step):
    cmd = [
        "python",
        "expt2_large_amplitude_pendulum_sim_fixed.py",
        f"--damping={damping}",
        f"--small_amp={small_amp}",
        f"--large_amp={large_amp}",
        f"--amp_start={amp_start}",
        f"--amp_end={amp_end}",
        f"--amp_step={amp_step}",
    ]
    subprocess.run(cmd, cwd=os.getcwd(), check=True)

    # ==================== Find latest output folder ====================
    out_dirs = sorted(
        [p for p in Path(".").glob("outputs_expt2_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not out_dirs:
        raise FileNotFoundError("No outputs_expt2_* folder found!")

    latest_dir = out_dirs[0]

    zip_path = str(latest_dir) + ".zip"
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    return (
        str(latest_dir / "small_amp_plot.png"),
        str(latest_dir / "large_amp_plot.png"),
        str(latest_dir / "small_vs_large_theta.png"),
        str(latest_dir / "period_vs_amplitude.png"),
        str(latest_dir / "small_angle_error.png"),
        str(latest_dir / "Expt2_Large_Amplitude_Pendulum_Report.md"),
        zip_path,
    )


with gr.Blocks(title="Expt_2 Large Amplitude Pendulum") as demo:
    gr.Markdown("# Large Amplitude Pendulum - Auto Lab Report")

    with gr.Row():
        damping = gr.Slider(0.0, 0.02, value=0.0025, step=0.0005, label="Damping Coefficient")
        small_amp = gr.Slider(0.05, 0.50, value=0.20, step=0.01, label="Small Amplitude (rad)")
        large_amp = gr.Slider(1.60, 3.00, value=2.80, step=0.05, label="Large Amplitude (rad)")

    with gr.Row():
        amp_start = gr.Slider(0.20, 1.00, value=0.20, step=0.05, label="Sweep Start (rad)")
        amp_end = gr.Slider(1.00, 2.40, value=2.40, step=0.05, label="Sweep End (rad)")
        amp_step = gr.Slider(0.05, 0.40, value=0.20, step=0.05, label="Sweep Step (rad)")

    btn = gr.Button("🚀 Run Pendulum Simulation", variant="primary", size="large")

    with gr.Row():
        img1 = gr.Image(label="Small Amplitude Plot")
        img2 = gr.Image(label="Large Amplitude Plot")

    with gr.Row():
        img3 = gr.Image(label="Small vs Large Displacement")
        img4 = gr.Image(label="Period vs Amplitude")
        img5 = gr.Image(label="Small-Angle Error")

    report = gr.File(label="Download Markdown Report")
    zip_file = gr.File(label="Download All Outputs (.zip)")

    btn.click(
        run_simulation,
        inputs=[damping, small_amp, large_amp, amp_start, amp_end, amp_step],
        outputs=[img1, img2, img3, img4, img5, report, zip_file],
    )

demo.launch(server_name="0.0.0.0", server_port=7861, share=False)