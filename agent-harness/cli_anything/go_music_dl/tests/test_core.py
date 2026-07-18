"""Unit tests for cli-anything-go-music-dl core modules.

Tests project, session, and export modules with synthetic data.
No external dependencies (no backend server required).
"""

import json
import os
import tempfile

import pytest

from cli_anything.go_music_dl.core import project as _project
from cli_anything.go_music_dl.core import session as _session
from cli_anything.go_music_dl.core import export as _export


# ── project.py tests ──────────────────────────────────────────────────

class TestProject:
    def test_create_project(self):
        proj = _project.create_project(name="test")
        assert proj.name == "test"
        assert proj.active_source == "netease"
        assert proj.download_dir == "./downloads"
        assert proj.with_cover is True
        assert proj.with_lyrics is True
        assert proj.created_at is not None

    def test_create_project_custom(self):
        proj = _project.create_project(
            name="custom",
            download_dir="/tmp/music",
            active_source="qq",
            with_cover=False,
            with_lyrics=True,
        )
        assert proj.name == "custom"
        assert proj.download_dir == "/tmp/music"
        assert proj.active_source == "qq"
        assert proj.with_cover is False
        assert proj.with_lyrics is True

    def test_save_and_open_project(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        try:
            proj = _project.create_project(name="roundtrip", active_source="kugou")
            _project.save_project(proj, path)

            loaded = _project.open_project(path)
            assert loaded.name == "roundtrip"
            assert loaded.active_source == "kugou"
            assert loaded.download_dir == "./downloads"
            assert loaded.created_at == proj.created_at
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            _project.open_project("/nonexistent/path/project.json")

    def test_project_info(self):
        proj = _project.create_project(name="info-test", active_source="migu")
        info = _project.project_info(proj)
        assert isinstance(info, dict)
        assert info["name"] == "info-test"
        assert info["active_source"] == "migu"
        assert "created_at" in info
        assert "updated_at" in info

    def test_project_to_dict(self):
        proj = _project.create_project(name="dict-test")
        d = proj.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "dict-test"

    def test_project_from_dict(self):
        data = {
            "name": "from-dict",
            "active_source": "kuwo",
            "download_dir": "./output",
            "with_cover": False,
            "with_lyrics": False,
            "filename_template": "{name}",
        }
        proj = _project.Project.from_dict(data)
        assert proj.name == "from-dict"
        assert proj.active_source == "kuwo"
        assert proj.download_dir == "./output"

    def test_validate_project_path(self):
        # Empty path
        err = _project.validate_project_path("")
        assert err is not None
        # Valid path (non-existent parent is OK, we create it)
        err = _project.validate_project_path("valid/path/project.json")
        assert err is None


# ── session.py tests ──────────────────────────────────────────────────

class TestSession:
    def test_session_init(self):
        sess = _session.Session()
        assert sess.has_project() is False
        assert sess.project is None
        assert sess.modified is False
        assert sess.can_undo() is False
        assert sess.can_redo() is False
        assert sess.get_downloads() == []

    def test_set_project(self):
        sess = _session.Session()
        proj = _project.create_project(name="sess-test")
        sess.set_project(proj, "/tmp/test.json")
        assert sess.has_project() is True
        assert sess.project.name == "sess-test"
        assert sess.project_path == os.path.abspath("/tmp/test.json")
        assert sess.modified is True

    def test_snapshot_undo_redo(self):
        sess = _session.Session()
        proj = _project.create_project(name="undo-test", active_source="netease")
        sess.set_project(proj)

        sess.snapshot("initial")
        sess.project.active_source = "qq"
        sess.snapshot("changed to qq")

        # Undo
        state = sess.undo()
        assert state is not None
        assert sess.project.active_source == "netease"

        # Redo
        state = sess.redo()
        assert state is not None
        assert sess.project.active_source == "qq"

    def test_undo_empty(self):
        sess = _session.Session()
        assert sess.undo() is None
        assert sess.can_undo() is False

    def test_redo_empty(self):
        sess = _session.Session()
        assert sess.redo() is None
        assert sess.can_redo() is False

    def test_download_history(self):
        sess = _session.Session()
        entry = {"song_id": "123", "name": "Test", "path": "/tmp/test.mp3"}
        sess.add_download(entry)
        assert len(sess.get_downloads()) == 1
        assert sess.get_downloads()[0]["song_id"] == "123"

        sess.clear_downloads()
        assert len(sess.get_downloads()) == 0

    def test_session_serialization(self):
        sess = _session.Session()
        proj = _project.create_project(name="serial-test")
        sess.set_project(proj, "/tmp/test.json")
        sess.set_server(8080, 12345)
        sess.add_download({"song_id": "1", "name": "Song", "path": "/tmp/song.mp3"})
        sess.snapshot("test snapshot")

        # Save to dict and back
        data = sess.to_dict()

        sess2 = _session.Session()
        # Simulate loading
        if data.get("project"):
            sess2.set_project(
                _project.Project.from_dict(data["project"]),
                data.get("project_path")
            )
        srv = data.get("server", {})
        if srv.get("port"):
            sess2.set_server(srv["port"], srv["pid"])
        for dl in data.get("download_history", []):
            sess2.add_download(dl)

        assert sess2.project.name == "serial-test"
        assert sess2.get_downloads()[0]["song_id"] == "1"
        assert sess2.server_info["port"] == 8080

    def test_clear_project(self):
        sess = _session.Session()
        proj = _project.create_project(name="clear-test")
        sess.set_project(proj, "/tmp/test.json")
        assert sess.has_project() is True

        sess.clear_project()
        assert sess.has_project() is False
        assert sess.project is None

    def test_global_session(self):
        _session.reset_session()
        sess1 = _session.get_session()
        sess2 = _session.get_session()
        assert sess1 is sess2

        _session.reset_session()
        sess3 = _session.get_session()
        assert sess3 is not sess1

    def test_clear_server(self):
        sess = _session.Session()
        sess.set_server(8080, 99999)
        assert sess.server_info["port"] == 8080

        sess.clear_server()
        assert sess.server_info["port"] is None


# ── export.py tests ────────────────────────────────────────────────────

class TestExport:
    def test_download_job_defaults(self):
        job = _export.DownloadJob(song_id="123", source="netease", name="Test")
        assert job.status == "pending"
        assert job.with_cover is True
        assert job.with_lyrics is True
        assert job.created_at is not None

    def test_download_job_to_dict(self):
        job = _export.DownloadJob(
            song_id="456", source="qq", name="Song",
            artist="Artist", status="completed",
            output_path="/tmp/test.mp3", file_size=1024,
        )
        d = job.to_dict()
        assert d["song_id"] == "456"
        assert d["status"] == "completed"
        assert d["file_size"] == 1024

    def test_verify_download_output_missing(self):
        result = _export.verify_download_output("/nonexistent/file.mp3")
        assert result["exists"] is False
        assert result["size"] == 0

    def test_verify_output_format(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3 some fake mp3 data")
            path = f.name

        try:
            result = _export.verify_download_output(path)
            assert result["exists"] is True
            assert result["size"] > 0
            assert result["extension"] == ".mp3"
            assert result["is_audio"] is True
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_verify_flac_format(self):
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            path = f.name

        try:
            result = _export.verify_download_output(path)
            assert result["is_audio"] is True
            assert result["extension"] == ".flac"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_verify_non_audio(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an audio file")
            path = f.name

        try:
            result = _export.verify_download_output(path)
            assert result["exists"] is True
            assert result["is_audio"] is False
            assert result["extension"] == ".txt"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_download_result_to_dict(self):
        result = _export.DownloadResult(
            success=True, path="/tmp/test.mp3",
            filename="test.mp3", file_size=2048,
            format="mp3", source="netease", song_id="789",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["file_size"] == 2048
        assert d["source"] == "netease"
