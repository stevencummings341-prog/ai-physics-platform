# AI Physics Experiment Platform

## What Lives Where

```text
/125090599
├── core/                 # Shared engine code used by all experiments
├── experiments/          # One folder per experiment
│   ├── expt1_angular_momentum/
│   └── expt7_momentum/
├── report_templates/     # Markdown report templates
├── outputs/              # Auto-generated experiment results
├── run.py                # Unified non-interactive launcher
├── expt1_angular_momentum_sim.py   # Interactive launcher for experiment 1
├── expt7_momentum_sim.py           # Interactive launcher for experiment 7
├── requirements.txt
├── AGENTS.md
└── .cursor/rules/        # Persistent AI rules
```

## Recommended Run Commands

### Interactive mode

```bash
cd /125090599
python expt1_angular_momentum_sim.py
python expt7_momentum_sim.py
```

### Unified CLI mode

```bash
cd /125090599
python run.py expt1_angular_momentum
python run.py expt7_momentum
```

## Output Policy

- Every run writes a timestamped folder under `outputs/`
- It is safe to delete old output folders when you no longer need them
- Source code and configs are stored outside `outputs/`

## Saving Your Work

- If you are connected over SSH, files remain on the server after you disconnect
- Closing SSH does **not** delete saved files
- Unsaved editor changes can still be lost, so always make sure the file is written to disk
- For durable version history, use git commits
- For local backup, copy the project back with `scp` or `rsync`
