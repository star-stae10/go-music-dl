"""cli-anything-go-music-dl REPL Skin."""

import os
import sys
from pathlib import Path

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_UNDERLINE = "\033[4m"

_CYAN = "\033[38;5;80m"
_CYAN_BG = "\033[48;5;80m"
_WHITE = "\033[97m"
_GRAY = "\033[38;5;245m"
_DARK_GRAY = "\033[38;5;240m"
_LIGHT_GRAY = "\033[38;5;250m"

_ACCENT_COLORS = {
    "gimp":        "\033[38;5;214m",
    "blender":     "\033[38;5;208m",
    "inkscape":    "\033[38;5;39m",
    "audacity":    "\033[38;5;33m",
    "libreoffice": "\033[38;5;40m",
    "obs_studio":  "\033[38;5;55m",
    "kdenlive":    "\033[38;5;69m",
    "shotcut":     "\033[38;5;35m",
}
_DEFAULT_ACCENT = "\033[38;5;75m"

_GREEN = "\033[38;5;78m"
_YELLOW = "\033[38;5;220m"
_RED = "\033[38;5;196m"
_BLUE = "\033[38;5;75m"
_MAGENTA = "\033[38;5;176m"

_SKILL_SOURCE_REPO = os.environ.get("CLI_ANYTHING_SKILL_REPO", "HKUDS/CLI-Anything")

_ICON = f"{_CYAN}{_BOLD}◆{_RESET}"
_ICON_SMALL = f"{_CYAN}▸{_RESET}"

_H_LINE = "─"
_V_LINE = "│"
_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"
_T_DOWN = "┬"
_T_UP = "┴"
_T_RIGHT = "├"
_T_LEFT = "┤"


class ReplSkin:
    """Unified REPL skin for cli-anything CLI harnesses."""

    def __init__(self, software_name: str, version: str = "1.0.0",
                 accent_color: str = None):
        self.name = software_name
        self.version = version
        self.accent = accent_color or _ACCENT_COLORS.get(
            software_name.replace("-", "_"), _DEFAULT_ACCENT
        )

    def _skill_path(self) -> str:
        """Return the path to SKILL.md, preferring repo-root then packaged copy."""
        repo_skill = Path("skills") / f"cli-anything-{self.name}" / "SKILL.md"
        if repo_skill.exists():
            return str(repo_skill.resolve())
        pkg_skill = Path(__file__).resolve().parent.parent / "skills" / "SKILL.md"
        if pkg_skill.exists():
            return str(pkg_skill.resolve())
        return "(not found)"

    def print_banner(self):
        """Print branded startup banner."""
        skill_path = self._skill_path()
        accent = self.accent
        reset = _RESET
        bold = _BOLD
        dim = _DIM
        cyan = _CYAN
        name = self.name.upper()
        banner = (
            f"{_TL}{_H_LINE * 62}{_TR}\n"
            f"{_V_LINE}  {accent}{bold}◆  cli-anything {name}{reset}  "
            f"v{self.version}{' ' * (34 - len(self.version))}{_V_LINE}\n"
            f"{_T_RIGHT}{_H_LINE * 62}{_T_LEFT}\n"
            f"{_V_LINE}  {dim}Interative REPL for {self.name}{' ' * (40 - len(self.name))}{_V_LINE}\n"
            f"{_V_LINE}  {dim}Skill: {skill_path}{' ' * max(2, 56 - len(skill_path))}{_V_LINE}\n"
            f"{_V_LINE}  {dim}Type 'help' for commands, 'exit' to quit{' ' * 19}{_V_LINE}\n"
            f"{_BL}{_H_LINE * 62}{_BR}{reset}"
        )
        print(banner, file=sys.stderr)

    def create_prompt_session(self):
        """Create a prompt_toolkit session if available, else return None."""
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory
            from prompt_toolkit.styles import Style

            style = Style.from_dict({
                "prompt": f"{self.accent} bold",
                "trailing_input": _DIM,
            })
            return PromptSession(
                history=InMemoryHistory(),
                style=style,
                enable_history_search=True,
            )
        except ImportError:
            return None

    def get_input(self, pt_session=None, project_name="", modified=False):
        """Get user input with an appropriate prompt."""
        mod_marker = f" {_YELLOW}*{_RESET}" if modified else ""
        prefix = f"{_ICON_SMALL} {project_name}{mod_marker} > "
        if pt_session:
            from prompt_toolkit import prompt as pt_prompt
            return pt_prompt(prefix, session=pt_session)
        try:
            return input(prefix)
        except (EOFError, KeyboardInterrupt):
            raise

    def help(self, commands: dict):
        """Print formatted help listing."""
        print(f"\n  {self.accent}{_BOLD}Commands:{_RESET}", file=sys.stderr)
        for cmd, desc in commands.items():
            print(f"    {_CYAN}{cmd:<28}{_RESET} {desc}", file=sys.stderr)
        print(file=sys.stderr)

    def success(self, msg: str):
        print(f"  {_GREEN}✓{_RESET} {msg}")

    def error(self, msg: str):
        print(f"  {_RED}✗{_RESET} {msg}", file=sys.stderr)

    def warning(self, msg: str):
        print(f"  {_YELLOW}⚠{_RESET} {msg}")

    def info(self, msg: str):
        print(f"  {_BLUE}●{_RESET} {msg}")

    def status(self, key: str, value: str):
        print(f"  {_DIM}{key}:{_RESET} {value}")

    def table(self, headers: list[str], rows: list[list[str]]):
        """Print a formatted table."""
        if not rows:
            return
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        header_str = "  ".join(
            f"{_BOLD}{h:<{w}}{_RESET}" for h, w in zip(headers, col_widths)
        )
        print(f"  {header_str}")
        print(f"  {_DIM}{'-' * (sum(col_widths) + 2 * (len(headers) - 1))}{_RESET}")
        for row in rows:
            row_str = "  ".join(
                f"{str(c):<{w}}" for c, w in zip(row, col_widths)
            )
            print(f"  {row_str}")

    def progress(self, current: int, total: int, label: str = ""):
        """Print a simple progress bar."""
        bar_width = 30
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = f"{_GREEN}{'█' * filled}{_DIM}{'░' * (bar_width - filled)}{_RESET}"
        pct = f"{100 * current // total}%" if total > 0 else "?"
        label_text = f" {label}" if label else ""
        print(f"  {bar} {pct}{label_text}", end="\r", file=sys.stderr)
        if current >= total:
            print(file=sys.stderr)

    def print_goodbye(self):
        """Print exit message."""
        print(f"\n  {_ICON}  {_DIM}Goodbye!{_RESET}\n")
