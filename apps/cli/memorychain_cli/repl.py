"""Interactive REPL — the default experience when you run `memorychain`.

Provides a Copilot/Codex-style terminal takeover with branded header,
directory-aware prompt, and exclusive-mode feel.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from rich.panel import Panel
from rich.text import Text
from rich import box

from . import client
from .config import API_BASE_URL, USER_ID
from .display import (
    console,
    show_chat_response,
    show_error,
    show_goals,
    show_heuristics,
    show_insights,
    show_review,
    show_search_results,
    show_success,
    show_tasks,
    show_today,
)
from .terminal import (
    set_title,
    restore_title,
    clear_screen,
    get_cwd,
    get_short_cwd,
    detect_git,
    get_account_display,
    get_data_dir,
)
from .theme import (
    BLUE, BLUE_BRIGHT, BLUE_DIM, GREY_MID, GREY_DARK, GREEN, RED, PT_STYLE,
)

# Slash commands the completer knows about
SLASH_COMMANDS = [
    "/today", "/review", "/search", "/insights", "/detect",
    "/promote", "/accept", "/reject", "/goals", "/tasks",
    "/heuristics", "/status", "/help", "/clear", "/quit", "/exit",
    "/checkin", "/onboard",
]

HELP_TEXT = f"""\
[bold {BLUE}]MemoryChain[/bold {BLUE}] — interactive mode

[bold]Just type naturally[/bold] to log entries, ask questions, or chat.
  [{GREY_MID}]e.g. "Slept 7h, mood 8/10. Morning run 5k."[/{GREY_MID}]
  [{GREY_MID}]e.g. "How has my sleep been this week?"[/{GREY_MID}]
  [{GREY_MID}]e.g. "hey! what can you do?"[/{GREY_MID}]

[bold]Slash commands:[/bold]
  [{BLUE_BRIGHT}]/today[/{BLUE_BRIGHT}]            Today's checkin, tasks, goals
  [{BLUE_BRIGHT}]/review[/{BLUE_BRIGHT}]           Show latest weekly review
  [{BLUE_BRIGHT}]/review generate[/{BLUE_BRIGHT}]  Generate a new weekly review
  [{BLUE_BRIGHT}]/search[/{BLUE_BRIGHT}] <query>   Search across all objects
  [{BLUE_BRIGHT}]/insights[/{BLUE_BRIGHT}]         List insight candidates
  [{BLUE_BRIGHT}]/detect[/{BLUE_BRIGHT}]           Run insight detectors
  [{BLUE_BRIGHT}]/promote[/{BLUE_BRIGHT}] <id>     Promote insight → heuristic
  [{BLUE_BRIGHT}]/accept[/{BLUE_BRIGHT}] <id>      Accept candidate → active
  [{BLUE_BRIGHT}]/reject[/{BLUE_BRIGHT}] <id>      Reject an insight
  [{BLUE_BRIGHT}]/goals[/{BLUE_BRIGHT}]            List active goals
  [{BLUE_BRIGHT}]/tasks[/{BLUE_BRIGHT}]            List open tasks
  [{BLUE_BRIGHT}]/heuristics[/{BLUE_BRIGHT}]       List learned heuristics
  [{BLUE_BRIGHT}]/status[/{BLUE_BRIGHT}]           Check API connection
  [{BLUE_BRIGHT}]/clear[/{BLUE_BRIGHT}]            Clear the screen
  [{BLUE_BRIGHT}]/checkin[/{BLUE_BRIGHT}]          Start daily check-in
  [{BLUE_BRIGHT}]/onboard[/{BLUE_BRIGHT}]          Run onboarding questionnaire
  [{BLUE_BRIGHT}]/help[/{BLUE_BRIGHT}]             Show this help
  [{BLUE_BRIGHT}]/quit[/{BLUE_BRIGHT}]             Exit

"""

# ── Branded Header ───────────────────────────────────────────

_LOGO = f"""[bold {BLUE}]
 _____                       _____ _       _
