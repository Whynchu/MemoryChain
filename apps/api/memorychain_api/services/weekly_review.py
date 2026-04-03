from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta

from ..config import settings
from ..schemas import WeeklyReview
from ..storage.repository import Repository

logger = logging.getLogger(__name__)


def _build_insight_mentions(repo: Repository, user_id: str, week_start: date, week_end: date) -> list[str]:
    insights = repo.get_insights_for_week(user_id, week_start, week_end)
    mentions: list[str] = []
    for ins in insights:
        label = ins.status.capitalize()
        conf = f" (confidence {ins.confidence:.0%})" if ins.confidence else ""
        mentions.append(f"[{label}] {ins.title}{conf}")
    return mentions


def _build_activity_summary(repo: Repository, user_id: str, week_start: date, week_end: date) -> list[str]:
    activities = repo.get_activities_for_week(user_id, week_start, week_end)
    if not activities:
        return []
    type_counts: Counter[str] = Counter()
    for a in activities:
        type_counts[a.activity_type] += 1
    lines = [f"{count}× {atype}" for atype, count in type_counts.most_common()]
    return [f"{len(activities)} activit{'y' if len(activities) == 1 else 'ies'} logged: {', '.join(lines)}"]


def _build_metric_highlights(repo: Repository, user_id: str, week_start: date, week_end: date) -> list[str]:
    metrics = repo.get_metrics_for_week(user_id, week_start, week_end)
    if not metrics:
        return []
    by_type: dict[str, list[float]] = {}
    for m in metrics:
        try:
            val = float(m.value)
        except (ValueError, TypeError):
            continue
        by_type.setdefault(m.metric_type, []).append(val)

    highlights: list[str] = []
    for mtype, vals in sorted(by_type.items()):
        if len(vals) == 1:
            highlights.append(f"{mtype}: {vals[0]:.1f}" + (f" {metrics[0].unit}" if metrics[0].unit else ""))
        else:
            avg = sum(vals) / len(vals)
            lo, hi = min(vals), max(vals)
            highlights.append(f"{mtype}: avg {avg:.1f}, range {lo:.1f}–{hi:.1f} ({len(vals)} readings)")
    return highlights


def _build_sparse_data_flags(checkins_dates: set[date], week_start: date, week_end: date) -> list[str]:
    flags: list[str] = []
    d = week_start
    missing: list[str] = []
    while d <= week_end:
        if d not in checkins_dates:
            missing.append(d.strftime("%A %b %d"))
        d += timedelta(days=1)
    if missing:
        flags.append(f"No check-in on: {', '.join(missing)}")
    return flags


def _build_notable_entries(journal_entries: list, checkins: list) -> list[str]:
    """Extract date-referenced notable entries for the review."""
    notable: list[str] = []
    for entry in journal_entries[:5]:
        day = entry.effective_at.strftime("%b %d")
        text = entry.text[:120].rstrip()
        if len(entry.text) > 120:
            text += "…"
        notable.append(f"On {day}: {text}")
    return notable


