"""Immutable revision directories: one per (normalized project, render configuration)."""

import hashlib
from pathlib import Path

from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.runtime.files import canonical_json


def content_hash(project: Project, render: RenderSettings) -> str:
    payload = {"project": project.model_dump(mode="json"), "render": render.to_dict()}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def revision_dir(out: Path, project: Project, render: RenderSettings) -> Path:
    short = content_hash(project, render)[:8]
    return Path(out) / project.project_id / f"r{project.project_revision:03d}-{short}"
