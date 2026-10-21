"""Schema of the neoclassical_townhouse template (style C, schema_version 1.1). 1-based floors.

Opening `height` runs from the sill to the crown; an arch head has radius width/2 and springs at
sill + height - width/2.
"""

from typing import Literal

from pydantic import Field

from exterior_agent.domain.modern import FrontYard
from exterior_agent.domain.params import Choice, Count, Flag, Length, Scalar, Strict


class ClassicBalcony(Strict):
    kind: Literal["iron_belly", "balustrade", "round_iron", "iron_straight"]
    projection: Length
    rail_height: Length


class ClassicOpening(Strict):
    id: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    kind: Literal["door", "window", "door_wood"]
    head: Literal["flat", "arch"] = "flat"
    offset: Length
    width: Length
    height: Length
    sill: Length
    balcony: ClassicBalcony | None = None
    hood: Flag | None = None
    keystone: Flag | None = None


class ClassicFloor(Strict):
    height: Length
    openings_front: list[ClassicOpening] = Field(default_factory=list)
    openings_rear: list[ClassicOpening] = Field(default_factory=list)


class Pediment(Strict):
    height: Length
    ornament: Flag


class Bay(Strict):
    side: Choice  # "left" | "right": the bay starts at that edge of the footprint
    width: Length
    projection: Length
    from_floor: Count  # the loggia floor (open front, columns)
    to_floor: Count
    columns: Flag
    column_radius: Length
    pediment: Pediment | None = None


class Pilasters(Strict):
    width: Length
    depth: Length


class Cornices(Strict):
    height: Length
    depth: Length
    dentils: Flag


class GableFront(Strict):
    oculus_radius: Length
    ornament: Flag


class ClassicRoof(Strict):
    pitch_deg: Scalar
    overhang: Length
    thickness: Length
    gable_front: GableFront
    gutters: Flag


class ClassicBuilding(Strict):
    footprint_width: Length
    footprint_depth: Length
    wall_thickness: Length
    slab_thickness: Length
    floors: list[ClassicFloor]
    bay: Bay | None = None
    pilasters: Pilasters | None = None
    cornices: Cornices
    roof: ClassicRoof
    front_yard: FrontYard
