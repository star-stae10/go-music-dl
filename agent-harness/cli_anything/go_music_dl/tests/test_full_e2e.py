"""End-to-end tests for cli-anything-go-music-dl.

Tests the backend server, CLI subprocess, and full workflows.
Requires the music-dl Go binary to be compiled and the CLI package installed.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import tempfile

import pytest

from cli_anything.go_music_dl.core import project as _project
from cli_anything.go_music_dl.core import session as _session
from cli_anything.go_music_dl.core import export as _export


# ── Helper ─────────────────────────────────────────────────────────────

CLI_NAME = "cli-anything-go-music-dl"


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"\n[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(
            f"{name} not found in PATH. Install with: pip install -e ."
        )
    module_name = f"cli_anything.go_music_dl.go_music_dl_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module_name}")
    return [sys.executable, "-m", module_name]


CLI_BASE = _resolve_cli(CLI_NAME)


class TestCLISubprocess:
    """Test the installed CLI via subprocess."""

    def _run(self, args, check=True, timeout=30):
        return subprocess.run(
            CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "go-music-dl" in result.stdout or "Usage" in result.stdout

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert result.stdout.strip()
        # Version should contain the version number
        assert len(result.stdout.strip()) > 0

    def test_sources_json(self):
        result = self._run(["--json", "sources"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        # Should contain netease
        sources = [s["key"] for s in data]
        assert "netease" in sources

    def test_sources_human(self):
        result = self._run(["sources"])
        assert result.returncode == 0
        assert result.stdout.strip()

    def test_project_new_json(self, tmp_path):
        proj_path = tmp_path / "my-project.json"
        result = self._run([
            "--json", "project", "new", "my-music",
            "-O", str(proj_path),
            "--source", "netease",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "name" in data
        assert data["name"] == "my-music"
        # Verify file was created
        assert proj_path.exists()

    def test_project_info(self, tmp_path):
        proj_path = tmp_path / "test-proj.json"
        self._run([
            "--json", "project", "new", "test-proj",
            "-O", str(proj_path),
        ])
        result = self._run([
            "--json", "project", "info",
            "--project", str(proj_path),
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "test-proj"

    def test_parse_url(self):
        result = self._run([
            "--json", "parse",
            "https://music.163.com/song?id=123456",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("source") == "netease"

    def test_status_json(self, tmp_path):
        result = self._run(["--json", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "has_project" in data
        assert "modified" in data
        assert "server_running" in data

    def test_undo_redo_no_project(self):
        """Undo with no project should fail gracefully."""
        result = self._run(["--json", "undo"], check=False)
        # Should error since there's no project
        assert "Nothing to undo" in result.stderr or "Nothing to undo" in result.stdout or "error" in result.stdout.lower()

    def test_full_project_workflow(self, tmp_path):
        """Create project, set properties, save, info."""
        proj_path = tmp_path / "full_workflow.json"

        # New project
        r1 = self._run([
            "--json", "project", "new", "workflow-test",
            "-O", str(proj_path),
            "--source", "qq",
        ])
        assert r1.returncode == 0

        # Info
        r2 = self._run([
            "--json", "project", "info",
            "--project", str(proj_path),
        ])
        assert r2.returncode == 0
        data = json.loads(r2.stdout)
        assert data["active_source"] == "qq"

        # Status (pass --project to load into session in a new subprocess)
        r3 = self._run(["--json", "--project", str(proj_path), "status"])
        assert r3.returncode == 0
        data3 = json.loads(r3.stdout)
        assert data3["has_project"] is True
        assert data3["project_name"] == "workflow-test"

        # History (should be empty, pass --project to load session)
        r4 = self._run(["--json", "--project", str(proj_path), "history"])
        assert r4.returncode == 0
        data4 = json.loads(r4.stdout)
        assert isinstance(data4, list)


# ── Backend Tests (require music-dl binary) ────────────────────────────

@pytest.mark.skipif(
    shutil.which("music-dl") is None,
    reason="music-dl binary not found in PATH"
)
class TestBackendIntegration:
    """Integration tests that require the music-dl binary."""

    @classmethod
    def setup_class(cls):
        from cli_anything.go_music_dl.utils.backend import (
            BinaryNotFoundError, BackendConfig, start_server, stop_server
        )
        cls.config = BackendConfig(port=8199, startup_timeout=20)
        try:
            cls.server_info = start_server(cls.config)
            cls._running = True
        except BinaryNotFoundError as e:
            cls._running = False
            cls._error = str(e)
        time.sleep(1)

    @classmethod
    def teardown_class(cls):
        if getattr(cls, '_running', False):
            stop_server()

    def test_health_check(self):
        if not self._running:
            pytest.skip(f"Server not running: {getattr(self, '_error', 'unknown')}")
        from cli_anything.go_music_dl.utils.backend import health_check
        result = health_check()
        assert result["status"] == "healthy"

    def test_sources_list(self):
        if not self._running:
            pytest.skip(f"Server not running: {getattr(self, '_error', 'unknown')}")
        from cli_anything.go_music_dl.utils.backend import get_source_list
        sources = get_source_list()
        assert len(sources) > 0
        source_keys = [s["key"] for s in sources]
        assert "netease" in source_keys

    def test_get_cookies(self):
        if not self._running:
            pytest.skip(f"Server not running: {getattr(self, '_error', 'unknown')}")
        from cli_anything.go_music_dl.utils.backend import get_cookies
        cookies = get_cookies()
        assert isinstance(cookies, dict)

    def test_get_settings(self):
        if not self._running:
            pytest.skip(f"Server not running: {getattr(self, '_error', 'unknown')}")
        from cli_anything.go_music_dl.utils.backend import get_settings
        settings = get_settings()
        assert isinstance(settings, dict)
        assert "embedDownload" in settings


# ── Output Verification Tests ──────────────────────────────────────────

class TestOutputVerification:
    """Test output verification independent of backend."""

    def test_module_imports(self):
        """All core modules import correctly."""
        from cli_anything.go_music_dl import __version__
        assert __version__ == "1.0.0"

    def test_session_save_load(self):
        """Session save/load round-trip with real files."""
        sess = _session.Session()
        proj = _project.create_project(name="e2e-test")
        sess.set_project(proj, "/tmp/e2e-test.json")
        sess.add_download({"song_id": "e2e123", "name": "E2E Song", "path": "/tmp/e2e.mp3"})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            sess_path = f.name

        try:
            sess.save_session(sess_path)

            # Load it back
            loaded = _session.Session.load_session(sess_path)
            assert loaded.project.name == "e2e-test"
            assert len(loaded.get_downloads()) == 1
            assert loaded.get_downloads()[0]["song_id"] == "e2e123"
        finally:
            if os.path.exists(sess_path):
                os.unlink(sess_path)

    def test_verify_real_audio_file(self):
        """Verify a real audio file if available, else create a minimal test."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\xff\xfb\x90\x00test audio frame data")
            path = f.name

        try:
            result = _export.verify_download_output(path)
            assert result["exists"] is True
            assert result["size"] > 0
            assert result["is_audio"] is True
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_backend_source_list_matches_core(self):
        """Backend source list should match core module's list."""
        from cli_anything.go_music_dl.utils.backend import (
            ALL_SOURCES, DEFAULT_SOURCES, SOURCE_DESCRIPTIONS
        )
        assert "netease" in ALL_SOURCES
        assert "qq" in ALL_SOURCES
        assert "netease" in DEFAULT_SOURCES
        assert "bilibili" not in DEFAULT_SOURCES  # excluded from defaults
        assert SOURCE_DESCRIPTIONS["netease"] == "网易云音乐"
