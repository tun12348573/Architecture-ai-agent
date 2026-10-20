"""Pydantic schema for project.json. Every design value carries provenance (Param)."""

from typing import Literal

from pydantic import Field

from exterior_agent.domain.modern import ModernBuilding, StreetContext
from exterior_agent.domain.params import (  # noqa: F401 - re-exported for existing imports
    Choice,
    Count,
    Flag,
    Length,
    MaterialParam,
    MaterialSpec,
    Original,
    Param,
    Scalar,
    Status,
    Strict,
    StrictFloat,
    StrictInt,
)

WallName = Literal["front", "rear", "left", "right"]


class Site(Strict):
    width: Length
    depth: Length
    front_setback: Length
    rear_setback: Length


class Roof(Strict):
    type: Choice
    thickness: Length


class Opening(Strict):
    id: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    kind: Literal["door", "window"]
    wall: WallName
    offset: Length
    width: Length
    height: Length
    sill: Length


class Building(Strict):
    footprint_width: Length
    footprint_depth: Length
    floors: Count
    wall_height: Length
    wall_thickness: Length
    roof: Roof
    openings: list[Opening]


class Materials(Strict):
    wall: MaterialParam
    roof: MaterialParam
    door: MaterialParam
    window_glass: MaterialParam
    land: MaterialParam
    context_ground: MaterialParam
    # Extra roles used by the modern_townhouse template (required there, see modern_rules).
    frame: MaterialParam | None = None
    aluminium: MaterialParam | None = None
    louver: MaterialParam | None = None
    terrace_floor: MaterialParam | None = None
    paving: MaterialParam | None = None
    grass: MaterialParam | None = None
    soil: MaterialParam | None = None
    pergola_wood: MaterialParam | None = None
    props: MaterialParam | None = None
    # Street context and cladding roles (M2c, required only when used).
    cladding: MaterialParam | None = None
    asphalt: MaterialParam | None = None
    sidewalk: MaterialParam | None = None
    kerb: MaterialParam | None = None
    road_marking: MaterialParam | None = None
    neighbour_wall: MaterialParam | None = None
    neighbour_glass: MaterialParam | None = None


class World(Strict):
    hdri: Choice  # asset id of kind "hdri"
    strength: Scalar
    rotation_deg: Scalar


class CameraDef(Strict):
    id: str
    view: str


CANONICAL_CAMERA_IDS = (
    "01_front",
    "02_rear",
    "03_left",
    "04_right",
    "05_front_left",
    "06_front_right",
    "07_rear_left",
    "08_rear_right",
    "09_top",
    "10_aerial",
)
CANONICAL_CAMERAS = [CameraDef(id=c, view=c[3:]) for c in CANONICAL_CAMERA_IDS]


class Project(Strict):
    schema_version: Literal["1.0", "1.1"]
    project_id: str = Field(pattern=r"^[a-z0-9-]+$")
    project_revision: int = Field(ge=1, strict=True)
    input_mode: str
    label: str
    template: Literal["basic_house", "modern_townhouse"] = "basic_house"
    site: Site
    building: Building | None = None
    modern: ModernBuilding | None = None
    world: World | None = None
    context: StreetContext | None = None
    materials: Materials
    cameras: list[CameraDef] = Field(default_factory=lambda: list(CANONICAL_CAMERAS))
    render_profile: Literal["preview", "final", "smoke"] = "preview"
