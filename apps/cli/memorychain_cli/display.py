"""Rich display helpers for MemoryChain CLI output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .theme import RICH_THEME, BLUE, BLUE_BRIGHT, GREY_MID, GREEN, RED, YELLOW

console = Console(theme=RICH_THEME)
err_console = Console(stderr=True, theme=RICH_THEME)


# ── Utilities ────────────────────────────────────────────────
def _short_id(uid: str) -> str:
    """Show first 8 chars of a UUID for readability."""
    return uid[:8] if uid and len(uid) >= 8 else uid or "—"


def _trunc(text: str | None, length: int = 80) -> str:
    if not text:
        return "—"
    return text[:length] + "…" if len(text) > length else text


def _date_fmt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso[:16] if len(iso) >= 16 else iso


def status_badge(status: str) -> Text:
    colors = {
        "active": GREEN,
        "candidate": YELLOW,
        "rejected": RED,
        "archived": "dim",
        "promoted": f"bold {BLUE_BRIGHT}",
        "completed": GREEN,
        "in_progress": YELLOW,
        "not_started": "dim",
        "open": YELLOW,
        "closed": "dim",
    }
    color = colors.get(status, "white")
    return Text(status, style=color)


# ── Chat / Log ───────────────────────────────────────────────
def show_chat_response(data: dict[str, Any]) -> None:
    reply = data.get("assistant_message", "")
    extraction = data.get("extraction", {})

    has_data = bool(extraction) and (
        extraction.get("source_document_id")
        or extraction.get("journal_entry_id")
        or extraction.get("checkin_id")
        or extraction.get("task_ids")
        or extraction.get("goal_ids")
        or extraction.get("activity_ids")
        or extraction.get("metric_ids")
    )

    console.print()
    if has_data:
        # Log response — bordered panel + extraction details
        console.print(Panel(reply, border_style=BLUE, padding=(1, 2)))
        console.print()
        _extraction_line("Source Document", extraction.get("source_document_id"))
        _extraction_line("Journal Entry", extraction.get("journal_entry_id"))
        _extraction_line("Check-in", extraction.get("checkin_id"))
        _extraction_list("Tasks", extraction.get("task_ids", []))
        _extraction_list("Goals", extraction.get("goal_ids", []))
        _extraction_list("Activities", extraction.get("activity_ids", []))
        _extraction_list("Metrics", extraction.get("metric_ids", []))
    else:
        # Chat/query response — just text, no box
        console.print(f"  [{BLUE_BRIGHT}]›[/{BLUE_BRIGHT}] {reply}")
    console.print()


def _extraction_line(label: str, obj_id: str | None) -> None:
    if obj_id:
        console.print(f"  [{BLUE_BRIGHT}]✓[/{BLUE_BRIGHT}] [{GREY_MID}]{label}:[/{GREY_MID}] {_short_id(obj_id)}")


def _extraction_list(label: str, ids: list[str]) -> None:
    if ids:
        console.print(f"  [{BLUE_BRIGHT}]✓[/{BLUE_BRIGHT}] [{GREY_MID}]{len(ids)} {label}:[/{GREY_MID}] {', '.join(_short_id(i) for i in ids)}")


# ── Today ────────────────────────────────────────────────────
def show_today(checkins: list, tasks: list, goals: list) -> None:
    console.print()

    # Checkin panel
    if checkins:
        ci = checkins[0]
        mood = ci.get("mood_score", "—")
        sleep = ci.get("sleep_hours", "—")
        energy = ci.get("energy_level", "—")
        notes = ci.get("notes", "")
        ci_text = (
            f"[bold]Mood:[/bold] {mood}/10  "
            f"[bold]Sleep:[/bold] {sleep}h  "
            f"[bold]Energy:[/bold] {energy}/10\n"
        )
        if notes:
            ci_text += f"\n{_trunc(notes, 200)}"
        console.print(Panel(ci_text, title=f"[{BLUE_BRIGHT}]📋 Today's Check-in[/{BLUE_BRIGHT}]", border_style=BLUE))
    else:
        console.print(Panel(f"[{GREY_MID}]No check-in recorded today.[/{GREY_MID}]", title=f"[{GREY_MID}]📋 Today's Check-in[/{GREY_MID}]", border_style=GREY_MID))

    # Tasks
    open_tasks = [t for t in tasks if t.get("status") not in ("completed", "cancelled")]
    if open_tasks:
        table = Table(title="📌 Open Tasks", show_lines=False, pad_edge=False)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", min_width=30)
        table.add_column("Status", width=12)
        table.add_column("Due", width=12)
        for t in open_tasks[:10]:
            table.add_row(
                _short_id(t["id"]),
                _trunc(t.get("title", ""), 50),
                status_badge(t.get("status", "open")),
                _date_fmt(t.get("due_date")),
            )
        console.print(table)
    else:
        console.print("[dim]  No open tasks.[/dim]")

    # Goals
    active_goals = [g for g in goals if g.get("status") == "active"]
    if active_goals:
        table = Table(title="🎯 Active Goals", show_lines=False, pad_edge=False)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", min_width=30)
        table.add_column("Target", width=14)
        for g in active_goals[:10]:
            table.add_row(
                _short_id(g["id"]),
                _trunc(g.get("title", ""), 50),
                _date_fmt(g.get("target_date")),
            )
        console.print(table)
    else:
        console.print("[dim]  No active goals.[/dim]")

    console.print()


# ── Search ───────────────────────────────────────────────────
def show_search_results(data: dict[str, Any], query: str) -> None:
    results = data.get("results", []) if isinstance(data, dict) else data
    console.print()
    if not results:
        console.print(f"[dim]No results for '{query}'.[/dim]")
        console.print()
        return

    console.print(f"[bold]{len(results)} result(s)[/bold] for [{BLUE_BRIGHT}]'{query}'[/{BLUE_BRIGHT}]\n")
    for r in results:
        obj_type = r.get("object_type", "unknown")
        title = r.get("title") or r.get("snippet", "—")
        created = _date_fmt(r.get("effective_at"))
        tags = r.get("tags", [])
        tag_str = f"  [dim]{', '.join(tags)}[/dim]" if tags else ""
        console.print(f"  [bold]{obj_type}[/bold] {_trunc(title, 60)}{tag_str}  [dim]{created}[/dim]")
    console.print()


# ── Weekly Review ────────────────────────────────────────────
def show_review(review: dict[str, Any]) -> None:
    console.print()
    week = review.get("week_label", "")
    summary = review.get("summary", "No summary available.")
    narrative = review.get("llm_narrative", "")

    console.print(Panel(summary, title=f"[{BLUE_BRIGHT}]📊 Weekly Review — {week}[/{BLUE_BRIGHT}]", border_style=BLUE))

    # Wins & Slips
    wins = review.get("wins", [])
    if wins:
        console.print("\n[bold green]🏆 Wins[/bold green]")
        for w in wins:
            console.print(f"  • {w}")

    slips = review.get("slips", [])
    if slips:
        console.print("\n[bold yellow]⚠ Slips[/bold yellow]")
        for s in slips:
            console.print(f"  • {s}")

    # Open loops
    loops = review.get("open_loops", [])
    if loops:
        console.print("\n[bold]🔄 Open Loops[/bold]")
        for l in loops:
            console.print(f"  • {l}")

    # Insight mentions
    mentions = review.get("insight_mentions", [])
    if mentions:
        console.print("\n[bold]💡 Insight Mentions[/bold]")
        for m in mentions:
            console.print(f"  • {m}")

    # Activity summary
    activities = review.get("activity_summary", [])
    if activities:
        console.print("\n[bold]🏃 Activities[/bold]")
        for a in activities:
            console.print(f"  • {a}")

    # Metric highlights
    highlights = review.get("metric_highlights", [])
    if highlights:
        console.print("\n[bold]📈 Metrics[/bold]")
        for h in highlights:
            console.print(f"  • {h}")

    # Sparse data flags
    sparse = review.get("sparse_data_flags", [])
    if sparse:
        console.print("\n[bold yellow]⚠ Sparse Data[/bold yellow]")
        for flag in sparse:
            console.print(f"  • {flag}")

    # Notable entries
    notable = review.get("notable_entries", [])
    if notable:
        console.print("\n[bold]📝 Notable Entries[/bold]")
        for n in notable:
            console.print(f"  • {n}")

    # Recommended next actions
    actions = review.get("recommended_next_actions", [])
    if actions:
        console.print("\n[bold]➡ Recommended Actions[/bold]")
        for a in actions:
            console.print(f"  • {a}")

    # LLM narrative
    if narrative:
        console.print()
        console.print(Panel(narrative, title=f"[{BLUE_BRIGHT}]🤖 AI Narrative[/{BLUE_BRIGHT}]", border_style=BLUE))

    console.print()


# ── Insights ─────────────────────────────────────────────────
def show_insights(insights: list[dict[str, Any]]) -> None:
    console.print()
    if not insights:
        console.print("[dim]No insights found.[/dim]\n")
        return

    table = Table(title="💡 Insights", show_lines=False)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Confidence", width=10, justify="right")
    table.add_column("Evidence", width=8, justify="right")
    table.add_column("Created", width=12)

    for ins in insights:
        conf = ins.get("confidence")
        conf_str = f"{conf:.2f}" if conf is not None else "—"
        ev_count = len(ins.get("evidence_ids", []))
        table.add_row(
            _short_id(ins["id"]),
            _trunc(ins.get("title", ""), 50),
            status_badge(ins.get("status", "candidate")),
            conf_str,
            str(ev_count),
            _date_fmt(ins.get("created_at")),
        )
    console.print(table)
    console.print()


# ── Goals ────────────────────────────────────────────────────
def show_goals(goals: list[dict[str, Any]]) -> None:
    console.print()
    if not goals:
        console.print("[dim]No goals found.[/dim]\n")
        return

    table = Table(title="🎯 Goals", show_lines=False)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Target", width=12)

    for g in goals:
        table.add_row(
            _short_id(g["id"]),
            _trunc(g.get("title", ""), 50),
            status_badge(g.get("status", "active")),
            _date_fmt(g.get("target_date")),
        )
    console.print(table)
    console.print()


# ── Tasks ────────────────────────────────────────────────────
def show_tasks(tasks: list[dict[str, Any]]) -> None:
    console.print()
    if not tasks:
        console.print("[dim]No tasks found.[/dim]\n")
        return

    table = Table(title="📌 Tasks", show_lines=False)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Priority", width=8)
    table.add_column("Due", width=12)

    for t in tasks:
        table.add_row(
            _short_id(t["id"]),
            _trunc(t.get("title", ""), 50),
            status_badge(t.get("status", "open")),
            t.get("priority", "—"),
            _date_fmt(t.get("due_date")),
        )
    console.print(table)
    console.print()


# ── Heuristics ───────────────────────────────────────────────
def show_heuristics(heuristics: list[dict[str, Any]]) -> None:
    console.print()
    if not heuristics:
        console.print("[dim]No heuristics found.[/dim]\n")
        return

    table = Table(title="🧠 Heuristics", show_lines=False)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Rule", min_width=30)
    table.add_column("Type", width=16)
    table.add_column("Active", width=6)

    for h in heuristics:
        table.add_row(
            _short_id(h["id"]),
            _trunc(h.get("rule_text", ""), 60),
            h.get("source_type", "—"),
            "✓" if h.get("is_active") else "✗",
        )
    console.print(table)
    console.print()


# ── Error ────────────────────────────────────────────────────
def show_error(message: str) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def show_success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")
