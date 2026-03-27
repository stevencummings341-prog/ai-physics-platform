"""Reusable scene construction helpers for Isaac Sim experiments."""

from __future__ import annotations

import numpy as np
from isaacsim.core.api.objects import FixedCuboid, VisualCuboid
from isaacsim.core.api.materials import PhysicsMaterial
from pxr import UsdLux


class SceneBuilder:
    """Provides commonly needed scene elements so experiments don't duplicate code."""

    def __init__(self, world, stage):
        self.world = world
        self.stage = stage

    # --------------------------------------------------------------- lighting
    def add_dome_light(self, intensity: float = 1500.0, path: str = "/World/DomeLight"):
        UsdLux.DomeLight.Define(self.stage, path).CreateIntensityAttr(intensity)

    # --------------------------------------------------------------- materials
    @staticmethod
    def frictionless_material(
        prim_path: str = "/World/Materials/Frictionless",
        restitution: float = 1.0,
    ) -> PhysicsMaterial:
        return PhysicsMaterial(
            prim_path=prim_path,
            static_friction=0.0,
            dynamic_friction=0.0,
            restitution=restitution,
        )

    # ----------------------------------------------------------------- track
    def add_track(
        self,
        length: float = 8.0,
        width: float = 0.30,
        height: float = 0.10,
        material: PhysicsMaterial | None = None,
        color: np.ndarray | None = None,
    ) -> float:
        """Add a horizontal track at Z=0.  Returns the Z of the track top surface."""
        if color is None:
            color = np.array([0.15, 0.15, 0.18])
        top_z = 0.0

        self.world.scene.add(
            FixedCuboid(
                prim_path="/World/Track",
                name="track",
                position=np.array([0.0, 0.0, top_z - height / 2]),
                scale=np.array([length, width, height]),
                color=color,
                physics_material=material,
            )
        )

        rail_h = 0.04
        for sign, tag in [(1, "Left"), (-1, "Right")]:
            self.world.scene.add(
                FixedCuboid(
                    prim_path=f"/World/Rail{tag}",
                    name=f"rail_{tag.lower()}",
                    position=np.array([0.0, sign * width / 2, top_z + rail_h / 2]),
                    scale=np.array([length, 0.01, rail_h]),
                    color=np.array([0.30, 0.30, 0.35]),
                    physics_material=material,
                )
            )
        return top_z

    # ----------------------------------------------------------- grid marks
    def add_grid_markings(
        self,
        track_width: float = 0.30,
        x_range: tuple[float, float] = (-4.0, 4.0),
        spacing: float = 0.5,
        z: float = 0.001,
    ):
        """Visual-only tick marks on track surface (no collision)."""
        for i, x in enumerate(np.arange(x_range[0], x_range[1] + 0.01, spacing)):
            is_origin = abs(x) < 1e-6
            color = np.array([0.95, 0.85, 0.2]) if is_origin else np.array([0.50, 0.50, 0.50])
            w = 0.01 if is_origin else 0.005
            self.world.scene.add(
                VisualCuboid(
                    prim_path=f"/World/GridMark_{i}",
                    name=f"grid_mark_{i}",
                    position=np.array([float(x), 0.0, z]),
                    scale=np.array([w, track_width, 0.001]),
                    color=color,
                )
            )

    # -------------------------------------------------------------- floor
    def add_ground_plane(
        self,
        size: float = 20.0,
        z: float = -0.25,
        color: np.ndarray | None = None,
        material: PhysicsMaterial | None = None,
    ):
        if color is None:
            color = np.array([0.10, 0.10, 0.12])
        self.world.scene.add(
            FixedCuboid(
                prim_path="/World/GroundPlane",
                name="ground_plane",
                position=np.array([0.0, 0.0, z]),
                scale=np.array([size, size, 0.02]),
                color=color,
                physics_material=material,
            )
        )
