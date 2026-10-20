"""Schema of the modern_townhouse template (schema_version 1.1). Floor indices are 1-based."""

from typing import Literal

from pydantic import Field

from exterior_agent.domain.params import Choice, Count, Flag, Length, Strict


class ModernOpening(Strict):
    id: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    kind: Literal["door", "window", "door_4leaf"]
    offset: Length
    width: Length
    height: Length
    sill: Length
    transom_height: Length | None = None


class Floor(Strict):
    height: Length
    front_setback: Length
    openings_front: list[ModernOpening] = Field(default_factory=list)
    openings_rear: list[ModernOpening] = Field(default_factory=list)
    terrace_pergola: Flag | None = None


class Balcony(Strict):
    floor: Count
    offset: Length
    width: Length
    depth: Length
    rail_height: Length
    slab_thickness: Length


class FacadeFrame(Strict):
    from_floor: Count
    to_floor: Count
    thickness: Length
    depth: Length


class Louvers(Strict):
    floor: Count
    offset: Length
    width: Length
    count: Count
    blade_width: Length
    blade_depth: Length


class Canopy(Strict):
    height: Length
    depth: Length
    thickness: Length


class StairHead(Strict):
    width: Length
    depth: Length
    height: Length


class RoofGarden(Strict):
    planter_width: Length
    planter_height: Length
    pergola: Flag
    plant_models: list[Choice] = Field(default_factory=list)  # asset ids of kind "model"


class ModernRoof(Strict):
    parapet_height: Length
    parapet_thickness: Length
    stair_head: StairHead
    garden: RoofGarden | None = None


class FrontYard(Strict):
    kind: Choice
    gate_width: Length
    gate_height: Length
    fence_height: Length
    car: Flag
    motorbikes: Count


class Cladding(Strict):
    zone: Choice  # "ground_front": floor-1 front wall around its openings
    thickness: Length


class Neighbours(Strict):
    per_side: Count
    seed: Count


class ContextModels(Strict):
    tree: Choice  # asset ids of kind "model"
    lamp: Choice
    pot: Choice


class StreetContext(Strict):
    """Illustrative street around the lot (never measured data)."""

    front: Choice  # "road" | "park"
    sidewalk_width: Length
    road_width: Length
    neighbours: Neighbours | None = None
    street_lamps: Flag
    street_trees: Flag
    pots: Flag
    models: ContextModels


class ModernBuilding(Strict):
    footprint_width: Length
    footprint_depth: Length
    wall_thickness: Length
    slab_thickness: Length
    floors: list[Floor]
    balconies: list[Balcony] = Field(default_factory=list)
    frames: list[FacadeFrame] = Field(default_factory=list)
    louvers: list[Louvers] = Field(default_factory=list)
    canopy: Canopy | None = None
    cladding: Cladding | None = None
    roof: ModernRoof
    front_yard: FrontYard
