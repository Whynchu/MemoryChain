from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..storage.repository import Repository


def _day_period(now: datetime) -> str:
    hour = now.hour
    if hour < 6:
        return "late night"
    if hour < 9:
        return "early morning"
    if hour < 12:
        return "morning"
    if hour < 14:
        return "early afternoon"
    if hour < 17:
        return "afternoon"
    if hour < 20:
        return "evening"
    return "night"


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _checkin_streak_days(checkin_dates: list[date], today: date) -> int:
    date_set = set(checkin_dates)
    streak = 0
    cursor = today
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@dataclass
class ContextSnapshot:
    generated_at: datetime
    local_date: date
    day_name: str
    period: str
    has_checkin_today: bool
    last_checkin_date: date | None
    days_since_checkin: int | None
    checkin_streak_days: int
    latest_sleep_hours: float | None
    latest_mood: int | None
    latest_energy: int | None
    recent_sleep_avg: float | None
    recent_mood_avg: float | None
    recent_energy_avg: float | None
    open_task_count: int
    stale_task_count: int
    active_goal_count: int
    candidate_insight_count: int
    active_heuristic_count: int
    unresolved_discrepancy_count: int
    adherence_rate_7d: float | None
    longest_nonresponse_streak_days: int
    profile_onboarded: bool
    active_goal_titles: list[str] = field(default_factory=list)
    open_task_titles: list[str] = field(default_factory=list)
    active_heuristic_rules: list[str] = field(default_factory=list)
    candidate_insight_titles: list[str] = field(default_factory=list)
    recent_discrepancy_ids: list[str] = field(default_factory=list)
    recent_discrepancy_summaries: list[str] = field(default_factory=list)

    @property
    def is_morning_window(self) -> bool:
        return self.period in {"early morning", "morning", "early afternoon"}

    @property
    def likely_low_recovery(self) -> bool:
        latest_sleep_low = self.latest_sleep_hours is not None and self.latest_sleep_hours < 6.5
        latest_energy_low = self.latest_energy is not None and self.latest_energy < 5
        avg_sleep_low = self.recent_sleep_avg is not None and self.recent_sleep_avg < 6.5
        avg_energy_low = self.recent_energy_avg is not None and self.recent_energy_avg < 5.5
        return latest_sleep_low or latest_energy_low or avg_sleep_low or avg_energy_low

    @property
    def likely_low_mood(self) -> bool:
        latest_mood_low = self.latest_mood is not None and self.latest_mood < 5
        avg_mood_low = self.recent_mood_avg is not None and self.recent_mood_avg < 5.5
        return latest_mood_low or avg_mood_low

    @property
    def has_stale_commitment_pressure(self) -> bool:
        return self.stale_task_count > 0

    @property
    def has_pattern_pressure(self) -> bool:
        return self.candidate_insight_count > 0 or self.active_heuristic_count > 0

    @property
    def has_goal_alignment_pressure(self) -> bool:
        return self.unresolved_discrepancy_count > 0

    def to_memory_context(self) -> list[str]:
        context = [
            f"Current time: {self.day_name} {self.generated_at.strftime('%I:%M %p').lstrip('0')} ({self.period})",
        ]
        if self.open_task_titles:
            context.append(f"Open tasks ({self.open_task_count}): {'; '.join(self.open_task_titles[:3])}")
        if self.active_goal_titles:
            context.append(f"Active goals ({self.active_goal_count}): {'; '.join(self.active_goal_titles[:3])}")
        if self.last_checkin_date:
            recent_parts: list[str] = []
            if self.recent_sleep_avg is not None:
                recent_parts.append(f"avg sleep {self.recent_sleep_avg:.1f}h")
            if self.recent_mood_avg is not None:
                recent_parts.append(f"avg mood {self.recent_mood_avg:.1f}/10")
            if self.recent_energy_avg is not None:
                recent_parts.append(f"avg energy {self.recent_energy_avg:.1f}/10")
            if recent_parts:
                context.append(
                    f"Recent check-ins (last date {self.last_checkin_date.isoformat()}): " + ", ".join(recent_parts)
                )
            if not self.has_checkin_today and self.days_since_checkin is not None:
                context.append(f"No check-in today (last was {self.days_since_checkin} day(s) ago)")
        else:
            context.append("No check-ins recorded yet — user is new")

        if self.adherence_rate_7d is not None:
            context.append(
                f"Prompt adherence last 7d: {self.adherence_rate_7d * 100:.0f}%"
            )
        if self.active_heuristic_rules:
            context.append(
                f"Active heuristics ({self.active_heuristic_count}): {'; '.join(self.active_heuristic_rules[:2])}"
            )
        if self.candidate_insight_titles:
            context.append(
                f"Candidate insights ({self.candidate_insight_count}): {'; '.join(self.candidate_insight_titles[:2])}"
            )
        if self.recent_discrepancy_summaries:
            context.append(
                f"Open discrepancies ({self.unresolved_discrepancy_count}): "
                + "; ".join(self.recent_discrepancy_summaries[:2])
            )
        return context


