from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from memorychain_api.services.companion_actions import build_companion_actions
from memorychain_api.services.companion_orchestrator import orchestrate_companion
from memorychain_api.services.context_snapshot import build_context_snapshot
from memorychain_api.services.intent import ClassificationResult
from memorychain_api.services.llm import generate_companion_reply


def test_build_context_snapshot_computes_recent_state() -> None:
    repo = MagicMock()
    today = date(2026, 4, 7)
    now = datetime(2026, 4, 7, 9, 30)

    repo.list_open_tasks.return_value = [
        SimpleNamespace(title="Old task", created_at=datetime(2026, 3, 20, 8, 0)),
        SimpleNamespace(title="Fresh task", created_at=datetime(2026, 4, 6, 8, 0)),
    ]
    repo.list_goals.return_value = [
        SimpleNamespace(title="Goal A", status="active"),
        SimpleNamespace(title="Goal B", status="completed"),
    ]
    repo.list_checkins.return_value = [
        SimpleNamespace(date=today - timedelta(days=1), sleep_hours=7.0, mood=6, energy=5),
        SimpleNamespace(date=today - timedelta(days=2), sleep_hours=8.0, mood=8, energy=7),
    ]
    repo.list_insights.return_value = [SimpleNamespace(status="candidate"), SimpleNamespace(status="active")]
    repo.list_heuristics.return_value = [SimpleNamespace(rule="Protect sleep")]
    repo.list_discrepancy_events.return_value = [
        SimpleNamespace(id="disc_1", summary="Canceled `Old task` after it stayed open without follow-through.")
    ]
    repo.get_engagement_summary.return_value = SimpleNamespace(
        adherence_rate=0.5,
        longest_nonresponse_streak_days=2,
    )
    repo.get_user_profile.return_value = None

    snapshot = build_context_snapshot(repo, "sam", now=now)

    assert snapshot.has_checkin_today is False
    assert snapshot.days_since_checkin == 1
    assert snapshot.open_task_count == 2
    assert snapshot.stale_task_count == 1
    assert snapshot.active_goal_count == 1
    assert snapshot.candidate_insight_count == 1
    assert snapshot.active_heuristic_count == 1
    assert snapshot.unresolved_discrepancy_count == 1
    assert snapshot.latest_sleep_hours == 7.0
    assert snapshot.latest_mood == 6
    assert snapshot.latest_energy == 5
    assert snapshot.recent_sleep_avg == 7.5
    assert snapshot.recent_mood_avg == 7.0
    assert snapshot.recent_energy_avg == 6.0
    assert snapshot.has_stale_commitment_pressure is True
    assert snapshot.has_pattern_pressure is True
    assert snapshot.has_goal_alignment_pressure is True


def test_orchestrator_prioritizes_daily_checkin_for_morning_greeting() -> None:
    snapshot = SimpleNamespace(
        has_checkin_today=False,
        period="morning",
        is_morning_window=True,
        longest_nonresponse_streak_days=0,
        adherence_rate_7d=None,
        stale_task_count=0,
        has_stale_commitment_pressure=False,
        candidate_insight_count=0,
        active_heuristic_count=0,
        unresolved_discrepancy_count=0,
        has_pattern_pressure=False,
        has_goal_alignment_pressure=False,
        active_goal_count=1,
        likely_low_recovery=False,
        likely_low_mood=False,
    )

    directive = orchestrate_companion(
        user_message="hey",
        classification=ClassificationResult(intent="chat", confidence=0.9),
        snapshot=snapshot,
    )

    assert directive.mode == "intake"
    assert directive.active_thread == "daily_checkin"

    actions = build_companion_actions(
        user_message="hey",
        snapshot=snapshot,
        directive=directive,
    )

    assert actions[0].kind == "clarify"
    assert actions[0].expected_response == "checkin_state"
    assert "sleep" in actions[0].prompt.lower()


