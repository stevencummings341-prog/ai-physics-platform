# 2026-04-28 — Post-Presentation Cleanup

## TL;DR

Stripped the working tree back to **platform architecture only**. The
final-presentation deck, the teleprompter speech script, the build scripts
that produced them, and the situational backup checklist — all artefacts of
the end-of-term video — were removed from the repository. They live on in
the offline backup tarball produced earlier the same day.

A single-file durable AI memory dump (`docs/AI_CONTRIBUTION_ARCHIVE.md`,
1,319 lines) is **kept** in git as the canonical record of everything AI
agents did across the 33-day project.

The platform itself — every line of code, every USD asset, every
documentation artefact that defines the experiment platform — is unchanged.

## Motivation

The project owner asked for a clean architecture before pushing to
`stevencummings341-prog/ai-physics-platform`. Two distinct concerns were
mixing in the working tree:

1. The **AI Physics Experiment Platform** — durable, every commit a step
   forward in capability.
2. The **end-of-term video production** — one-shot toolchain (PPTX builder,
   speech-script PDF builder, backup script, situational checklists).

The latter does not belong in the platform repo. Future agents reading this
project should see the platform, not the production-week scaffolding.

## What was removed

```
- tools/build_presentation.py        (1,200 LOC; never tracked)
- tools/build_speech_script.py       (470 LOC;   never tracked)
- tools/backup.sh                    (160 LOC;   never tracked)
- docs/BACKUP_BEFORE_SHUTDOWN.md     (253 lines; never tracked)
- outputs/                           (68 MB of generated artefacts; gitignored already)
- .vite.log, .isaacsim.log           (runtime logs; gitignored already)
- .vite.pid, .isaacsim.pid, .frontend.pid (PID files; gitignored already)
- .share/                            (tunnel state; gitignored already)
```

The first four items were **untracked** in git, so removing them is purely
filesystem cleanup; nothing changes in the GitHub remote until this commit
adds the kept document.

The last four lines were already gitignored. Cleaning them locally is a
courtesy to the next person who runs `ls`.

## What was added

```
+ docs/AI_CONTRIBUTION_ARCHIVE.md    (1,319 lines)
+ docs/handoff/2026-04-28-post-presentation-cleanup.md   (this file)
```

`AI_CONTRIBUTION_ARCHIVE.md` consolidates 17 handoffs + 4 ADRs +
`AGENTS.md` + `state/active_context.json` into one self-contained
document. Read order, file manifest, every per-experiment summary, every
ADR (full text), the resurrection guide, and the team-contribution map —
all in one file, ~75 KB. It opens with a post-cleanup note so a future
reader does not get confused by references to `outputs/` or `tools/` paths
that the cleanup commit removed.

## Final repository layout

```
/                       (project root)
├── README.md           # One-page project overview + quick start
├── AGENTS.md           # AI-agent operating instructions
├── requirements.txt    # Python deps
├── .gitignore
├── .cursor/rules/      # Cursor rule files (project / handoff / deep-thinking / isaac-sim)
│
├── launch.sh           # One-click frontend
├── start_isaac.sh      # Isaac Sim launcher (VNC/DISPLAY-aware)
├── start_server.py     # Script-Editor entry; force-reloads core.* on re-run
├── share.sh            # Public-tunnel manager (bore.pub default, lhr fallback)
├── setup.sh            # Environment install
├── bootstrap.sh        # SSH key + git config bootstrap
├── run.py              # Batch-mode CLI (expt 1, 2, 3)
│
├── core/               # Backend framework
│   ├── webrtc_server.py        # 7,233 LOC; all WS + RTC + 8 experiment dispatchers
│   ├── experiment_base.py      # ABC for batch experiments
│   ├── scene.py / recorder.py / reporter.py
│   ├── vr.py / vr_hand_receiver.py     # parked
│   └── exp{2,4,5,8}*.py        # Per-experiment analysis pipelines
│
├── configs/server.py   # Centralised configuration (env-var overridable)
├── frontend/           # React 19 + TypeScript + Vite + Tailwind
├── experiments/        # Batch experiment subpackages
├── Experiment/         # USD scene assets
├── report_templates/   # Jinja2 Markdown templates for lab reports
├── camera/             # Camera presets (dev-time helpers)
├── vr/                 # Quest 3S Unity app code (parked)
├── launchers/bin/      # Statically-linked binaries (bore for share.sh)
│
├── docs/
│   ├── START_HERE.md                  # Canonical entry for new agent sessions
│   ├── PROJECT_STATE.md               # Current snapshot
│   ├── ROADMAP.md                     # 5-phase plan
│   ├── AI_CONTRIBUTION_ARCHIVE.md     # Single-file durable AI memory
│   ├── adr/                           # 4 architecture decision records
│   ├── handoff/                       # 18 dated session notes (this file is the latest)
│   ├── experiments/                   # Per-experiment notes
│   ├── templates/                     # Startup / closeout templates
│   ├── reference/                     # PHY1002 lab manuals
│   └── legacy/                        # Preserved teammate code (post-integration)
│
└── state/
    ├── active_context.json            # Machine-readable current status
    └── artifact_manifest.json         # Canonical entry-points + roots
```

25 entries at the root, each with one clear purpose. Down from 28 (deleted
`outputs/`, `tools/`, `.share/`) plus three orphan PID/log files.

## Verification

| Check | Result |
|---|---|
| `python3 -c "import ast; ast.parse(...)"` on every kept .py | ✅ all OK |
| `npx tsc --noEmit` (frontend) | ✅ no errors |
| `npx vite build` | ✅ clean |
| `git status` after commit | ✅ working tree clean |
| `git push origin master` | ✅ pushed to GitHub |
| `ls /125090599` | ✅ 25 entries, no noise |
| Reading `docs/AI_CONTRIBUTION_ARCHIVE.md` from scratch | ✅ self-sufficient; deleted-path note up-front |

## What lives in the offline backup, not in the repo

Everything below was preserved in `~/physics_platform_backup_*.tar.gz`
before this cleanup, so removing them from the repo is non-destructive:

- `outputs/Final_Presentation.pptx` (27 slides, mixed Chinese/English)
- `outputs/Speech_Script.pdf` (10 pages, teleprompter style)
- `outputs/preview/` (PNG of every deck slide + every script page)
- `outputs/expt*_web_*.zip` (lab-report archives from real runs of Exp 2/4/5/6/8)
- `tools/build_presentation.py` / `tools/build_speech_script.py` / `tools/backup.sh`
- The 12 Cursor agent-transcript directories (`/root/.cursor/projects/125090599/agent-transcripts/`)
- `.isaacsim.log` (last runtime evidence)

If any of these is ever needed back in the platform repo (it shouldn't be),
restore from the backup tarball.

## For future agents

- Treat this commit as the canonical "platform-only" baseline. Every future
  experiment / feature commit builds on top of this layout.
- If you need to produce another PPT/PDF/B-roll for the project, do it in a
  **separate** repo or directory; do not pollute this one with one-shot
  presentation tooling again.
- The single source of truth for "what AI agents did" is now
  `docs/AI_CONTRIBUTION_ARCHIVE.md`. Any new substantial AI work should be
  recorded as a new handoff under `docs/handoff/` and, if architecturally
  significant, also as a section update or appendix to the archive.
- `docs/handoff/LATEST.md` now points to this file as the most recent
  relevant handoff.
