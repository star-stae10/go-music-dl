"""cli-anything-go-music-dl — Main CLI entry point.

Provides a Click-based command-line interface for go-music-dl, the aggregated
music search and download tool supporting 13+ music platforms.

Usage:
    cli-anything-go-music-dl                          # Enter interactive REPL
    cli-anything-go-music-dl search "周杰伦"           # Search songs
    cli-anything-go-music-dl download --id 123456 --source netease
    cli-anything-go-music-dl server start             # Start backend
    cli-anything-go-music-dl --json search "周杰伦"    # JSON output
"""

import json
import os
import sys
import atexit
from pathlib import Path

import click

from cli_anything.go_music_dl import __version__
from cli_anything.go_music_dl.core import project as _project
from cli_anything.go_music_dl.core import session as _session
from cli_anything.go_music_dl.core import export as _export
from cli_anything.go_music_dl.utils import backend as _backend

# ── Global state for REPL detection ────────────────────────────────────
_repl_mode = False


# ── Output helpers ─────────────────────────────────────────────────────

def _out(data, as_json: bool):
    """Print data as JSON or human-readable depending on --json flag."""
    if as_json:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        if isinstance(data, list):
            if not data:
                click.echo("  (empty)")
            else:
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        click.echo(f"  [{i+1}] {item.get('name', 'Unknown')}")
                        for k, v in item.items():
                            if k not in ("name",) and v:
                                click.echo(f"       {k}: {v}")
                    else:
                        click.echo(f"  [{i+1}] {item}")
                click.echo(f"  ── {len(data)} results")
        elif isinstance(data, dict):
            for k, v in data.items():
                if v or v == 0:
                    click.echo(f"  {k}: {v}")
        elif data is None:
            click.echo("")
        else:
            click.echo(str(data))


def _err(msg: str):
    click.echo(f"  ✗ {msg}", err=True)


def _ok(msg: str):
    click.echo(f"  ✓ {msg}")


def _warn(msg: str):
    click.echo(f"  ⚠ {msg}")


# ── Error handler ──────────────────────────────────────────────────────

def handle_error(msg: str, as_json: bool, exit_code: int = 1):
    """Print error and exit."""
    if as_json:
        click.echo(json.dumps({"error": msg}))
    else:
        _err(msg)
    sys.exit(exit_code)


# ── Common options ─────────────────────────────────────────────────────

def _common_options(f):
    """Add --source, --cover, --lyrics options to a command."""
    f = click.option("--lyrics/--no-lyrics", "with_lyrics", default=True,
                     help="Download lyrics")(f)
    f = click.option("--cover/--no-cover", "with_cover", default=True,
                     help="Download cover art")(f)
    f = click.option("--source", "-s", "source", default="netease",
                     help="Music source (netease, qq, kugou, etc.)")(f)
    return f


# ── Root group ─────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Path to project file")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Run command without saving changes to disk")
@click.version_option(__version__, prog_name="cli-anything-go-music-dl")
@click.pass_context
def cli(ctx, as_json, project_path, dry_run):
    """cli-anything-go-music-dl — Aggregated music search & download CLI.

    Supports 13+ music platforms: netease, qq, kugou, kuwo, migu,
    qianqian, soda, fivesing, jamendo, joox, bilibili, apple, local.

    If no subcommand is given, enters the interactive REPL.
    """
    ctx.ensure_object(dict)
    ctx.obj["as_json"] = as_json
    ctx.obj["dry_run"] = dry_run
    ctx.obj["project_path"] = project_path

    # Load or create session
    sess = _session.get_session()
    if project_path:
        try:
            proj = _project.open_project(project_path)
            sess.set_project(proj, project_path)
        except FileNotFoundError:
            pass
    ctx.obj["session"] = sess

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.result_callback()
def auto_save_on_exit(result, as_json, project_path, dry_run, **kwargs):
    """Auto-save project after one-shot commands if state was modified.

    Saves project in plain format (not session-wrapped) to keep the file
    compatible with `project info` and other project commands.
    """
    global _repl_mode
    if _repl_mode:
        return
    if dry_run:
        return
    sess = _session.get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            # Save as plain project JSON (not session-wrapped)
            _project.save_project(sess.project, sess.project_path)
            sess._modified = False
        except Exception as e:
            click.echo(f"Warning: Auto-save failed: {e}", err=True)


