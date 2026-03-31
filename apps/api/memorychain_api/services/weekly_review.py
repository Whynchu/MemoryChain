from __future__ import annotations

from datetime import date

from ..schemas import WeeklyReview
from ..storage.repository import Repository


def generate_weekly_review(
    repo: Repository,
    *,
    user_id: str,
    week_start: date,
    week_end: date,
) -> WeeklyReview:
    journal_entries, checkins, tasks = repo.get_records_for_week(user_id, week_start, week_end)

    completed_tasks = [task for task in tasks if task.status == "done" and task.completed_at]
    open_tasks = [task for task in tasks if task.status in ("todo", "in_progress")]

    mood_scores = [c.mood for c in checkins if c.mood is not None]
    avg_mood = (sum(mood_scores) / len(mood_scores)) if mood_scores else None

    wins = [f"Completed task: {task.title}" for task in completed_tasks[:3]]
    if mood_scores:
        wins.append(f"Tracked mood on {len(mood_scores)} day(s)")

    slips = []
    if not checkins:
        slips.append("No structured check-ins recorded this week")
    if not completed_tasks:
        slips.append("No tasks were marked done this week")

    open_loops = [task.title for task in open_tasks[:5]]

    next_actions: list[str] = []
    if open_tasks:
        next_actions.append("Close one oldest open task before creating new tasks")
    if not checkins:
        next_actions.append("Log a daily check-in for at least 3 days this week")
    if avg_mood is not None and avg_mood < 5:
        next_actions.append("Add one low-effort recovery activity on low-mood days")

    summary_parts = [
        f"Weekly review for {week_start.isoformat()} to {week_end.isoformat()}.",
        f"Captured {len(journal_entries)} journal entr{'y' if len(journal_entries) == 1 else 'ies'} and {len(checkins)} check-in(s).",
        f"Completed {len(completed_tasks)} task(s); {len(open_tasks)} remain open.",
    ]
    if avg_mood is not None:
        summary_parts.append(f"Average mood score was {avg_mood:.1f}/10.")

    source_ids = [entry.id for entry in journal_entries] + [checkin.id for checkin in checkins]
    confidence = 0.7 if source_ids else 0.3

    return repo.create_weekly_review(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
        summary=" ".join(summary_parts),
        wins=wins,
        slips=slips,
        open_loops=open_loops,
        recommended_next_actions=next_actions,
        source_ids=source_ids,
        confidence=confidence,
    )
