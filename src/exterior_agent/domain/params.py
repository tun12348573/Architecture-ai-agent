"""Provenance-carrying value types shared by every project schema."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from exterior_agent.domain.units import LENGTH_UNITS

Status = Literal["needs_review", "confirmed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


StrictFloat = Annotated[float, Field(strict=True)]  # rejects bool/str; int is still accepted
StrictInt = Annotated[int, Field(strict=True)]


class Original(Strict):
    value: StrictFloat
    unit: str

    @field_validator("unit")
    @classmethod
    def _known_unit(cls, unit: str) -> str:
        if unit not in LENGTH_UNITS:
            raise ValueError(f"length unit must be one of {sorted(LENGTH_UNITS)}")
        return unit


class Param[T](Strict):
    value: T
    unit: str | None
    source: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    status: Status
    original: Original | None = None


class Length(Param[float]):
    value: StrictFloat

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
    value: StrictInt

    @field_validator("unit")
    @classmethod
    def _count_unit(cls, unit: str | None) -> str | None:
        if unit != "count":
            raise ValueError("unit must be 'count'")
        return unit


class Flag(Param[bool]):
    value: Annotated[bool, Field(strict=True)]

    @field_validator("unit")
    @classmethod
    def _no_unit(cls, unit: str | None) -> str | None:
        if unit is not None:
            raise ValueError("unit must be null for a flag")
        return unit


class Scalar(Param[float]):
    """Unitless number (e.g. light strength, angle in degrees named by the field)."""

    value: StrictFloat

    @field_validator("unit")
    @classmethod
    def _no_unit(cls, unit: str | None) -> str | None:
        if unit is not None:
            raise ValueError("unit must be null for a scalar")
        return unit

    @field_validator("value")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value


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
    transmission: float = Field(default=0.0, ge=0, le=1)
    metallic: float = Field(default=0.0, ge=0, le=1)  # >0: clear refractive glass (Cycles)
    texture: str | None = None  # asset id in assets/catalog.json (townhouse templates)
    texture_color: bool = True  # False: flat base_color; the texture adds roughness/relief only

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
