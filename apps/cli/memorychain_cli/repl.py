"""Interactive REPL — the default experience when you run `memorychain`."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

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

# Slash commands the completer knows about
SLASH_COMMANDS = [
    "/today", "/review", "/search", "/insights", "/detect",
    "/promote", "/accept", "/reject", "/goals", "/tasks",
    "/heuristics", "/status", "/help", "/quit", "/exit",
]

HELP_TEXT = """\
[bold cyan]MemoryChain[/bold cyan] — interactive mode

[bold]Just type naturally[/bold] to log entries, ask questions, or chat.
  e.g. "Slept 7h, mood 8/10. Morning run 5k."
  e.g. "How has my sleep been this week?"

[bold]Slash commands:[/bold]
  [green]/today[/green]            Today's checkin, tasks, goals
  [green]/review[/green]           Show latest weekly review
  [green]/review generate[/green]  Generate a new weekly review
  [green]/search[/green] <query>   Search across all objects
  [green]/insights[/green]         List insight candidates
  [green]/detect[/green]           Run insight detectors
  [green]/promote[/green] <id>     Promote insight → heuristic
  [green]/accept[/green] <id>      Accept candidate → active
  [green]/reject[/green] <id>      Reject an insight
  [green]/goals[/green]            List active goals
  [green]/tasks[/green]            List open tasks
  [green]/heuristics[/green]       List learned heuristics
  [green]/status[/green]           Check API connection
  [green]/help[/green]             Show this help
  [green]/quit[/green]             Exit

"""


def _welcome_banner() -> None:
    """Print a welcome banner with connection status."""
    banner = Text()
    banner.append("MemoryChain", style="bold cyan")
    banner.append(" v0.2.0\n", style="dim")
    banner.append("Type naturally to log • slash commands for actions • /help for more\n", style="dim")

    try:
        client.health()
        banner.append(f"Connected to {API_BASE_URL}", style="green")
    except Exception:
        banner.append(f"⚠ Cannot reach API at {API_BASE_URL}", style="bold red")

    console.print()
    console.print(Panel(banner, border_style="cyan", padding=(0, 2)))
    console.print()


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
                console.print("[dim]Generating weekly review…[/dim]")
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
            console.print("[dim]Running insight detectors…[/dim]")
            new = client.run_detectors(user_id=USER_ID)
            if new:
                console.print(f"[green]  ✓ {len(new)} new insight(s) detected.[/green]\n")
            else:
                console.print("[dim]  No new insights detected.[/dim]\n")
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
            console.print(f"[dim]API:[/dim] {API_BASE_URL}")
            data = client.health()
            console.print(f"[green]✓[/green] API is {data.get('status', 'unknown')}")
            console.print(f"[dim]User:[/dim] {USER_ID}")

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
    """Main interactive loop."""
    _welcome_banner()

    completer = WordCompleter(SLASH_COMMANDS, sentence=True)
    session: PromptSession[str] = PromptSession(
        history=InMemoryHistory(),
        completer=completer,
        complete_while_typing=True,
    )

    conversation_id: str | None = None

    while True:
        try:
            line = session.prompt(
                HTML("<ansigreen><b>memorychain</b></ansigreen> <ansigray>›</ansigray> "),
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
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
            console.print("[dim]Goodbye.[/dim]")
            break