def build_context_snapshot(
    repo: Repository,
    user_id: str,
    *,
    now: datetime | None = None,
) -> ContextSnapshot:
    now = now or datetime.now()
    today = now.date()
    period = _day_period(now)

    open_tasks = repo.list_open_tasks(user_id=user_id, limit=10)
    all_goals = repo.list_goals(user_id=user_id, limit=10)
    active_goals = [goal for goal in all_goals if goal.status == "active"]
    checkins = repo.list_checkins(user_id)
    insights = repo.list_insights(user_id=user_id, status=None, limit=20)
    heuristics = repo.list_heuristics(user_id=user_id, active_only=True, limit=10)
    discrepancies = repo.list_discrepancy_events(user_id=user_id, status="open", limit=10)
    engagement = repo.get_engagement_summary(user_id=user_id, window_days=7, as_of=today)
    profile = repo.get_user_profile(user_id)

    last_checkin_date = checkins[0].date if checkins else None
    has_checkin_today = bool(last_checkin_date == today)
    days_since_checkin = (today - last_checkin_date).days if last_checkin_date else None
    latest_sleep_hours = checkins[0].sleep_hours if checkins else None
    latest_mood = checkins[0].mood if checkins else None
    latest_energy = checkins[0].energy if checkins else None

    recent_checkins = [checkin for checkin in checkins[:7] if checkin.date]
    recent_sleep_avg = _average([c.sleep_hours for c in recent_checkins if c.sleep_hours is not None])
    recent_mood_avg = _average([float(c.mood) for c in recent_checkins if c.mood is not None])
    recent_energy_avg = _average([float(c.energy) for c in recent_checkins if c.energy is not None])

    open_task_count = len(open_tasks)
    stale_task_count = sum(
        1 for task in open_tasks if (today - task.created_at.date()).days >= 7
    )
    active_goal_count = len(active_goals)
    candidate_insight_count = sum(1 for insight in insights if insight.status == "candidate")
    active_heuristic_count = len(heuristics)
    unresolved_discrepancy_count = len(discrepancies)

    return ContextSnapshot(
        generated_at=now,
        local_date=today,
        day_name=now.strftime("%A"),
        period=period,
        has_checkin_today=has_checkin_today,
        last_checkin_date=last_checkin_date,
        days_since_checkin=days_since_checkin,
        checkin_streak_days=_checkin_streak_days([c.date for c in checkins], today),
        latest_sleep_hours=latest_sleep_hours,
        latest_mood=latest_mood,
        latest_energy=latest_energy,
        recent_sleep_avg=recent_sleep_avg,
        recent_mood_avg=recent_mood_avg,
        recent_energy_avg=recent_energy_avg,
        open_task_count=open_task_count,
        stale_task_count=stale_task_count,
        active_goal_count=active_goal_count,
        candidate_insight_count=candidate_insight_count,
        active_heuristic_count=active_heuristic_count,
        unresolved_discrepancy_count=unresolved_discrepancy_count,
        adherence_rate_7d=engagement.adherence_rate,
        longest_nonresponse_streak_days=engagement.longest_nonresponse_streak_days,
        profile_onboarded=bool(profile and profile.onboarded_at),
        active_goal_titles=[goal.title for goal in active_goals],
        open_task_titles=[task.title for task in open_tasks],
        active_heuristic_rules=[heuristic.rule for heuristic in heuristics],
        candidate_insight_titles=[
            getattr(insight, "title", "Candidate pattern")
            for insight in insights
            if insight.status == "candidate"
        ],
        recent_discrepancy_ids=[event.id for event in discrepancies],
        recent_discrepancy_summaries=[event.summary for event in discrepancies],
    )
