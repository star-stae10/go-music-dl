"""Project management — create, open, save, and query music-dl projects."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Project:
    """Represents a music-dl project/workspace."""
    name: str
    active_source: str = "netease"
    download_dir: str = "./downloads"
    with_cover: bool = True
    with_lyrics: bool = True
    filename_template: str = "{name} - {artist}"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(
            name=data.get("name", "untitled"),
            active_source=data.get("active_source", "netease"),
            download_dir=data.get("download_dir", "./downloads"),
            with_cover=data.get("with_cover", True),
            with_lyrics=data.get("with_lyrics", True),
            filename_template=data.get("filename_template", "{name} - {artist}"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


def create_project(name: str, download_dir: str = "./downloads",
                   active_source: str = "netease",
                   with_cover: bool = True, with_lyrics: bool = True) -> Project:
    """Create a new project with the given settings."""
    return Project(
        name=name,
        download_dir=download_dir,
        active_source=active_source,
        with_cover=with_cover,
        with_lyrics=with_lyrics,
    )


def save_project(project: Project, path: str) -> str:
    """Save a project to a JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    project.updated_at = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def open_project(path: str) -> Project:
    """Open a project from a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Project.from_dict(data)


def project_info(project: Project) -> dict:
    """Return project info as a dictionary."""
    return {
        "name": project.name,
        "active_source": project.active_source,
        "download_dir": project.download_dir,
        "with_cover": project.with_cover,
        "with_lyrics": project.with_lyrics,
        "filename_template": project.filename_template,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def validate_project_path(path: str) -> Optional[str]:
    """Validate a project file path. Returns error message or None."""
    if not path:
        return "Path is empty"
    if os.path.isdir(path):
        return "Path is a directory, not a file"
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            return f"Cannot create directory: {e}"
    return None