def _generate_llm_narrative(
    *,
    summary: str,
    wins: list[str],
    slips: list[str],
    insight_mentions: list[str],
    activity_summary: list[str],
    metric_highlights: list[str],
    notable_entries: list[str],
) -> str | None:
    """Generate an LLM-written narrative from structured review data. Returns None if LLM unavailable."""
    if settings.llm_provider != "openai" or not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    facts_block = f"Summary: {summary}\n"
    if wins:
        facts_block += "Wins:\n" + "\n".join(f"- {w}" for w in wins) + "\n"
    if slips:
        facts_block += "Slips:\n" + "\n".join(f"- {s}" for s in slips) + "\n"
    if insight_mentions:
        facts_block += "Insights:\n" + "\n".join(f"- {i}" for i in insight_mentions) + "\n"
    if activity_summary:
        facts_block += "Activities:\n" + "\n".join(f"- {a}" for a in activity_summary) + "\n"
    if metric_highlights:
        facts_block += "Metrics:\n" + "\n".join(f"- {m}" for m in metric_highlights) + "\n"
    if notable_entries:
        facts_block += "Notable entries:\n" + "\n".join(f"- {n}" for n in notable_entries) + "\n"

    system_prompt = (
        "You are MemoryChain, writing a concise weekly review narrative for the user. "
        "Be warm but direct. Use second person ('you'). "
        "Only make claims supported by the data provided — never invent events or metrics. "
        "Keep it to 3-5 short paragraphs. Highlight patterns and actionable takeaways."
    )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Write a weekly review narrative from these facts:\n\n{facts_block}"},
            ],
            temperature=0.5,
            max_tokens=600,
        )
        return completion.choices[0].message.content or None
    except Exception:
        logger.warning("LLM narrative generation failed, falling back to structured summary", exc_info=True)
        return None


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

    sleep_values = [c.sleep_hours for c in checkins if c.sleep_hours is not None]
    avg_sleep = (sum(sleep_values) / len(sleep_values)) if sleep_values else None

    window_days = max((week_end - week_start).days + 1, 1)
    engagement = repo.get_engagement_summary(user_id=user_id, window_days=window_days, as_of=week_end)

    # --- Wins ---
    wins = [f"Completed task: {task.title}" for task in completed_tasks[:3]]
    if mood_scores:
        wins.append(f"Tracked mood on {len(mood_scores)} day(s)")
    if engagement.adherence_rate is not None and engagement.adherence_rate >= 0.7:
        wins.append(
            f"Prompt adherence was {engagement.adherence_rate * 100:.0f}% across {engagement.total_cycles} cycle(s)"
        )

    # --- Slips ---
    slips: list[str] = []
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

    # --- Next actions ---
    next_actions: list[str] = []
    if open_tasks:
        next_actions.append("Close one oldest open task before creating new tasks")
    if not checkins:
        next_actions.append("Log a daily check-in for at least 3 days this week")
    if avg_mood is not None and avg_mood < 5:
        next_actions.append("Add one low-effort recovery activity on low-mood days")
    if engagement.adherence_rate is not None and engagement.adherence_rate < 0.6:
        next_actions.append("Use shorter prompt check-ins next week to improve response consistency")

    # --- Summary text ---
    summary_parts = [
        f"Weekly review for {week_start.isoformat()} to {week_end.isoformat()}.",
        f"Captured {len(journal_entries)} journal entr{'y' if len(journal_entries) == 1 else 'ies'} and {len(checkins)} check-in(s).",
        f"Completed {len(completed_tasks)} task(s); {len(open_tasks)} remain open.",
    ]
    if avg_mood is not None:
        summary_parts.append(f"Average mood score was {avg_mood:.1f}/10.")
    if avg_sleep is not None:
        summary_parts.append(f"Average sleep was {avg_sleep:.1f}h.")
    if engagement.total_cycles > 0:
        adherence = (engagement.adherence_rate or 0.0) * 100
        summary_parts.append(
            f"Prompt adherence: {adherence:.0f}% ({engagement.responded_cycles}/{engagement.total_cycles}), "
            f"missed: {engagement.missed_cycles}, longest gap: {engagement.longest_nonresponse_streak_days} day(s)."
        )

    # --- Engagement notes ---
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

    # --- Phase 3 enrichments ---
    insight_mentions = _build_insight_mentions(repo, user_id, week_start, week_end)
    activity_summary = _build_activity_summary(repo, user_id, week_start, week_end)
    metric_highlights = _build_metric_highlights(repo, user_id, week_start, week_end)

    checkin_dates = {c.date for c in checkins}
    sparse_data_flags = _build_sparse_data_flags(checkin_dates, week_start, week_end)

    notable_entries = _build_notable_entries(journal_entries, checkins)

    # --- Optional LLM narrative ---
    summary_text = " ".join(summary_parts)
    llm_narrative = _generate_llm_narrative(
        summary=summary_text,
        wins=wins,
        slips=slips,
        insight_mentions=insight_mentions,
        activity_summary=activity_summary,
        metric_highlights=metric_highlights,
        notable_entries=notable_entries,
    )

    source_ids = [entry.id for entry in journal_entries] + [checkin.id for checkin in checkins]
    confidence = 0.7 if source_ids else 0.3

    return repo.create_weekly_review(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
        summary=summary_text,
        wins=wins,
        slips=slips,
        open_loops=open_loops,
        recommended_next_actions=next_actions,
        engagement_notes=engagement_notes,
        insight_mentions=insight_mentions,
        activity_summary=activity_summary,
        metric_highlights=metric_highlights,
        sparse_data_flags=sparse_data_flags,
        notable_entries=notable_entries,
        llm_narrative=llm_narrative,
        source_ids=source_ids,
        confidence=confidence,
    )