def test_orchestrator_reflects_on_continuity_gaps_before_planning() -> None:
    snapshot = SimpleNamespace(
        has_checkin_today=True,
        period="afternoon",
        is_morning_window=False,
        longest_nonresponse_streak_days=3,
        adherence_rate_7d=0.4,
        stale_task_count=0,
        has_stale_commitment_pressure=False,
        candidate_insight_count=0,
        active_heuristic_count=0,
        unresolved_discrepancy_count=0,
        has_pattern_pressure=False,
        has_goal_alignment_pressure=False,
        active_goal_count=1,
        likely_low_recovery=False,
        likely_low_mood=False,
    )

    directive = orchestrate_companion(
        user_message="hey",
        classification=ClassificationResult(intent="chat", confidence=0.9),
        snapshot=snapshot,
    )

    assert directive.mode == "reflect"
    assert directive.active_thread == "continuity_gap"


def test_orchestrator_guides_on_stale_commitments() -> None:
    snapshot = SimpleNamespace(
        has_checkin_today=True,
        period="afternoon",
        is_morning_window=False,
        longest_nonresponse_streak_days=0,
        adherence_rate_7d=0.8,
        stale_task_count=2,
        has_stale_commitment_pressure=True,
        candidate_insight_count=0,
        active_heuristic_count=0,
        unresolved_discrepancy_count=0,
        has_pattern_pressure=False,
        has_goal_alignment_pressure=False,
        active_goal_count=1,
        likely_low_recovery=False,
        likely_low_mood=False,
    )

    directive = orchestrate_companion(
        user_message="hey",
        classification=ClassificationResult(intent="chat", confidence=0.9),
        snapshot=snapshot,
    )

    assert directive.mode == "guide"
    assert directive.active_thread == "stale_commitment"

    actions = build_companion_actions(
        user_message="hey",
        snapshot=SimpleNamespace(
            open_task_titles=["Finish refactor"],
            active_goal_titles=["Ship companion"],
        ),
        directive=directive,
    )

    assert actions[0].kind == "commit"
    assert actions[0].expected_response == "task_status"
    assert "finish refactor" in actions[0].prompt.lower()


def test_orchestrator_reflects_on_patterns_when_candidates_exist() -> None:
    snapshot = SimpleNamespace(
        has_checkin_today=True,
        period="evening",
        is_morning_window=False,
        longest_nonresponse_streak_days=0,
        adherence_rate_7d=0.9,
        stale_task_count=0,
        has_stale_commitment_pressure=False,
        candidate_insight_count=2,
        active_heuristic_count=1,
        unresolved_discrepancy_count=0,
        has_pattern_pressure=True,
        has_goal_alignment_pressure=False,
        active_goal_count=1,
        likely_low_recovery=False,
        likely_low_mood=False,
    )

    directive = orchestrate_companion(
        user_message="hey",
        classification=ClassificationResult(intent="chat", confidence=0.9),
        snapshot=snapshot,
    )

    assert directive.mode == "reflect"
    assert directive.active_thread == "pattern_review"


def test_orchestrator_reflects_on_goal_alignment_pressure() -> None:
    snapshot = SimpleNamespace(
        has_checkin_today=True,
        period="evening",
        is_morning_window=False,
        longest_nonresponse_streak_days=0,
        adherence_rate_7d=0.9,
        stale_task_count=0,
        has_stale_commitment_pressure=False,
        candidate_insight_count=0,
        active_heuristic_count=0,
        unresolved_discrepancy_count=2,
        has_pattern_pressure=False,
        has_goal_alignment_pressure=True,
        active_goal_count=1,
        likely_low_recovery=False,
        likely_low_mood=False,
    )

    directive = orchestrate_companion(
        user_message="hey",
        classification=ClassificationResult(intent="chat", confidence=0.9),
        snapshot=snapshot,
    )

    assert directive.mode == "reflect"
    assert directive.active_thread == "goal_alignment"


