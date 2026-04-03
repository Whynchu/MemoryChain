"""
MemoryChain CLI — daily logging, review, and insight management from the terminal.

Usage:
    memorychain log "Had a great morning run, slept 7 hours, mood is 8/10"
    memorychain today
    memorychain search "running"
    memorychain review
    memorychain insights
    memorychain promote <id>
    memorychain goals
    memorychain tasks
"""

from __future__ import annotations

import click
import httpx

from . import client
from .config import USER_ID
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


@click.group()
@click.version_option("0.1.0", prog_name="memorychain")
def cli() -> None:
    """MemoryChain — personal memory and execution backend."""


# ── log ──────────────────────────────────────────────────────
@cli.command()
@click.argument("message", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def log(message: tuple[str, ...], yes: bool) -> None:
    """Send freeform text to MemoryChain for extraction and storage."""
    text = " ".join(message)
    try:
        data = client.post_chat(text, user_id=USER_ID)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)

    show_chat_response(data)

    # Confirmation flow — show what was extracted
    extraction = data.get("extraction", {})
    has_extractions = (
        extraction.get("journal_entry_id")
        or extraction.get("checkin_id")
        or extraction.get("task_ids")
        or extraction.get("goal_ids")
        or extraction.get("activity_ids")
        or extraction.get("metric_ids")
    ) if extraction else False

    if has_extractions and not yes:
        if not click.confirm("Keep these extractions?", default=True):
            console.print("[dim]  Extractions discarded (already stored by API).[/dim]")
            console.print("[dim]  Use the audit log to rollback if needed.[/dim]")


# ── today ────────────────────────────────────────────────────
@cli.command()
def today() -> None:
    """Show today's check-in, open tasks, and active goals."""
    try:
        checkins = client.list_checkins(limit=1)
        tasks = client.list_tasks(limit=50)
        goals = client.list_goals(limit=50)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}")
        raise SystemExit(1)

    show_today(checkins, tasks, goals)


# ── search ───────────────────────────────────────────────────
@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=20, help="Max results (default: 20)")
def search(query: str, limit: int) -> None:
    """Search across all MemoryChain objects."""
    try:
        results = client.search(query, user_id=USER_ID, limit=limit)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}")
        raise SystemExit(1)

    show_search_results(results, query)


# ── review ───────────────────────────────────────────────────
@cli.command()
@click.option("--generate", "-g", is_flag=True, help="Generate a new review for this week")
def review(generate: bool) -> None:
    """Show or generate weekly review."""
    from datetime import date, timedelta
    try:
        if generate:
            today = date.today()
            # Find the Monday of this week
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            console.print(f"[dim]Generating review for {week_start} → {week_end}…[/dim]")
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
                console.print("[dim]No reviews yet. Run with --generate to create one.[/dim]")
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)


# ── insights ─────────────────────────────────────────────────
@cli.command()
@click.option("--status", "-s", type=click.Choice(["candidate", "active", "rejected", "archived", "promoted"]), help="Filter by status")
@click.option("--detect", is_flag=True, help="Run detectors first to discover new insights")
def insights(status: str | None, detect: bool) -> None:
    """List insights, optionally running detectors first."""
    try:
        if detect:
            console.print("[dim]Running insight detectors…[/dim]")
            new = client.run_detectors(user_id=USER_ID)
            if new:
                console.print(f"[green]  ✓ {len(new)} new insight(s) detected.[/green]")
            else:
                console.print("[dim]  No new insights detected.[/dim]")
            console.print()

        data = client.list_insights(status=status)
        show_insights(data)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)


# ── promote ──────────────────────────────────────────────────
@cli.command()
@click.argument("insight_id")
def promote(insight_id: str) -> None:
    """Promote an active insight to a heuristic."""
    try:
        result = client.promote_insight(insight_id, user_id=USER_ID)
        show_success(f"Insight {insight_id[:8]} promoted to heuristic {result.get('id', '')[:8]}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            show_error(f"Cannot promote: {exc.response.json().get('detail', 'conflict')}")
        elif exc.response.status_code == 404:
            show_error(f"Insight {insight_id} not found")
        else:
            show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)


# ── reject ───────────────────────────────────────────────────
@cli.command()
@click.argument("insight_id")
def reject(insight_id: str) -> None:
    """Reject a candidate or active insight."""
    try:
        client.change_insight_status(insight_id, "rejected", user_id=USER_ID)
        show_success(f"Insight {insight_id[:8]} rejected.")
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)


# ── accept ───────────────────────────────────────────────────
@cli.command()
@click.argument("insight_id")
def accept(insight_id: str) -> None:
    """Accept a candidate insight (move to active)."""
    try:
        client.change_insight_status(insight_id, "active", user_id=USER_ID)
        show_success(f"Insight {insight_id[:8]} accepted → active.")
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}: {exc.response.text}")
        raise SystemExit(1)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)


# ── goals ────────────────────────────────────────────────────
@cli.command()
def goals() -> None:
    """List all goals."""
    try:
        data = client.list_goals()
        show_goals(data)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}")
        raise SystemExit(1)


# ── tasks ────────────────────────────────────────────────────
@cli.command()
@click.option("--all", "show_all", is_flag=True, help="Include completed/cancelled tasks")
def tasks(show_all: bool) -> None:
    """List tasks (open by default)."""
    try:
        data = client.list_tasks()
        if not show_all:
            data = [t for t in data if t.get("status") not in ("completed", "cancelled")]
        show_tasks(data)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}")
        raise SystemExit(1)


# ── heuristics ───────────────────────────────────────────────
@cli.command()
def heuristics() -> None:
    """List learned heuristics (promoted insights + user-defined rules)."""
    try:
        data = client.list_heuristics()
        show_heuristics(data)
    except httpx.ConnectError:
        show_error("Cannot connect to MemoryChain API. Is it running?")
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        show_error(f"API returned {exc.response.status_code}")
        raise SystemExit(1)


# ── status ───────────────────────────────────────────────────
@cli.command()
def status() -> None:
    """Check API health and show connection info."""
    from .config import API_BASE_URL

    console.print(f"[dim]API:[/dim] {API_BASE_URL}")
    try:
        data = client.health()
        console.print(f"[green]✓[/green] API is {data.get('status', 'unknown')}")
    except httpx.ConnectError:
        console.print("[red]✗[/red] Cannot connect to API")
        raise SystemExit(1)
    except Exception as exc:
        console.print(f"[red]✗[/red] Error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
