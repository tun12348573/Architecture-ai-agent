"""Render profiles. GPU is opt-in (Cycles only) until validated on the real machine."""

from dataclasses import asdict, dataclass, replace
from typing import Literal


@dataclass(frozen=True)
class RenderSettings:
    profile: str
    width: int
    height: int
    engine: Literal["BLENDER_EEVEE", "CYCLES"]
    device: Literal["CPU", "GPU"] | None  # None = engine default (Eevee uses the GPU)
    samples: int

    def to_dict(self) -> dict:
        return asdict(self)


PROFILES: dict[str, RenderSettings] = {
    "preview": RenderSettings("preview", 1280, 720, "BLENDER_EEVEE", None, 16),
    "final": RenderSettings("final", 1920, 1080, "BLENDER_EEVEE", None, 64),
    "smoke": RenderSettings("smoke", 128, 72, "CYCLES", "CPU", 4),
}
ENGINES = {"eevee": "BLENDER_EEVEE", "cycles": "CYCLES"}
DEVICES = {"cpu": "CPU", "gpu": "GPU"}


def resolve_render(
    profile: str, engine: str | None = None, device: str | None = None
) -> RenderSettings:
    if profile not in PROFILES:
        raise ValueError(f"unknown render profile {profile!r}; expected one of {sorted(PROFILES)}")
    settings = PROFILES[profile]
    if engine is not None:
        if engine.lower() not in ENGINES:
            raise ValueError(f"unknown engine {engine!r}; expected eevee or cycles")
        settings = replace(settings, engine=ENGINES[engine.lower()])
        if settings.engine == "BLENDER_EEVEE":
            settings = replace(settings, device=None)
        elif settings.device is None:
            settings = replace(settings, device="CPU")
    if device is not None:
        if settings.engine != "CYCLES":
            raise ValueError("--device is only valid with the cycles engine")
        if device.lower() not in DEVICES:
            raise ValueError(f"unknown device {device!r}; expected cpu or gpu")
        settings = replace(settings, device=DEVICES[device.lower()])
    return settings
