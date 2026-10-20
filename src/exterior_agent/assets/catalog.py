"""Committed catalog of CC0 assets (textures, HDRIs, models) pinned by sha256."""

import os
import re
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator

from exterior_agent.domain.params import Strict

ALLOWED_HOSTS = frozenset({"dl.polyhaven.org"})
CATALOG_ENV = "EXTERIOR_AGENT_CATALOG"
DEFAULT_CATALOG = Path(__file__).resolve().parents[3] / "assets" / "catalog.json"


class AssetFile(Strict):
    path: str
    url: str
    size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: str

    @field_validator("path")
    @classmethod
    def _safe_relative(cls, path: str) -> str:
        parts = PurePosixPath(path).parts
        if (
            not parts
            or "\\" in path
            or path.startswith("/")
            or re.match(r"^[A-Za-z]:", path)
            or any(p in ("..", ".") for p in parts)
        ):
            raise ValueError("asset file path must be a plain relative path")
        return path

    @field_validator("url")
    @classmethod
    def _allowed_url(cls, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError(f"asset URL must be https on {sorted(ALLOWED_HOSTS)}")
        return url


class Asset(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    kind: Literal["texture", "hdri", "model"]
    license: Literal["CC0"]
    authors: list[str]
    source_page: str
    resolution: str
    scale_m: float | None = None
    files: list[AssetFile] = Field(min_length=1)


class Catalog(Strict):
    schema_: Literal["asset_catalog/1"] = Field(alias="schema")
    assets: list[Asset]

    def get(self, asset_id: str) -> Asset:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        raise KeyError(asset_id)


def load_catalog(path: Path | None = None) -> Catalog:
    path = Path(path or os.environ.get(CATALOG_ENV) or DEFAULT_CATALOG)
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))
