# Session context anchor (do not lose this)

**Purpose:** Short memory for agents after context window resets. Read `docs/handoff/LATEST.md` → this file → `state/active_context.json` → `continuity_snapshot`.

## What we are building

Full-stack **AI Physics Experiment Platform**: React frontend (`frontend/`) + Isaac Sim in-process server (`core/webrtc_server.py` via `start_server.py`). User goal: **operate experiments (especially exp1 angular momentum) from the web** with live video and telemetry.

## Canonical paths (this deployment)

- **Project root:** `/125090599` (contains `launch.sh`, `start_server.py`, `frontend/`, `core/`, `Experiment/`)
- **GitHub remote:** `stevencummings341-prog/ai-physics-platform` (branch `master`)

## Run workflow (every session)

1. **Frontend (cloud / any machine with Node):**  
   `cd /125090599 && ./launch.sh`  
   Serves **:5173**.

2. **Backend (only inside Isaac Sim, on a machine with GPU + Kit):**  
   **Window → Script Editor** → run:
   ```python
   exec(open("/125090599/start_server.py").read())
   ```
   Binds **HTTP :8080** (WebRTC offer) and **WebSocket :30000**.

3. **Browser:**  
   - Same host: `http://127.0.0.1:5173`  
   - Remote cloud: `http://<server-public-ip>:5173` **or** SSH tunnel:  
     `ssh -L 5173:127.0.0.1:5173 user@server` then `http://127.0.0.1:5173`  
   - If unreachable: open firewall / security group for **5173** (and **8080**, **30000** for Isaac).

**Note:** Isaac Sim is **not** started by a random `python` in `conda base`; it is the **Isaac Sim application**, then Python runs inside Script Editor.

## Experiment status (snapshot)

| Exp | Web usable | Notes |
|-----|------------|--------|
| 1 | Yes | Angular momentum — primary user target |
| 2 | Yes | Large pendulum |
| 7 | UI on; server wiring vs USD may need work | Batch: `expt7_momentum` |
| 3–6, 8 | Frontend **locked** | Stubs only until USD + server completed |

Batch CLI path remains `run.py` + `ExperimentBase`; **not** the same process as the web server.

## User’s current situation (from chat)

- Shell prompt: `(base) root@...:/125090599#` — **correct project root**, no extra `aiphysics` folder required.
- Issues encountered: **browser couldn’t open** → usually wrong URL (must use server IP or SSH tunnel) or **ports closed**.
- **No `git clone` needed** if repo already lives at `/125090599`.

## Where full architecture is documented

- `docs/PROJECT_STATE.md` — diagram + ports + experiment table  
- `AGENTS.md` — how to add experiments  
- `docs/handoff/2026-03-29-fullstack-integration.md` — integration commit narrative  

---

*Update this anchor when workflow or deployment assumptions change.*
