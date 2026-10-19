"""Length units accepted in project files. Internal unit is the metre."""

LENGTH_UNITS: dict[str, float] = {"m": 1.0, "cm": 0.01, "mm": 0.001, "ft": 0.3048, "in": 0.0254}


def to_metres(value: float, unit: str) -> float:
    try:
        return value * LENGTH_UNITS[unit]
    except KeyError:
        known = sorted(LENGTH_UNITS)
        raise ValueError(f"unknown length unit {unit!r}; expected one of {known}") from None
