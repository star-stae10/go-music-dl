"""Backend module — wraps the go-music-dl web server as an HTTP API backend.

Architecture:
  The Python CLI starts the Go binary's web server (`music-dl web`) as a
  managed subprocess, then communicates with it via HTTP.

  For operations that return JSON (cookies, settings, inspect, download with
  embed&saveLocal), we use the JSON endpoints directly.

  For operations that return HTML (search, playlist, album), we parse the
  HTML response using BeautifulSoup to extract structured data.

  This follows HARNESS.md's rule: "Use the Real Software — Don't Reimplement It."
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode, urljoin

import requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ── Backend Configuration ──────────────────────────────────────────────

@dataclass
class BackendConfig:
    """Configuration for the music-dl backend web server."""
    binary_name: str = "music-dl"
    host: str = "127.0.0.1"
    port: int = 8099
    base_path: str = "/music"
    startup_timeout: float = 15.0
    health_check_interval: float = 0.5

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.base_path}"


# ── Source Names ───────────────────────────────────────────────────────

ALL_SOURCES = [
    "netease", "qq", "kugou", "kuwo", "migu", "fivesing",
    "jamendo", "joox", "qianqian", "soda", "bilibili", "apple", "local",
]

DEFAULT_SOURCES = [
    "netease", "qq", "kugou", "kuwo", "migu", "qianqian", "soda", "apple",
]

PLAYLIST_SOURCES = [
    "netease", "qq", "kugou", "kuwo", "migu", "jamendo", "joox",
    "qianqian", "bilibili", "soda", "fivesing", "apple",
]

ALBUM_SOURCES = [
    "netease", "qq", "kugou", "kuwo", "migu", "jamendo",
    "joox", "qianqian", "soda", "apple",
]

SOURCE_DESCRIPTIONS = {
    "netease": "网易云音乐",
    "qq": "QQ音乐",
    "kugou": "酷狗音乐",
    "kuwo": "酷我音乐",
    "migu": "咪咕音乐",
    "fivesing": "5sing",
    "jamendo": "Jamendo (CC)",
    "joox": "JOOX",
    "qianqian": "千千音乐",
    "soda": "汽水音乐",
    "bilibili": "Bilibili",
    "apple": "Apple Music",
    "local": "本地音乐",
}


# ── Exceptions ─────────────────────────────────────────────────────────

class BackendError(Exception):
    """Base error for backend operations."""
    pass

class BackendNotRunningError(BackendError):
    """The backend server is not started or not reachable."""
    pass

class BackendStartupError(BackendError):
    """Failed to start the backend server."""
    pass

class BinaryNotFoundError(BackendError):
    """The music-dl binary was not found."""
    pass


# ── Server Lifecycle ───────────────────────────────────────────────────

_proc: Optional[subprocess.Popen] = None
_config: BackendConfig = BackendConfig()


def find_binary(name: str = "music-dl") -> str:
    """Find the go-music-dl binary in PATH or common locations."""
    # Check PATH first
    which = shutil_which(name)
    if which:
        return which

    # Check common locations relative to the package
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(package_dir, "..", "..", "..", "cmd", "music-dl", name),
        os.path.join(package_dir, "..", "..", "..", "bin", name + ".exe"),
        os.path.join(package_dir, "..", "..", "..", "bin", name),
        os.path.join(os.path.dirname(package_dir), "bin", name + ".exe"),
        os.path.join(os.path.dirname(package_dir), "bin", name),
    ]
    for path in candidates:
        normalized = os.path.abspath(path)
        if os.path.isfile(normalized) and os.access(normalized, os.X_OK):
            return normalized

    raise BinaryNotFoundError(
        f"music-dl binary not found. "
        f"Please build it: cd go-music-dl && go build -o music-dl ./cmd/music-dl"
    )


def start_server(config: Optional[BackendConfig] = None) -> dict:
    """Start the music-dl web server as a background process.

    Returns server info dict with port, pid.
    Raises BackendStartupError if the server fails to start.
    """
    global _proc, _config

    if config:
        _config = config

    binary = find_binary(_config.binary_name)

    env = os.environ.copy()
    env["MUSIC_DL_CONFIG_DB"] = os.path.join(
        os.getcwd(), "data", "settings.db"
    )

    try:
        _proc = subprocess.Popen(
            [binary, "web", "--port", str(_config.port), "--no-browser"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError:
        raise BinaryNotFoundError(
            f"music-dl binary not found at {binary}"
        )

    # Wait for the server to become healthy
    start_time = time.time()
    last_error = ""
    while time.time() - start_time < _config.startup_timeout:
        try:
            resp = requests.get(
                urljoin(_config.base_url, "/healthz"),
                timeout=2,
            )
            if resp.status_code == 200:
                info = {
                    "port": _config.port,
                    "pid": _proc.pid,
                    "base_url": _config.base_url,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "running",
                }
                return info
        except requests.RequestException as e:
            last_error = str(e)
            time.sleep(_config.health_check_interval)

    # Timeout — collect stderr for diagnostics
    stderr_output = ""
    if _proc and _proc.stderr:
        try:
            stderr_output = _proc.stderr.read(4096).decode("utf-8", errors="replace")
        except Exception:
            pass

    raise BackendStartupError(
        f"Server failed to start on port {_config.port} after "
        f"{_config.startup_timeout}s. Last error: {last_error}. "
        f"Stderr: {stderr_output[:500]}"
    )


def stop_server():
    """Stop the backend server if running."""
    global _proc
    if _proc is None:
        return
    try:
        if sys.platform == "win32":
            _proc.terminate()
        else:
            os.kill(_proc.pid, signal.SIGTERM)
        _proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
        try:
            _proc.kill()
            _proc.wait(timeout=2)
        except Exception:
            pass
    _proc = None


def server_running() -> bool:
    """Check if the backend server process is alive."""
    global _proc
    if _proc is None:
        return False
    try:
        resp = requests.get(urljoin(_config.base_url, "/healthz"), timeout=2)
        return resp.status_code == 200
    except requests.RequestException:
        return False if _proc.poll() is not None else True


def ensure_server():
    """Ensure the backend server is running. Starts it if needed."""
    if not server_running():
        start_server()


# ── HTTP Client Helpers ────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({"User-Agent": "cli-anything-go-music-dl/1.0"})


def _get(path: str, params: dict = None, timeout: float = 30) -> requests.Response:
    """Make a GET request to the backend server."""
    if not server_running():
        raise BackendNotRunningError("Backend server is not running. Use 'server start' first.")
    url = urljoin(_config.base_url, path)
    return _session.get(url, params=params, timeout=timeout)


def _post(path: str, json_data: dict = None, timeout: float = 30) -> requests.Response:
    """Make a POST request to the backend server."""
    if not server_running():
        raise BackendNotRunningError("Backend server is not running. Use 'server start' first.")
    url = urljoin(_config.base_url, path)
    return _session.post(url, json=json_data, timeout=timeout)


# ── Search Operations ──────────────────────────────────────────────────

def _parse_song_row(row) -> Optional[dict]:
    """Parse a song HTML row from the web interface."""
    try:
        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        # Extract data from cells
        song_link = cells[0].find("a") if cells[0] else None
        song_name = song_link.get_text(strip=True) if song_link else cells[0].get_text(strip=True)

        artist_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        album_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

        source_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        # Try to extract song ID from data attributes or links
        song_id = ""
        if song_link and song_link.get("href"):
            href = song_link["href"]
            id_match = re.search(r'[?&]id=(\d+)', href)
            if id_match:
                song_id = id_match.group(1)

        # Try download link for ID
        download_btn = row.find("a", class_="download-btn") or row.find("button", class_="download")
        if not song_id and download_btn:
            onclick = download_btn.get("onclick", "") or download_btn.get("data-id", "")
            if onclick:
                id_match = re.search(r'(\d+)', str(onclick))
                if id_match:
                    song_id = id_match.group(1)

        duration_text = ""
        dur_cell = cells[4] if len(cells) > 4 else None
        if dur_cell:
            duration_text = dur_cell.get_text(strip=True)

        return {
            "id": song_id,
            "name": song_name,
            "artist": artist_text,
            "album": album_text,
            "source": source_text.lower() if source_text else "",
            "duration": duration_text,
        }
    except Exception:
        return None


def _parse_playlist_row(row) -> Optional[dict]:
    """Parse a playlist/album HTML row from the web interface."""
    try:
        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        name_link = cells[0].find("a") if cells[0] else None
        name = name_link.get_text(strip=True) if name_link else cells[0].get_text(strip=True)

        # Extract ID from link
        playlist_id = ""
        if name_link and name_link.get("href"):
            href = name_link["href"]
            id_match = re.search(r'[?&]id=([^&]+)', href)
            if id_match:
                playlist_id = urllib.parse.unquote(id_match.group(1))

        creator_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        count_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        source_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        return {
            "id": playlist_id,
            "name": name,
            "creator": creator_text,
            "track_count": count_text,
            "source": source_text.lower() if source_text else "",
        }
    except Exception:
        return None


def search_songs(keyword: str, sources: list[str] = None, timeout: float = 30) -> list[dict]:
    """Search for songs across specified sources.

    Parses the HTML response from the web interface to extract song data.
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    params = {
        "q": keyword,
        "type": "song",
    }
    for src in sources:
        params.setdefault("sources", []).append(src)

    resp = _get("/search", params=params, timeout=timeout)
    resp.raise_for_status()

    songs = []
    if not HAS_BS4:
        return _fallback_parse_search(resp.text, keyword)

    soup = BeautifulSoup(resp.text, "html.parser")
    # Look for song rows in the results table
    table = soup.find("table", class_="song-table") or soup.find("table")
    if table:
        rows = table.find_all("tr")[1:]  # skip header
        for row in rows:
            song = _parse_song_row(row)
            if song and song["name"]:
                songs.append(song)

    return songs if songs else _fallback_parse_search(resp.text, keyword)


