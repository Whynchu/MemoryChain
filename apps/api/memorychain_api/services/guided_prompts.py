from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..schemas import GuidedPrompt, GuidedPromptsResponse
from ..storage.repository import Repository


def get_guided_prompts(repo: Repository, *, user_id: str) -> GuidedPromptsResponse:
    today = datetime.now(timezone.utc).date()
    seven_days_ago = today - timedelta(days=7)

    open_tasks = repo.search(
        user_id=user_id,
        object_types=["task"],
        limit=5,
    )
    open_tasks = [item for item in open_tasks if item.snippet.startswith("[todo]") or item.snippet.startswith("[in_progress]")]

    recent_checkins = repo.search(
        user_id=user_id,
        object_types=["daily_checkin"],
        date_from=seven_days_ago,
        date_to=today,
        limit=7,
    )

    recent_journal = repo.search(
        user_id=user_id,
        object_types=["journal_entry"],
        date_from=seven_days_ago,
        date_to=today,
        limit=5,
    )

    active_goals = repo.search(
        user_id=user_id,
        object_types=["goal"],
        limit=5,
    )
    active_goals = [item for item in active_goals if item.snippet.startswith("[active]")]

    attendance = repo.get_engagement_summary(user_id=user_id, window_days=7)

    return GuidedPromptsResponse(
        prompts=[
            GuidedPrompt(
                id="open_tasks",
                label="Open Tasks",
                description="Tasks that are still actionable right now.",
                results=open_tasks,
            ),
            GuidedPrompt(
                id="recent_checkins",
                label="Recent Check-ins",
                description="Daily check-ins from the last 7 days.",
                results=recent_checkins,
            ),
            GuidedPrompt(
                id="recent_journal",
                label="Recent Journal",
                description="Journal captures from the last 7 days.",
                results=recent_journal,
            ),
            GuidedPrompt(
                id="active_goals",
                label="Active Goals",
                description="Goals currently marked active.",
                results=active_goals,
            ),
            GuidedPrompt(
                id="attendance_this_week",
                label="Attendance This Week",
                description="Continuity and response behavior across recent prompt cycles.",
                metadata={
                    "window_days": attendance.window_days,
                    "total_cycles": attendance.total_cycles,
                    "responded_cycles": attendance.responded_cycles,
                    "missed_cycles": attendance.missed_cycles,
                    "viewed_no_response_cycles": attendance.viewed_no_response_cycles,
                    "adherence_rate": attendance.adherence_rate,
                    "longest_nonresponse_streak_days": attendance.longest_nonresponse_streak_days,
                    "streak_resume_count": attendance.streak_resume_count,
                },
            ),
        ]
    )