# ── REPL ───────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def repl(ctx):
    """Enter the interactive REPL session."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.go_music_dl.utils.repl_skin import ReplSkin
    sess = _session.get_session()
    skin = ReplSkin("go-music-dl", version=__version__)
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    repl_commands = {
        "search <keyword>":       "Search songs across sources",
        "search playlist <kw>":   "Search playlists",
        "search album <kw>":      "Search albums",
        "download <id>":          "Download a song by ID",
        "inspect <id>":           "Inspect a song (get download URL info)",
        "playlist <source> <id>": "Get playlist songs",
        "album <source> <id>":    "Get album songs",
        "sources":                "List supported music sources",
        "cookies":                "Show stored cookies",
        "settings":               "Show current settings",
        "server start":           "Start the backend web server",
        "server stop":            "Stop the backend web server",
        "server status":          "Check server status",
        "project info":           "Show current project info",
        "undo":                   "Undo last operation",
        "redo":                   "Redo last undone operation",
        "history":                "Show download history",
        "help":                   "Show this help",
        "exit / quit":            "Exit REPL",
    }

    skin.help(repl_commands)
    click.echo("")

    while True:
        try:
            modified = sess.modified if sess.has_project() else False
            proj_name = sess.project.name if sess.project else "no-project"
            line = skin.get_input(pt_session, project_name=proj_name, modified=modified)
        except (KeyboardInterrupt, EOFError):
            click.echo("")
            break

        if not line or not line.strip():
            continue

        parts = _parse_repl_line(line.strip())
        if not parts:
            continue

        cmd = parts[0]
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            break
        elif cmd == "help":
            skin.help(repl_commands)
        elif cmd == "sources":
            _out(_backend.get_source_list(), as_json=False)
        elif cmd == "cookies":
            if _backend.server_running():
                _out(_backend.get_cookies(), as_json=False)
            else:
                _warn("Server not running. Use 'server start' first.")
        elif cmd == "settings":
            if _backend.server_running():
                _out(_backend.get_settings(), as_json=False)
            else:
                _warn("Server not running. Use 'server start' first.")
        elif cmd == "server":
            _handle_server_repl(args, skin)
        elif cmd == "project":
            _handle_project_repl(args, skin)
        elif cmd == "search":
            _handle_search_repl(args, skin)
        elif cmd == "download":
            _handle_download_repl(args, skin)
        elif cmd == "inspect":
            _handle_inspect_repl(args, skin)
        elif cmd in ("playlist", "album"):
            _handle_collection_repl(cmd, args, skin)
        elif cmd == "history":
            downloads = sess.get_downloads()
            if not downloads:
                skin.info("No downloads yet.")
            else:
                for d in downloads:
                    click.echo(f"  {d.get('name', '?')} → {d.get('path', '?')}")
        elif cmd == "undo":
            state = sess.undo()
            if state:
                skin.success(f"Undone: {state.get('description', '')}")
            else:
                skin.warning("Nothing to undo.")
        elif cmd == "redo":
            state = sess.redo()
            if state:
                skin.success(f"Redone: {state.get('description', '')}")
            else:
                skin.warning("Nothing to redo.")
        else:
            skin.error(f"Unknown command: {cmd}. Type 'help' for available commands.")

    skin.print_goodbye()


def _parse_repl_line(line: str) -> list[str]:
    """Parse a REPL line into parts, respecting quoted strings."""
    parts = []
    current = []
    in_quote = False
    quote_char = None
    for ch in line:
        if in_quote:
            if ch == quote_char:
                in_quote = False
            else:
                current.append(ch)
        elif ch in ('"', "'"):
            in_quote = True
            quote_char = ch
        elif ch.isspace():
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _handle_server_repl(args: list[str], skin):
    """Handle 'server' subcommands in REPL."""
    sub = args[0] if args else "status"
    if sub == "start":
        try:
            info = _backend.start_server()
            skin.success(f"Server started on port {info['port']} (PID: {info['pid']})")
            sess = _session.get_session()
            sess.set_server(info["port"], info["pid"])
        except _backend.BackendError as e:
            skin.error(str(e))
    elif sub == "stop":
        _backend.stop_server()
        sess = _session.get_session()
        sess.clear_server()
        skin.success("Server stopped.")
    elif sub == "status":
        if _backend.server_running():
            skin.success("Server is running")
        else:
            skin.warning("Server is not running")
    else:
        skin.error(f"Unknown server subcommand: {sub}")


def _handle_project_repl(args: list[str], skin):
    """Handle 'project' subcommands in REPL."""
    sub = args[0] if args else "info"
    sess = _session.get_session()
    if sub == "info":
        if sess.project:
            _out(_project.project_info(sess.project), as_json=False)
        else:
            skin.info("No active project.")
    elif sub == "new" and len(args) >= 2:
        name = args[1]
        proj = _project.create_project(name=name)
        sess.set_project(proj)
        sess.snapshot(f"Created project: {name}")
        skin.success(f"Created project: {name}")
    elif sub == "save":
        if sess.project_path and sess.project:
            _project.save_project(sess.project, sess.project_path)
            skin.success(f"Saved to {sess.project_path}")
        else:
            skin.warning("No project file path set.")
    elif sub == "set" and len(args) >= 2:
        key = args[1]
        val = " ".join(args[2:]) if len(args) > 2 else ""
        if sess.project and hasattr(sess.project, key):
            setattr(sess.project, key, val)
            sess.snapshot(f"Set {key}={val}")
            skin.success(f"Set {key} = {val}")
        else:
            skin.error(f"Unknown setting: {key}")
    else:
        skin.error(f"Usage: project new <name> | info | save | set <key> <val>")


def _handle_search_repl(args: list[str], skin):
    """Handle 'search' in REPL."""
    if not args:
        skin.error("Usage: search <keyword> [playlist|album] [--source SRC]")
        return

    kw = args[0]
    search_type = "song"
    sources = _backend.DEFAULT_SOURCES

    remaining = args[1:]
    if remaining and remaining[0] in ("playlist", "album"):
        search_type = remaining[0]
        remaining = remaining[1:]

    # Parse --source flag
    for i, arg in enumerate(remaining):
        if arg == "--source" and i + 1 < len(remaining):
            sources = [remaining[i + 1]]

    skin.info(f"Searching {search_type}s for '{kw}'...")
    try:
        if search_type == "playlist":
            results = _backend.search_playlists(kw, sources)
        elif search_type == "album":
            results = _backend.search_albums(kw, sources)
        else:
            results = _backend.search_songs(kw, sources)
        _out(results, as_json=False)
    except _backend.BackendError as e:
        skin.error(str(e))


def _handle_download_repl(args: list[str], skin):
    """Handle 'download' in REPL."""
    if not args:
        skin.error("Usage: download <id> [--source SRC] [--name NAME] [--artist ARTIST]")
        return

    song_id = args[0]
    source = "netease"
    name = "Unknown"
    artist = "Unknown"
    album = ""

    remaining = args[1:]
    for i, arg in enumerate(remaining):
        if arg == "--source" and i + 1 < len(remaining):
            source = remaining[i + 1]
        elif arg == "--name" and i + 1 < len(remaining):
            name = remaining[i + 1]
        elif arg == "--artist" and i + 1 < len(remaining):
            artist = remaining[i + 1]
        elif arg == "--album" and i + 1 < len(remaining):
            album = remaining[i + 1]

    skin.info(f"Downloading {name} from {source}...")
    try:
        result = _backend.download_song(
            source=source, song_id=song_id,
            name=name, artist=artist, album=album,
        )
        if result.get("success"):
            skin.success(f"Downloaded: {result.get('filename', '?')}")
            if result.get("path"):
                click.echo(f"  Path: {result['path']}")
            # Record in session
            sess = _session.get_session()
            sess.add_download(result)
            sess.snapshot(f"Downloaded {name}")
        else:
            skin.error(result.get("error", "Download failed"))
    except _backend.BackendError as e:
        skin.error(str(e))


def _handle_inspect_repl(args: list[str], skin):
    """Handle 'inspect' in REPL."""
    if len(args) < 1:
        skin.error("Usage: inspect <id> [--source SRC] [--duration SEC]")
        return

    song_id = args[0]
    source = "netease"
    duration = 0
    remaining = args[1:]
    for i, arg in enumerate(remaining):
        if arg == "--source" and i + 1 < len(remaining):
            source = remaining[i + 1]
        elif arg == "--duration" and i + 1 < len(remaining):
            try:
                duration = int(remaining[i + 1])
            except ValueError:
                pass

    try:
        result = _backend.inspect_song(source, song_id, duration)
        _out(result, as_json=False)
    except _backend.BackendError as e:
        skin.error(str(e))


def _handle_collection_repl(cmd: str, args: list[str], skin):
    """Handle 'playlist' or 'album' in REPL."""
    if len(args) < 2:
        skin.error(f"Usage: {cmd} <source> <id>")
        return

    source = args[0]
    col_id = args[1]

    skin.info(f"Getting {cmd} songs from {source}...")
    try:
        if cmd == "playlist":
            songs = _backend.get_playlist_songs(source, col_id)
        else:
            songs = _backend.get_album_songs(source, col_id)
        _out(songs, as_json=False)
    except _backend.BackendError as e:
        skin.error(str(e))


# ── Server Commands ────────────────────────────────────────────────────

@cli.group()
def server():
    """Manage the backend music-dl web server."""
    pass


@server.command()
@click.option("--port", "-p", default=8099, help="Server port")
@click.option("--timeout", "-t", default=15.0, help="Startup timeout (seconds)")
@click.pass_context
def start(ctx, port, timeout):
    """Start the backend web server."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    config = _backend.BackendConfig(port=port, startup_timeout=timeout)
    try:
        info = _backend.start_server(config)
        sess = _session.get_session()
        sess.set_server(info["port"], info["pid"])
        _ok(f"Server started on port {info['port']} (PID: {info['pid']})")
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


