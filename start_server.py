"""
Launch script — starts the WebRTC + WebSocket server inside Isaac Sim.

Usage (Isaac Sim Script Editor):
    Run this file in the Script Editor.

Usage (standalone):
    python start_server.py
"""
import sys
import os
import asyncio


def _is_project_root(path: str) -> bool:
    return (
        os.path.isdir(path)
        and os.path.exists(os.path.join(path, "configs", "server.py"))
        and os.path.exists(os.path.join(path, "core", "webrtc_server.py"))
    )


def _detect_project_root() -> str:
    candidates = []

    env_root = os.environ.get("AI_PHYSICS_PROJECT_ROOT")
    if env_root:
        candidates.append(env_root)

    try:
        candidates.append(os.getcwd())
    except Exception:
        pass

    if "__file__" in globals():
        try:
            file_dir = os.path.dirname(os.path.abspath(__file__))
            candidates.append(file_dir)
            candidates.append(os.path.dirname(file_dir))
        except Exception:
            pass

    # Workspace default for this deployment
    candidates.append("/125090599")

    for candidate in candidates:
        if _is_project_root(candidate):
            return candidate

    raise RuntimeError(
        "Could not detect project root. Set AI_PHYSICS_PROJECT_ROOT or run from the repo root."
    )


PROJECT_ROOT = _detect_project_root()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 60)
print("  AI Physics Experiment Platform — WebRTC Server")
print("=" * 60)

# ---------------------------------------------------------------
# Persistent holder so re-running the script in Script Editor
# properly tears down the previous instance.
# ---------------------------------------------------------------
import types

_HOLDER_KEY = "__ai_physics_server_holder__"

class _ServerHolder:
    instance = None
    monitor_sub = None

if _HOLDER_KEY not in sys.modules:
    mod = types.ModuleType(_HOLDER_KEY)
    setattr(mod, "_ServerHolder", _ServerHolder)
    sys.modules[_HOLDER_KEY] = mod
else:
    _ServerHolder = getattr(sys.modules[_HOLDER_KEY], "_ServerHolder")


async def _cleanup():
    if _ServerHolder.instance is not None:
        print("  Stopping previous server instance ...")
        old = _ServerHolder.instance
        try:
            if hasattr(old, "pcs") and old.pcs:
                await asyncio.gather(*(pc.close() for pc in old.pcs), return_exceptions=True)
            await old.stop()
        except Exception as e:
            print(f"  (cleanup warning: {e})")
        finally:
            _ServerHolder.instance = None
    _ServerHolder.monitor_sub = None


async def _start():
    await _cleanup()

    # Force-reload our modules so re-running in Script Editor always
    # picks up the latest code from disk.
    import importlib
    for mod_name in list(sys.modules):
        if mod_name.startswith(("configs", "core.webrtc_server")):
            try:
                del sys.modules[mod_name]
            except KeyError:
                pass

    from configs.server import HTTP_HOST, HTTP_PORT, WS_PORT, HOST_IP
    from core.webrtc_server import WebRTCServer

    server = WebRTCServer(host=HTTP_HOST, http_port=HTTP_PORT, ws_port=WS_PORT)
    await server.start()
    _ServerHolder.instance = server

    print()
    print("=" * 60)
    print("  Server running!")
    print(f"  WebRTC signaling : http://{HOST_IP}:{HTTP_PORT}/offer")
    print(f"  WebSocket control: ws://{HOST_IP}:{WS_PORT}/")
    print(f"  Frontend          : cd frontend && npm run dev")
    print("=" * 60)

    # Lightweight monitor on Kit update loop (if available)
    try:
        import omni.kit.app
        _count = [0]
        def _on_update(event):
            _count[0] += 1
            if _count[0] % 600 == 0 and server.video_track:
                t = server.video_track
                if not t.use_replicator:
                    print(f"  [monitor] Replicator not active ({t.width}x{t.height})")
        app = omni.kit.app.get_app()
        sub = app.get_update_event_stream().create_subscription_to_pop(_on_update)
        _ServerHolder.monitor_sub = sub
    except Exception:
        pass


def stop_server():
    asyncio.ensure_future(_cleanup())
    print("Server stopped.")


def get_server():
    return _ServerHolder.instance


# Auto-start
asyncio.ensure_future(_start())