|     |___ _____ ___ ___ _ _|     | |_ ___|_|___
| | | | -_|     | . |  _| | |   --|   | .'| |   |
|_|_|_|___|_|_|_|___|_| |_  |_____|_|_|__,|_|_|_|
                        |___|[/bold {BLUE}]"""


def _build_header() -> Panel:
    """Build the branded header panel with status info."""
    # Connection status
    try:
        client.health()
        api_status = f"[{GREEN}]● connected[/{GREEN}]"
    except Exception:
        api_status = f"[{RED}]● offline[/{RED}]"

    account = get_account_display()
    account_display = f"[{BLUE_BRIGHT}]{account}[/{BLUE_BRIGHT}]" if account != "not configured" else f"[{GREY_MID}]{account}[/{GREY_MID}]"

    # Git info
    git_info = detect_git()
    git_display = f"  [{GREY_MID}]{git_info['branch']}[/{GREY_MID}]" if git_info else ""

    # Build status lines
    cwd = get_cwd()

    header_text = Text.from_markup(
        f"{_LOGO}\n"
        f"  [{GREY_MID}]v0.3.0[/{GREY_MID}]\n\n"
        f"  [{GREY_MID}]API:[/{GREY_MID}]     {api_status}    [{GREY_MID}]Account:[/{GREY_MID}] {account_display}\n"
        f"  [{GREY_MID}]Dir:[/{GREY_MID}]     [{BLUE_BRIGHT}]{cwd}[/{BLUE_BRIGHT}]{git_display}\n"
        f"  [{GREY_MID}]Data:[/{GREY_MID}]    [{GREY_MID}]{get_data_dir()}[/{GREY_MID}]\n"
    )

    return Panel(
        header_text,
        border_style=BLUE_DIM,
        box=box.DOUBLE,
        padding=(0, 1),
        subtitle=f"[{GREY_MID}]Type naturally to log • ask questions • /help for commands[/{GREY_MID}]",
        subtitle_align="center",
    )


def _print_welcome() -> None:
    """Full terminal takeover: clear screen, set title, show branded header."""
    set_title("MemoryChain")
    clear_screen()
    console.print(_build_header())

    # Check LLM configuration — prompt setup if missing
    from .setup import check_and_prompt_setup
    check_and_prompt_setup()

    # Check if user needs onboarding
    _check_onboarding()

    console.print()


def _check_onboarding() -> None:
    """If user hasn't completed onboarding, offer to start it."""
    try:
        profile = client.get_user_profile()
        if profile and profile.get("onboarded_at"):
            return  # Already onboarded
    except Exception:
        return  # API not connected or no profile endpoint yet

    console.print()
    console.print(f"  [{BLUE_BRIGHT}]Welcome to MemoryChain![/{BLUE_BRIGHT}] Let's get you set up.")
    console.print(f"  [{GREY_MID}]I'll ask a few questions to personalize your experience.[/{GREY_MID}]")
    console.print()

    from prompt_toolkit import prompt as pt_prompt
    try:
        answer = pt_prompt("  Start onboarding? (Y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return

    if answer in ("", "y", "yes"):
        console.print(f"  [{GREY_MID}]Starting onboarding… type your answers to each question.[/{GREY_MID}]")
        console.print(f"  [{GREY_MID}]Use /onboard in the prompt if you want to restart later.[/{GREY_MID}]")
    else:
        console.print(f"  [{GREY_MID}]No problem! You can start anytime with /onboard[/{GREY_MID}]")


def _build_prompt() -> HTML:
    """Minimal prompt — just a chevron. Context lives in the bottom toolbar."""
    return HTML(f'<style fg="{BLUE}"><b>›</b></style> ')


def _bottom_toolbar() -> HTML:
    """Pinned bottom bar — dark background, subtle info."""
    short_path = get_short_cwd(max_parts=2)
    git = detect_git()
    parts = [f'<style fg="{GREY_MID}">{short_path}</style>']
    if git:
        parts.append(f'<style fg="{GREY_MID}">{git["branch"]}</style>')
    parts.append(f'<style fg="{GREY_DARK}">MemoryChain v0.3.0</style>')
    return HTML("  ".join(parts))


def _handle_slash(line: str, conversation_id: str | None) -> str | None:
    """Dispatch a slash command. Returns conversation_id (possibly unchanged)."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    try:
        if cmd in ("/quit", "/exit"):
            raise _ExitREPL()

        elif cmd == "/help":
            console.print(HELP_TEXT)

        elif cmd == "/today":
            checkins = client.list_checkins(limit=1)
            tasks = client.list_tasks(limit=50)
            goals = client.list_goals(limit=50)
            show_today(checkins, tasks, goals)

        elif cmd == "/review":
            if arg.strip().lower() == "generate":
                today = date.today()
                week_start = today - timedelta(days=today.weekday())
                week_end = week_start + timedelta(days=6)
                console.print(f"[{GREY_MID}]Generating weekly review…[/{GREY_MID}]")
                data = client.generate_review(
                    user_id=USER_ID,
                    week_start=week_start.isoformat(),
                    week_end=week_end.isoformat(),
                )
                show_review(data)
            else:
                reviews = client.list_reviews(limit=1)
                if reviews:
                    show_review(reviews[0])
                else:
                    console.print("[dim]No reviews yet. Try: /review generate[/dim]")

        elif cmd == "/search":
            if not arg:
                console.print("[dim]Usage: /search <query>[/dim]")
            else:
                data = client.search(arg, user_id=USER_ID)
                show_search_results(data, arg)

        elif cmd == "/insights":
            data = client.list_insights()
            show_insights(data)

        elif cmd == "/detect":
            console.print(f"[{GREY_MID}]Running insight detectors…[/{GREY_MID}]")
            new = client.run_detectors(user_id=USER_ID)
            if new:
                console.print(f"[{GREEN}]  ✓ {len(new)} new insight(s) detected.[/{GREEN}]\n")
            else:
                console.print(f"[{GREY_MID}]  No new insights detected.[/{GREY_MID}]\n")
            data = client.list_insights(status="candidate")
            if data:
                show_insights(data)

        elif cmd == "/promote":
            if not arg:
                console.print("[dim]Usage: /promote <insight_id>[/dim]")
            else:
                result = client.promote_insight(arg.strip(), user_id=USER_ID)
                show_success(f"Insight promoted to heuristic {result.get('id', '')[:8]}")

        elif cmd == "/accept":
            if not arg:
                console.print("[dim]Usage: /accept <insight_id>[/dim]")
            else:
                client.change_insight_status(arg.strip(), "active", user_id=USER_ID)
                show_success(f"Insight {arg.strip()[:8]} → active")

        elif cmd == "/reject":
            if not arg:
                console.print("[dim]Usage: /reject <insight_id>[/dim]")
            else:
                client.change_insight_status(arg.strip(), "rejected", user_id=USER_ID)
                show_success(f"Insight {arg.strip()[:8]} rejected")

        elif cmd == "/goals":
            data = client.list_goals()
            show_goals(data)

        elif cmd == "/tasks":
            data = client.list_tasks()
            data = [t for t in data if t.get("status") not in ("completed", "cancelled")]
            show_tasks(data)

        elif cmd == "/heuristics":
            data = client.list_heuristics()
            show_heuristics(data)

        elif cmd == "/status":
            console.print(f"  [{GREY_MID}]API:[/{GREY_MID}]     {API_BASE_URL}")
            try:
                data = client.health()
                console.print(f"  [{GREEN}]●[/{GREEN}] API is {data.get('status', 'unknown')}")
            except Exception:
                console.print(f"  [{RED}]●[/{RED}] Cannot connect to API")
            console.print(f"  [{GREY_MID}]Account:[/{GREY_MID}] {get_account_display()}")
            console.print(f"  [{GREY_MID}]User:[/{GREY_MID}]    {USER_ID}")
            console.print(f"  [{GREY_MID}]Dir:[/{GREY_MID}]     {get_cwd()}")
            git = detect_git()
            if git:
                console.print(f"  [{GREY_MID}]Git:[/{GREY_MID}]     [{GREY_MID}]{git['branch']}[/{GREY_MID}]")
            console.print(f"  [{GREY_MID}]Data:[/{GREY_MID}]    {get_data_dir()}")

        elif cmd == "/clear":
            clear_screen()
            console.print(_build_header())
            console.print()

        elif cmd in ("/checkin", "/onboard"):
            # Route through the chat API as questionnaire commands
            return _handle_chat(line, conversation_id)

        else:
            console.print(f"[dim]Unknown command: {cmd}. Type /help for options.[/dim]")

    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text[:200]}")

    return conversation_id


def _handle_chat(text: str, conversation_id: str | None) -> str | None:
    """Send freeform text to the chat API. Returns updated conversation_id."""
    try:
        with console.status("[dim]thinking…[/dim]", spinner="dots"):
            data = client.post_chat(text, user_id=USER_ID, conversation_id=conversation_id)
        show_chat_response(data)
        return data.get("conversation_id", conversation_id)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        return conversation_id
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text[:200]}")
        return conversation_id


class _ExitREPL(Exception):
    """Raised to cleanly exit the REPL loop."""


def run_repl() -> None:
    """Main interactive loop — full terminal takeover experience."""
    _print_welcome()

    completer = WordCompleter(SLASH_COMMANDS, sentence=True)
    session: PromptSession[str] = PromptSession(
        history=InMemoryHistory(),
        completer=completer,
        complete_while_typing=True,
        bottom_toolbar=_bottom_toolbar,
        style=PT_STYLE,
    )

    conversation_id: str | None = None

    while True:
        try:
            line = session.prompt(_build_prompt())
        except (EOFError, KeyboardInterrupt):
            _exit_gracefully()
            break

        line = line.strip()
        if not line:
            continue

        try:
            if line.startswith("/"):
                conversation_id = _handle_slash(line, conversation_id)
            else:
                conversation_id = _handle_chat(line, conversation_id)
        except _ExitREPL:
            _exit_gracefully()
            break


def _exit_gracefully() -> None:
    """Clean exit: restore terminal title, show farewell."""
    console.print()
    console.print(
        Panel(
            f"[{GREY_MID}]Session ended. Your data is saved in[/{GREY_MID}] "
            f"[{BLUE_BRIGHT}]{get_data_dir()}[/{BLUE_BRIGHT}]",
            border_style=GREY_DARK,
            padding=(0, 1),
        )
    )
    restore_title()