@server.command()
@click.pass_context
def stop(ctx):
    """Stop the backend web server."""
    _backend.stop_server()
    sess = _session.get_session()
    sess.clear_server()
    _ok("Server stopped.")


@server.command()
@click.pass_context
def status(ctx):
    """Check if the backend server is running."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    result = _backend.health_check()
    _out(result, as_json)


# ── Search Commands ────────────────────────────────────────────────────

@cli.command()
@click.argument("keyword")
@click.option("--source", "-s", multiple=True, help="Source(s) to search")
@click.option("--type", "search_type", type=click.Choice(["song", "playlist", "album"]),
              default="song", help="Search type")
@click.option("--limit", "-l", default=50, help="Max results per source")
@click.pass_context
def search(ctx, keyword, source, search_type, limit):
    """Search songs, playlists, or albums across music sources."""
    as_json = ctx.obj.get("as_json", False)

    sources = list(source) if source else None

    try:
        if search_type == "playlist":
            results = _backend.search_playlists(keyword, sources)
        elif search_type == "album":
            results = _backend.search_albums(keyword, sources)
        else:
            results = _backend.search_songs(keyword, sources)

        if limit and len(results) > limit:
            results = results[:limit]

        _out(results, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Inspect Command ────────────────────────────────────────────────────

@cli.command()
@click.option("--id", "song_id", required=True, help="Song ID")
@click.option("--source", "-s", default="netease", help="Music source")
@click.option("--duration", "-d", default=0, type=int, help="Song duration (s)")
@click.pass_context
def inspect(ctx, song_id, source, duration):
    """Inspect a song to get download URL, size, and bitrate."""
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _backend.inspect_song(source, song_id, duration)
        _out(result, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Download Commands ──────────────────────────────────────────────────

@cli.command()
@click.option("--id", "song_id", required=True, help="Song ID")
@click.option("--source", "-s", default="netease", help="Music source")
@click.option("--name", "-n", default="Unknown", help="Song name")
@click.option("--artist", "-a", default="Unknown", help="Artist name")
@click.option("--album", "-b", default="", help="Album name")
@click.option("--outdir", "-o", default=None, help="Output directory")
@click.option("--cover/--no-cover", default=True, help="Download cover art")
@click.option("--lyrics/--no-lyrics", default=True, help="Download lyrics")
@click.pass_context
def download(ctx, song_id, source, name, artist, album, outdir, cover, lyrics):
    """Download a song by ID from a specific source."""
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _backend.download_song(
            source=source, song_id=song_id,
            name=name, artist=artist, album=album,
            outdir=outdir, with_cover=cover, with_lyrics=lyrics,
        )
        if result.get("success"):
            sess = _session.get_session()
            sess.add_download(result)
            sess.snapshot(f"Downloaded {name}")
        _out(result, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Playlist / Album Commands ──────────────────────────────────────────

@cli.command()
@click.argument("source")
@click.argument("playlist_id")
@click.pass_context
def playlist(ctx, source, playlist_id):
    """Get songs from a playlist."""
    as_json = ctx.obj.get("as_json", False)
    try:
        songs = _backend.get_playlist_songs(source, playlist_id)
        _out(songs, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


@cli.command()
@click.argument("source")
@click.argument("album_id")
@click.pass_context
def album(ctx, source, album_id):
    """Get songs from an album."""
    as_json = ctx.obj.get("as_json", False)
    try:
        songs = _backend.get_album_songs(source, album_id)
        _out(songs, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Sources Command ────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def sources(ctx):
    """List all supported music sources."""
    as_json = ctx.obj.get("as_json", False)
    result = _backend.get_source_list()
    _out(result, as_json)


# ── Cookies Commands ───────────────────────────────────────────────────

@cli.group()
def cookies():
    """Manage authentication cookies per source."""
    pass


@cookies.command("list")
@click.pass_context
def cookies_list(ctx):
    """List all stored cookies."""
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _backend.get_cookies()
        _out(result, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


@cookies.command("set")
@click.argument("source")
@click.argument("value")
@click.pass_context
def cookies_set(ctx, source, value):
    """Set a cookie for a specific source."""
    as_json = ctx.obj.get("as_json", False)
    try:
        success = _backend.set_cookies({source: value})
        if success:
            _ok(f"Cookie set for {source}")
        else:
            handle_error("Failed to set cookie", as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Settings Commands ──────────────────────────────────────────────────

@cli.group()
def settings():
    """View and modify configuration settings."""
    pass


@settings.command("show")
@click.pass_context
def settings_show(ctx):
    """Show current settings."""
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _backend.get_settings()
        _out(result, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


@settings.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def settings_set(ctx, key, value):
    """Set a configuration key to a value."""
    as_json = ctx.obj.get("as_json", False)
    try:
        current = _backend.get_settings()
        # Try to convert value to appropriate type
        if key in current:
            current_type = type(current[key])
            if current_type == bool:
                value = value.lower() in ("true", "1", "yes")
            elif current_type == int:
                value = int(value)
            elif current_type == float:
                value = float(value)
        current[key] = value
        result = _backend.update_settings(current)
        _out(result, as_json)
    except _backend.BackendError as e:
        handle_error(str(e), as_json)


# ── Project Commands ───────────────────────────────────────────────────

@cli.group()
def project():
    """Manage music-dl projects."""
    pass


@project.command("new")
@click.argument("name")
@click.option("--source", "-s", default="netease", help="Default source")
@click.option("--outdir", "-o", default="./downloads", help="Download directory")
@click.option("--output", "-O", "output_path", default=None,
              help="Project file path (default: <name>.json)")
@click.pass_context
def project_new(ctx, name, source, outdir, output_path):
    """Create a new project."""
    as_json = ctx.obj.get("as_json", False)
    proj = _project.create_project(name=name, active_source=source, download_dir=outdir)
    path = output_path or f"{name}.json"
    _project.save_project(proj, path)
    sess = _session.get_session()
    sess.set_project(proj, path)
    sess.snapshot(f"Created project: {name}")
    result = {"name": name, "path": os.path.abspath(path), "source": source}
    _out(result, as_json)


@project.command("info")
@click.option("--project", "project_path", default=None, help="Project file path")
@click.pass_context
def project_info(ctx, project_path):
    """Show project information."""
    as_json = ctx.obj.get("as_json", False)
    path = project_path or ctx.obj.get("project_path")
    if path and os.path.exists(path):
        # Detect whether file is session-format or plain project-format
        import json as _json
        with open(path, "r", encoding="utf-8") as _f:
            _raw = _json.load(_f)
        if isinstance(_raw, dict) and "project" in _raw:
            # Session-wrapped project
            proj = _project.Project.from_dict(_raw["project"])
        else:
            proj = _project.open_project(path)
        _out(_project.project_info(proj), as_json)
    else:
        sess = _session.get_session()
        if sess.project:
            _out(_project.project_info(sess.project), as_json)
        else:
            handle_error("No active project", as_json)


@project.command("save")
@click.option("--project", "project_path", default=None, help="Project file path")
@click.pass_context
def project_save(ctx, project_path):
    """Save the current project."""
    as_json = ctx.obj.get("as_json", False)
    path = project_path or ctx.obj.get("project_path")
    if not path:
        handle_error("No project path specified", as_json)
    sess = _session.get_session()
    if not sess.project:
        handle_error("No active project", as_json)
    _project.save_project(sess.project, path)
    sess._modified = False
    _ok(f"Saved to {os.path.abspath(path)}")


@project.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def project_set(ctx, key, value):
    """Set a project property (active_source, download_dir, etc.)."""
    as_json = ctx.obj.get("as_json", False)
    sess = _session.get_session()
    if not sess.project:
        handle_error("No active project", as_json)
    if not hasattr(sess.project, key):
        handle_error(f"Unknown property: {key}", as_json)
    setattr(sess.project, key, value)
    sess._modified = True
    sess.snapshot(f"Set {key}={value}")
    _ok(f"Set {key} = {value}")


# ── Session Commands ───────────────────────────────────────────────────

@cli.command()
@click.pass_context
def status(ctx):
    """Show current session status."""
    as_json = ctx.obj.get("as_json", False)
    sess = _session.get_session()
    result = {
        "has_project": sess.has_project(),
        "project_name": sess.project.name if sess.project else None,
        "modified": sess.modified,
        "server": sess.server_info,
        "server_running": sess.is_server_running(),
        "downloads_count": len(sess.get_downloads()),
        "undo_available": sess.can_undo(),
        "redo_available": sess.can_redo(),
    }
    _out(result, as_json)


@cli.command()
@click.pass_context
def undo(ctx):
    """Undo the last operation."""
    as_json = ctx.obj.get("as_json", False)
    sess = _session.get_session()
    state = sess.undo()
    if state:
        result = {"undone": state.get("description", "")}
        _out(result, as_json)
    else:
        handle_error("Nothing to undo", as_json)


@cli.command()
@click.pass_context
def redo(ctx):
    """Redo the last undone operation."""
    as_json = ctx.obj.get("as_json", False)
    sess = _session.get_session()
    state = sess.redo()
    if state:
        result = {"redone": state.get("description", "")}
        _out(result, as_json)
    else:
        handle_error("Nothing to redo", as_json)


@cli.command()
@click.pass_context
def history(ctx):
    """Show download history."""
    as_json = ctx.obj.get("as_json", False)
    sess = _session.get_session()
    downloads = sess.get_downloads()
    _out(downloads, as_json)


# ── Parse URL Command ─────────────────────────────────────────────────

@cli.command()
@click.argument("url")
@click.pass_context
def parse(ctx, url):
    """Parse a music share URL to identify source and ID."""
    as_json = ctx.obj.get("as_json", False)
    result = _backend.parse_share_url(url)
    _out(result, as_json)


# ── Cleanup on exit ───────────────────────────────────────────────────

@atexit.register
def _cleanup():
    """Clean up backend resources on exit."""
    try:
        _backend.cleanup()
    except Exception:
        pass


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
