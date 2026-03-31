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

    window_days = max((week_end - week_start).days + 1, 1)
    engagement = repo.get_engagement_summary(user_id=user_id, window_days=window_days, as_of=week_end)

    wins = [f"Completed task: {task.title}" for task in completed_tasks[:3]]
    if mood_scores:
        wins.append(f"Tracked mood on {len(mood_scores)} day(s)")
    if engagement.adherence_rate is not None and engagement.adherence_rate >= 0.7:
        wins.append(
            f"Prompt adherence was {engagement.adherence_rate * 100:.0f}% across {engagement.total_cycles} cycle(s)"
        )

    slips = []
    if not checkins:
        slips.append("No structured check-ins recorded this week")
    if not completed_tasks:
        slips.append("No tasks were marked done this week")
    if engagement.missed_cycles > 0:
        slips.append(f"Missed {engagement.missed_cycles} prompt cycle(s)")
    if engagement.longest_nonresponse_streak_days >= 2:
        slips.append(
            f"Longest non-response streak reached {engagement.longest_nonresponse_streak_days} day(s)"
        )

    open_loops = [task.title for task in open_tasks[:5]]

    next_actions: list[str] = []
    if open_tasks:
        next_actions.append("Close one oldest open task before creating new tasks")
    if not checkins:
        next_actions.append("Log a daily check-in for at least 3 days this week")
    if avg_mood is not None and avg_mood < 5:
        next_actions.append("Add one low-effort recovery activity on low-mood days")
    if engagement.adherence_rate is not None and engagement.adherence_rate < 0.6:
        next_actions.append("Use shorter prompt check-ins next week to improve response consistency")

    summary_parts = [
        f"Weekly review for {week_start.isoformat()} to {week_end.isoformat()}.",
        f"Captured {len(journal_entries)} journal entr{'y' if len(journal_entries) == 1 else 'ies'} and {len(checkins)} check-in(s).",
        f"Completed {len(completed_tasks)} task(s); {len(open_tasks)} remain open.",
    ]
    if avg_mood is not None:
        summary_parts.append(f"Average mood score was {avg_mood:.1f}/10.")
    if engagement.total_cycles > 0:
        adherence = (engagement.adherence_rate or 0.0) * 100
        summary_parts.append(
            f"Prompt adherence: {adherence:.0f}% ({engagement.responded_cycles}/{engagement.total_cycles}), "
            f"missed: {engagement.missed_cycles}, longest gap: {engagement.longest_nonresponse_streak_days} day(s)."
        )

    engagement_notes: list[str] = []
    if engagement.total_cycles > 0:
        adherence = (engagement.adherence_rate or 0.0) * 100
        engagement_notes.append(
            f"Prompt adherence {adherence:.0f}% ({engagement.responded_cycles}/{engagement.total_cycles})"
        )
        engagement_notes.append(f"Missed cycles: {engagement.missed_cycles}")
        engagement_notes.append(
            f"Longest non-response streak: {engagement.longest_nonresponse_streak_days} day(s)"
        )
        if engagement.streak_resume_count > 0:
            engagement_notes.append(f"Streak resumptions: {engagement.streak_resume_count}")

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
        engagement_notes=engagement_notes,
        source_ids=source_ids,
        confidence=confidence,
    )
