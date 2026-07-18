"""Export module — download songs, manage output, and verify results.

This module wraps the go-music-dl backend (web server or direct binary)
for downloading songs, managing download jobs, and verifying output.
"""

import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class DownloadJob:
    """Represents a single download job."""
    song_id: str
    source: str
    name: str
    artist: str = ""
    album: str = ""
    cover: str = ""
    with_cover: bool = True
    with_lyrics: bool = True
    status: str = "pending"  # pending, downloading, completed, failed
    output_path: Optional[str] = None
    file_size: int = 0
    warning: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadJob":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    path: Optional[str] = None
    filename: Optional[str] = None
    file_size: int = 0
    format: str = ""
    warning: str = ""
    error: str = ""
    source: str = ""
    song_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def verify_download_output(path: str) -> dict:
    """Verify a downloaded audio file exists and has valid content.

    Returns a dict with verification results:
    - exists: bool
    - size: int (bytes)
    - extension: str
    - is_audio: bool (basic check via extension)
    """
    result = {
        "exists": False,
        "size": 0,
        "extension": "",
        "is_audio": False,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }

    if not path or not os.path.exists(path):
        return result

    stat = os.stat(path)
    result["exists"] = True
    result["size"] = stat.st_size
    result["extension"] = os.path.splitext(path)[1].lower()

    audio_extensions = {".mp3", ".flac", ".m4a", ".wma", ".ogg", ".wav", ".aac", ".ape"}
    result["is_audio"] = result["extension"] in audio_extensions

    # Check magic bytes for common formats
    try:
        with open(path, "rb") as f:
            header = f.read(8)
        if header[:3] == b"ID3":
            result["format"] = "mp3 (ID3)"
        elif header[:4] == b"\x1aE\xdf\xa3":
            result["format"] = "m4a (MPEG-4)"
        elif header[:4] == b"fLaC":
            result["format"] = "flac"
        elif header[:4] == b"RIFF" and header[8:12] == b"WAVE":
            result["format"] = "wav"
        elif header[:4] == b"OggS":
            result["format"] = "ogg"
        else:
            result["format"] = "unknown"
    except (IOError, OSError):
        result["format"] = "unreadable"

    return result


# Default download output directory
DEFAULT_DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
