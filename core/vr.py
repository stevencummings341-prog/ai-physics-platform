"""VR streaming bridge — enables Isaac Sim LiveStream for VR headset connection.

Integration path:
  1. Enable LiveStream extension in Isaac Sim
  2. Connect VR headset via Omniverse Streaming Client or CloudXR
  3. Map controller inputs to experiment config overrides and reset triggers

This module provides the scaffolding; full implementation depends on
the VR hardware and Omniverse streaming stack version.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger(__name__)


class VRBridge:
    """Manages VR streaming connection and controller event routing."""

    def __init__(self, enable: bool = False):
        self.enabled = enable
        self._callbacks: dict[str, list[Callable]] = {}

        if self.enabled:
            self._init_livestream()

    def _init_livestream(self):
        try:
            from omni.isaac.core.utils.extensions import enable_extension
            enable_extension("omni.kit.livestream.native")
            log.info("LiveStream extension enabled — ready for VR headset connection.")
        except ImportError:
            log.warning(
                "Could not enable LiveStream. "
                "Ensure omni.isaac.core is available and the extension is installed."
            )
            self.enabled = False

    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Register a callback for a VR controller event."""
        self._callbacks.setdefault(event_name, []).append(callback)

    def emit(self, event_name: str, **kwargs: Any) -> None:
        """Dispatch an event to all registered callbacks."""
        for cb in self._callbacks.get(event_name, []):
            cb(**kwargs)

    def poll_controller_inputs(self) -> dict[str, Any]:
        """Poll VR controller state. Stub — implement per hardware."""
        return {}
