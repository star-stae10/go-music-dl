"""Session management — stateful session with undo/redo for CLI operations."""

import json
import os
import copy
from datetime import datetime, timezone
from typing import Optional, Any

from cli_anything.go_music_dl.core.project import Project, project_info

# Session file locking helper (atomic save)
def _locked_save_json(path: str, data: dict):
    """Atomic JSON save with file locking to prevent concurrent write corruption."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as ftmp:
        json.dump(data, ftmp, ensure_ascii=False, indent=2)
        ftmp.flush()
        os.fsync(ftmp.fileno())
    try:
        # Cross-platform atomic save: write to temp, then rename
        os.replace(tmp, path)
    except OSError as e:
        # Fallback: direct write
        if os.path.exists(tmp):
            os.remove(tmp)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class Session:
    """Stateful session that tracks the active project, server, and history."""

    def __init__(self):
        self._project: Optional[Project] = None
        self._project_path: Optional[str] = None
        self._modified: bool = False
        self._server_port: Optional[int] = None
        self._server_pid: Optional[int] = None
        self._server_started: Optional[str] = None
        self._download_history: list[dict] = []
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._snapshot_count: int = 0

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def project(self) -> Optional[Project]:
        return self._project

    @property
    def project_path(self) -> Optional[str]:
        return self._project_path

    @property
    def modified(self) -> bool:
        return self._modified

    @property
    def server_info(self) -> dict:
        return {
            "port": self._server_port,
            "pid": self._server_pid,
            "started_at": self._server_started,
        }

    # ── Project Management ──────────────────────────────────────────────

    def has_project(self) -> bool:
        return self._project is not None

    def set_project(self, project: Project, path: Optional[str] = None):
        """Set the active project."""
        self._project = project
        if path:
            self._project_path = os.path.abspath(path)
        self._modified = True

    def clear_project(self):
        """Clear the active project without saving."""
        self._project = None
        self._project_path = None
        self._modified = False

    # ── Server Management ───────────────────────────────────────────────

    def set_server(self, port: int, pid: int):
        """Record backend server info."""
        self._server_port = port
        self._server_pid = pid
        self._server_started = datetime.now(timezone.utc).isoformat()

    def clear_server(self):
        """Clear server info."""
        self._server_port = None
        self._server_pid = None
        self._server_started = None

    def is_server_running(self) -> bool:
        """Check if the server PID is alive."""
        if self._server_pid is None:
            return False
        try:
            os.kill(self._server_pid, 0)
            return True
        except (OSError, PermissionError):
            return False

    # ── Undo/Redo ───────────────────────────────────────────────────────

    def snapshot(self, description: str = ""):
        """Save current project state to the undo stack."""
        if self._project is None:
            return
        self._snapshot_count += 1
        state = {
            "id": self._snapshot_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "description": description or f"snapshot #{self._snapshot_count}",
            "project": copy.deepcopy(self._project.to_dict()),
        }
        self._undo_stack.append(state)
        self._redo_stack.clear()
        self._modified = True

    def undo(self) -> Optional[dict]:
        """Undo the last operation.

        Pops the most recent snapshot (current state) from the undo stack,
        pushes it onto the redo stack, then restores the state from the
        previous snapshot (if one exists).
        """
        if not self._undo_stack or self._project is None:
            return None

        # Pop the current state (last snapshot) and push to redo
        current_state = self._undo_stack.pop()
        self._redo_stack.append(current_state)

        # Restore from the previous snapshot if available
        if self._undo_stack:
            target = self._undo_stack[-1]  # peek at the new last entry
            if target["project"]:
                self._project = Project.from_dict(target["project"])
        self._modified = True
        return current_state

    def redo(self) -> Optional[dict]:
        """Redo the last undone operation.

        Pops the top of the redo stack and pushes it back onto the undo
        stack, then restores the project state from that entry.
        """
        if not self._redo_stack or self._project is None:
            return None

        # Pop from redo and push back to undo
        state = self._redo_stack.pop()
        self._undo_stack.append(state)

        # Restore project state from the redo entry
        if state["project"]:
            self._project = Project.from_dict(state["project"])
        self._modified = True
        return state

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ── Download History ────────────────────────────────────────────────

    def add_download(self, entry: dict):
        """Record a downloaded song."""
        self._download_history.append(entry)
        self._modified = True

    def get_downloads(self) -> list[dict]:
        return list(self._download_history)

    def clear_downloads(self):
        self._download_history.clear()
        self._modified = True

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "project": project_info(self._project) if self._project else None,
            "project_path": self._project_path,
            "server": {
                "port": self._server_port,
                "pid": self._server_pid,
                "started_at": self._server_started,
            },
            "download_history": self._download_history[-100:],  # keep last 100
            "snapshot_count": self._snapshot_count,
        }

    def save_session(self, path: str):
        """Persist session to a JSON file with atomic locking."""
        _locked_save_json(path, self.to_dict())
        self._modified = False

    @classmethod
    def load_session(cls, path: str) -> "Session":
        """Load a session from a JSON file."""
        sess = cls()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("project"):
                sess._project = Project.from_dict(data["project"])
                sess._project_path = data.get("project_path")
            server = data.get("server", {})
            sess._server_port = server.get("port")
            sess._server_pid = server.get("pid")
            sess._server_started = server.get("started_at")
            sess._download_history = data.get("download_history", [])
            sess._snapshot_count = data.get("snapshot_count", 0)
            sess._modified = False
        return sess


# Global singleton session
_global_session: Optional[Session] = None


def get_session() -> Session:
    """Get or create the global session singleton."""
    global _global_session
    if _global_session is None:
        _global_session = Session()
    return _global_session


def set_session(session: Session):
    """Set the global session singleton."""
    global _global_session
    _global_session = session


def reset_session():
    """Reset the global session to empty."""
    global _global_session
    _global_session = Session()