def _fallback_parse_search(html: str, keyword: str) -> list[dict]:
    """Fallback: extract song data from raw HTML using regex patterns."""
    songs = []
    # Try to find JSON-like data embedded in the page
    # Pattern: song data in HTML comments or script tags
    script_pattern = r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?});</script>'
    match = re.search(script_pattern, html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return _extract_songs_from_state(data)
        except (json.JSONDecodeError, KeyError):
            pass
    return songs


def _extract_songs_from_state(data: dict) -> list[dict]:
    """Extract song data from parsed JSON state."""
    songs = []
    # Various known state structures
    for key in ("songs", "result", "songList", "songlist"):
        items = data.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("name"):
                    songs.append({
                        "id": str(item.get("id", "")),
                        "name": item.get("name", ""),
                        "artist": item.get("artist", "") or item.get("singer", ""),
                        "album": item.get("album", "") or item.get("album_name", ""),
                        "source": item.get("source", ""),
                        "duration": str(item.get("duration", "")),
                    })
    return songs


def search_playlists(keyword: str, sources: list[str] = None, timeout: float = 30) -> list[dict]:
    """Search for playlists across specified sources."""
    if sources is None:
        sources = PLAYLIST_SOURCES

    params = {
        "q": keyword,
        "type": "playlist",
    }
    for src in sources:
        params.setdefault("sources", []).append(src)

    resp = _get("/search", params=params, timeout=timeout)
    resp.raise_for_status()

    playlists = []
    if HAS_BS4:
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table") or soup.find("div", class_="playlist-grid")
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows:
                pl = _parse_playlist_row(row)
                if pl and pl["name"]:
                    playlists.append(pl)
    return playlists


def search_albums(keyword: str, sources: list[str] = None, timeout: float = 30) -> list[dict]:
    """Search for albums across specified sources."""
    if sources is None:
        sources = ALBUM_SOURCES

    params = {
        "q": keyword,
        "type": "album",
    }
    for src in sources:
        params.setdefault("sources", []).append(src)

    resp = _get("/search", params=params, timeout=timeout)
    resp.raise_for_status()

    albums = []
    if HAS_BS4:
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows:
                pl = _parse_playlist_row(row)
                if pl and pl["name"]:
                    albums.append(pl)
    return albums


# ── Playlist / Album Detail ────────────────────────────────────────────

def get_playlist_songs(source: str, playlist_id: str, timeout: float = 30) -> list[dict]:
    """Get songs from a specific playlist."""
    params = {"id": playlist_id, "source": source}
    resp = _get("/playlist", params=params, timeout=timeout)
    resp.raise_for_status()
    return _parse_songs_from_html(resp.text)


def get_album_songs(source: str, album_id: str, timeout: float = 30) -> list[dict]:
    """Get songs from a specific album."""
    params = {"id": album_id, "source": source}
    resp = _get("/album", params=params, timeout=timeout)
    resp.raise_for_status()
    return _parse_songs_from_html(resp.text)


def _parse_songs_from_html(html: str) -> list[dict]:
    """Parse song list from HTML response."""
    songs = []
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows:
                song = _parse_song_row(row)
                if song and song["name"]:
                    songs.append(song)
    return songs


# ── Inspect (Get Download URL) ─────────────────────────────────────────

def inspect_song(source: str, song_id: str, duration: int = 0,
                 extra: dict = None, timeout: float = 15) -> dict:
    """Inspect a song to get download URL, size, and bitrate.

    Returns JSON from the /music/inspect endpoint.
    """
    params = {"id": song_id, "source": source, "duration": str(duration)}
    if extra:
        params["extra"] = json.dumps(extra, ensure_ascii=False)

    resp = _get("/inspect", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── Download Operations ────────────────────────────────────────────────

def download_song(source: str, song_id: str, name: str = "Unknown",
                  artist: str = "Unknown", album: str = "",
                  cover: str = "", outdir: str = None,
                  with_cover: bool = True, with_lyrics: bool = True,
                  timeout: float = 120) -> dict:
    """Download a song via the backend server with JSON response.

    The web server returns JSON when embed=1 is set (local save mode).
    """
    params = {
        "id": song_id,
        "source": source,
        "name": name,
        "artist": artist,
        "album": album,
        "cover": cover,
        "embed": "1",
        "stream": "0",
        "save_local": "1",
    }
    if with_cover:
        params["with_cover"] = "1"
    if with_lyrics:
        params["with_lyrics"] = "1"
    if outdir:
        params["outdir"] = outdir

    resp = _get("/download", params=params, timeout=timeout)
    resp.raise_for_status()

    try:
        result = resp.json()
        return {
            "success": result.get("status") == "ok",
            "saved": result.get("saved", False),
            "path": result.get("path", ""),
            "filename": result.get("filename", ""),
            "warning": result.get("warning", ""),
            "source": source,
            "song_id": song_id,
        }
    except (json.JSONDecodeError, ValueError):
        # If response is not JSON, it returned the file directly
        return {
            "success": True,
            "saved": False,
            "path": "",
            "filename": f"{name} - {artist}",
            "warning": "File streamed directly (not saved locally)",
            "source": source,
            "song_id": song_id,
        }


# ── Cookie Management ──────────────────────────────────────────────────

def get_cookies() -> dict:
    """Get all cookies from the backend."""
    resp = _get("/cookies")
    resp.raise_for_status()
    return resp.json()


def set_cookies(cookies: dict) -> bool:
    """Set cookies on the backend."""
    resp = _post("/cookies", json_data=cookies)
    resp.raise_for_status()
    return resp.json().get("status") == "ok"


def get_cookie(source: str) -> str:
    """Get a specific source's cookie."""
    cookies = get_cookies()
    return cookies.get(source, "")


# ── Settings Management ────────────────────────────────────────────────

def get_settings() -> dict:
    """Get web/download settings from the backend."""
    resp = _get("/settings")
    resp.raise_for_status()
    return resp.json()


def update_settings(settings: dict) -> dict:
    """Update settings on the backend."""
    resp = _post("/settings", json_data=settings)
    resp.raise_for_status()
    return resp.json()


# ── Source Switching ───────────────────────────────────────────────────

def switch_source(name: str, artist: str, current_source: str,
                  target_source: str, duration: int = 0,
                  timeout: float = 30) -> dict:
    """Switch a song's source to find an alternative version."""
    params = {
        "name": name,
        "artist": artist,
        "source": current_source,
        "target": target_source,
        "duration": str(duration),
    }
    resp = _get("/switch_source", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── Utility ────────────────────────────────────────────────────────────

import shutil as shutil_which_helper
shutil_which = shutil_which_helper.which


def get_source_list() -> list[dict]:
    """Get list of all supported sources with descriptions."""
    return [
        {"key": s, "name": SOURCE_DESCRIPTIONS.get(s, s)}
        for s in ALL_SOURCES
    ]


def health_check() -> dict:
    """Check if the backend server is healthy."""
    try:
        resp = _get("/healthz", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return {"status": "healthy", "app": data.get("app", "go-music-dl")}
        return {"status": "unhealthy", "code": resp.status_code}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}


def parse_share_url(url: str) -> dict:
    """Parse a music share URL to identify source, type, and ID."""
    result = {"url": url, "source": "", "type": "song", "id": ""}

    # Source detection patterns
    patterns = [
        (r"music\.163\.com", "netease"),
        (r"y\.qq\.com", "qq"),
        (r"kugou\.com", "kugou"),
        (r"kuwo\.cn", "kuwo"),
        (r"music\.migu\.cn", "migu"),
        (r"bilibili\.com", "bilibili"),
        (r"music\.apple\.com", "apple"),
        (r"qianqian\.com", "qianqian"),
    ]
    for pattern, source in patterns:
        if re.search(pattern, url):
            result["source"] = source
            break

    # Type and ID extraction
    type_patterns = [
        (r"(?:song|music)[?/=](\d+)", "song"),
        (r"(?:playlist|list)[?/=](\d+)", "playlist"),
        (r"(?:album)[?/=](\d+)", "album"),
        (r"/([a-zA-Z0-9]+)(?:\?|$)", "song"),
    ]
    for pattern, type_name in type_patterns:
        match = re.search(pattern, url)
        if match:
            result["type"] = type_name
            result["id"] = match.group(1)
            break

    return result


def cleanup(timeout: float = 3):
    """Clean up backend resources."""
    try:
        stop_server()
    except Exception:
        pass
    try:
        _session.close()
    except Exception:
        pass
