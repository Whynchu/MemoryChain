"""Terminal environment — title, screen, directory context, git detection.

Handles the 'exclusive mode' feel: sets terminal title, clears screen,
detects working directory and git context, restores state on exit.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# ── Terminal Title ───────────────────────────────────────────

_original_title: str | None = None


def set_title(title: str = "MemoryChain") -> None:
    """Set the terminal window title. Saves original for restore."""
    global _original_title
    if _original_title is None:
        _original_title = os.environ.get("PROMPT", None)

    if sys.platform == "win32":
        try:
            # Windows: use ctypes for reliable title setting
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            # Fallback to ANSI escape (works in Windows Terminal)
            sys.stdout.write(f"\033]0;{title}\007")
            sys.stdout.flush()
    else:
        # Unix: ANSI escape sequence
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


def restore_title() -> None:
    """Restore the original terminal title."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("Windows PowerShell")
        except Exception:
            pass
    else:
        sys.stdout.write("\033]0;\007")
        sys.stdout.flush()


def clear_screen() -> None:
    """Clear the terminal screen."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


# ── Directory & Git Context ──────────────────────────────────

def get_cwd() -> str:
    """Get the current working directory as a display string."""
    cwd = Path.cwd()
    home = Path.home()
    try:
        relative = cwd.relative_to(home)
        return "~/" + str(relative).replace("\\", "/")
    except ValueError:
        return str(cwd)


def get_short_cwd(max_parts: int = 3) -> str:
    """Get a shortened cwd for the prompt — last N path components."""
    cwd = Path.cwd()
    home = Path.home()
    try:
        relative = cwd.relative_to(home)
        parts = relative.parts
    except ValueError:
        parts = cwd.parts

    if len(parts) <= max_parts:
        return "~/" + "/".join(parts) if cwd != home else "~"

    # Show …/last/few/parts
    return "…/" + "/".join(parts[-max_parts:])


def detect_git() -> dict[str, str] | None:
    """Detect git repo info if we're inside one. Returns {branch, root} or None."""
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2,
        )
        if root.returncode != 0:
            return None

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )

        return {
            "root": root.stdout.strip(),
            "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_terminal_width() -> int:
    """Get the current terminal width."""
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


# ── Account context ──────────────────────────────────────────

def get_account_display() -> str:
    """Get a short account display string from config."""
    from . import settings
    config = settings.load_config()
    name = config.get("account_name", "")
    email = config.get("account_email", "")
    if name:
        return name
    if email:
        return email
    if config.get("openai_api_key"):
        return "API key configured"
    return "not configured"


def get_data_dir() -> str:
    """Get the MemoryChain data directory path."""
    from . import settings
    return str(settings.CONFIG_DIR)
