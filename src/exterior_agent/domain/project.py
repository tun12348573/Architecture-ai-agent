"""Pydantic schema for project.json. Every design value carries provenance (Param)."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from exterior_agent.domain.units import LENGTH_UNITS

Status = Literal["needs_review", "confirmed"]
WallName = Literal["front", "rear", "left", "right"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Original(Strict):
    value: float
    unit: str


class Param[T](Strict):
    value: T
    unit: str | None
    source: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    status: Status
    original: Original | None = None


class Length(Param[float]):
    @field_validator("unit")
    @classmethod
    def _known_unit(cls, unit: str | None) -> str | None:
        if unit not in LENGTH_UNITS:
            raise ValueError(f"length unit must be one of {sorted(LENGTH_UNITS)}")
        return unit

    @field_validator("value")
    @classmethod
    def _finite_non_negative(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        if value < 0:
            raise ValueError("must not be negative")
        return value


class Count(Param[int]):
    @field_validator("unit")
    @classmethod
    def _count_unit(cls, unit: str | None) -> str | None:
        if unit != "count":
            raise ValueError("unit must be 'count'")
        return unit


class Choice(Param[str]):
    @field_validator("unit")
    @classmethod
    def _no_unit(cls, unit: str | None) -> str | None:
        if unit is not None:
            raise ValueError("unit must be null for a choice")
        return unit


class MaterialSpec(Strict):
    base_color: tuple[float, float, float]
    roughness: float = Field(ge=0, le=1)
    alpha: float = Field(default=1.0, ge=0, le=1)

    @field_validator("base_color")
    @classmethod
    def _unit_range(cls, rgb: tuple[float, float, float]) -> tuple[float, float, float]:
        if not all(0 <= c <= 1 for c in rgb):
            raise ValueError("colour components must be within 0..1")
        return rgb


class MaterialParam(Param[MaterialSpec]):
    @field_validator("unit")
    @classmethod
    def _no_unit(cls, unit: str | None) -> str | None:
        if unit is not None:
            raise ValueError("unit must be null for a material")
        return unit


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
    schema_version: Literal["1.0"]
    project_id: str = Field(pattern=r"^[a-z0-9-]+$")
    project_revision: int = Field(ge=1)
    input_mode: str
    label: str
    site: Site
    building: Building
    materials: Materials
    cameras: list[CameraDef] = Field(default_factory=lambda: list(CANONICAL_CAMERAS))
    render_profile: Literal["preview", "final", "smoke"] = "preview"