@patch("memorychain_api.services.llm._openai_reply")
def test_generate_companion_reply_falls_back_when_llm_ignores_directive(mock_openai_reply: MagicMock) -> None:
    mock_openai_reply.return_value = "Hey there! How's your evening going?"

    snapshot = SimpleNamespace(
        open_task_titles=["Finish refactor"],
        active_goal_titles=["Ship companion"],
        active_heuristic_rules=[],
        candidate_insight_titles=[],
        days_since_checkin=0,
        adherence_rate_7d=0.8,
        to_memory_context=lambda: ["Open tasks (1): Finish refactor", "Active goals (1): Ship companion"],
    )
    directive = SimpleNamespace(
        mode="guide",
        active_thread="stale_commitment",
        rationale=["There are stale open loops competing with new planning."],
        signals=[],
        actions=[
            SimpleNamespace(
                kind="commit",
                prompt="Decide whether `Finish refactor` is still real, should be renegotiated, or should be killed cleanly.",
                expected_response="task_status",
            )
        ],
    )

    reply = generate_companion_reply(
        user_message="hey",
        snapshot=snapshot,
        directive=directive,
        history_lines=[],
    )

    assert "finish refactor" in reply.lower()
    assert "how's your evening going" not in reply.lower()
    assert mock_openai_reply.call_args.kwargs["mode"] == "companion"


@patch("memorychain_api.services.llm._openai_reply")
def test_generate_companion_reply_uses_llm_for_brief_opening_when_compliant(mock_openai_reply: MagicMock) -> None:
    mock_openai_reply.return_value = (
        "Evening. `Finish refactor` is the pressure point right now. "
        "Is it still real, or do you need to renegotiate it cleanly?"
    )

    snapshot = SimpleNamespace(
        open_task_titles=["Finish refactor"],
        active_goal_titles=["Ship companion"],
        active_heuristic_rules=[],
        candidate_insight_titles=[],
        days_since_checkin=0,
        adherence_rate_7d=0.8,
        to_memory_context=lambda: ["Open tasks (1): Finish refactor", "Active goals (1): Ship companion"],
    )
    directive = SimpleNamespace(
        mode="guide",
        active_thread="stale_commitment",
        rationale=["There are stale open loops competing with new planning."],
        signals=[],
        actions=[
            SimpleNamespace(
                kind="commit",
                prompt="Decide whether `Finish refactor` is still real, should be renegotiated, or should be killed cleanly.",
                expected_response="task_status",
                focus_items=["Finish refactor", "Ship companion"],
            )
        ],
    )

    reply = generate_companion_reply(
        user_message="hey",
        snapshot=snapshot,
        directive=directive,
        history_lines=[],
    )

    assert "pressure point" in reply.lower()
    assert "finish refactor" in reply.lower()
    assert mock_openai_reply.call_args.kwargs["mode"] == "companion"


@patch("memorychain_api.services.llm._openai_reply")
def test_generate_companion_reply_uses_companion_mode_for_nontrivial_turns(mock_openai_reply: MagicMock) -> None:
    mock_openai_reply.return_value = "Let's get specific. What broke continuity, and what is actually true about today?"

    snapshot = SimpleNamespace(
        open_task_titles=[],
        active_goal_titles=["Ship companion"],
        active_heuristic_rules=[],
        candidate_insight_titles=[],
        days_since_checkin=0,
        adherence_rate_7d=0.4,
        to_memory_context=lambda: ["Active goals (1): Ship companion"],
    )
    directive = SimpleNamespace(
        mode="reflect",
        active_thread="continuity_gap",
        rationale=["Recent continuity is weak enough to warrant reflection before planning."],
        signals=[],
        actions=[
            SimpleNamespace(
                kind="reflect",
                prompt="What broke continuity, and what is actually true about today instead of the ideal version?",
                expected_response="open_text",
            )
        ],
    )

    reply = generate_companion_reply(
        user_message="I keep missing the plan and then overcompensating.",
        snapshot=snapshot,
        directive=directive,
        history_lines=[],
    )

    assert "what broke continuity" in reply.lower()
    assert mock_openai_reply.call_args.kwargs["mode"] == "companion"
