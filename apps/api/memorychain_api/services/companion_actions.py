from __future__ import annotations

from ..schemas import CompanionAction, CompanionActionKind, CompanionDirective, CompanionResponseShape
from .context_snapshot import ContextSnapshot


def _action(
    *,
    kind: CompanionActionKind,
    prompt: str,
    reason: str | None = None,
    expected_response: CompanionResponseShape = "open_text",
    focus_items: list[str] | None = None,
    inferred_from: list[str] | None = None,
) -> CompanionAction:
    return CompanionAction(
        kind=kind,
        prompt=prompt,
        reason=reason,
        expected_response=expected_response,
        focus_items=focus_items or [],
        inferred_from=inferred_from or [],
    )


def build_companion_actions(
    *,
    user_message: str,
    snapshot: ContextSnapshot,
    directive: CompanionDirective,
) -> list[CompanionAction]:
    signal_keys = [signal.key for signal in directive.signals]

    if directive.active_thread == "questionnaire":
        return [
            _action(
                kind="clarify",
                prompt="Answer the current questionnaire prompt directly so I can keep the intake clean.",
                reason="A questionnaire session is already in progress.",
                expected_response="questionnaire_answer",
            )
        ]

    if directive.active_thread == "daily_checkin":
        prompt = "Give me sleep, mood, energy, and the main tone of the morning."
        if "low_recovery" in signal_keys:
            prompt = "Start with sleep, energy, and whether your body actually has enough recovery for today."
        elif "low_mood_risk" in signal_keys:
            prompt = "Start with sleep, mood, energy, and what feels heaviest right now."
        return [
            _action(
                kind="clarify",
                prompt=prompt,
                reason="The highest-value move is to establish today's state before planning.",
                expected_response="checkin_state",
                focus_items=["sleep_hours", "mood", "energy", "stress_level"],
                inferred_from=[
                    key for key in signal_keys if key in {"brief_opening", "low_recovery", "low_mood_risk"}
                ],
            )
        ]

    if directive.active_thread == "daily_capture":
        if directive.mode == "commit":
            return [
                _action(
                    kind="commit",
                    prompt="If this should hold weight later, restate the concrete commitment in one clean line.",
                    reason="A logged declaration should be promoted into an explicit commitment when warranted.",
                    expected_response="plan_outline",
                    focus_items=["commitment"],
                )
            ]
        return [
            _action(
                kind="clarify",
                prompt="If any part of that needs tighter numbers, timing, or scope, add it now while the context is fresh.",
                reason="Fresh captures are easiest to clean up immediately.",
                expected_response="open_text",
                focus_items=["missing_detail"],
            )
        ]

    if directive.active_thread == "continuity_gap":
        return [
            _action(
                kind="reflect",
                prompt="What broke continuity, and what is actually true about today instead of the ideal version?",
                reason="Reflection needs to happen before new planning has any chance of sticking.",
                expected_response="open_text",
                focus_items=["continuity", "friction", "today_state"],
                inferred_from=[key for key in signal_keys if key in {"continuity_gap", "stress_signal"}],
            ),
            _action(
                kind="guide",
                prompt="After that, give me the minimum viable win that would re-establish momentum today.",
                reason="Once the drift is named, the day needs a low-friction re-entry point.",
                expected_response="plan_outline",
                focus_items=["minimum_viable_win"],
            ),
        ]

    if directive.active_thread == "stale_commitment":
        focus = snapshot.open_task_titles[0] if snapshot.open_task_titles else "the oldest open loop"
        focus_items = [focus]
        if snapshot.active_goal_titles:
            focus_items.append(snapshot.active_goal_titles[0])
        return [
            _action(
                kind="commit",
                prompt=f"Decide whether `{focus}` is still real, should be renegotiated, or should be killed cleanly.",
                reason="Stale commitments distort planning until they are made explicit.",
                expected_response="task_status",
                focus_items=focus_items,
                inferred_from=["stale_commitment_pressure"],
            ),
            _action(
                kind="guide",
                prompt="If it stays alive, restate the smallest concrete version that still counts.",
                reason="A smaller commitment is better than vague pressure.",
                expected_response="plan_outline",
                focus_items=[focus, "next_commitment"],
            ),
        ]

    if directive.active_thread == "pattern_review":
        pattern = None
        if snapshot.active_heuristic_rules:
            pattern = snapshot.active_heuristic_rules[0]
        elif snapshot.candidate_insight_titles:
            pattern = snapshot.candidate_insight_titles[0]
        focus_items = [pattern] if pattern else []
        prompt = "Does one of the recurring patterns seem active right now, and if so what is driving it?"
        if pattern:
            prompt = f"Is `{pattern}` showing up again right now, and if so what seems to be driving it?"
        return [
            _action(
                kind="reflect",
                prompt=prompt,
                reason="The system has enough pattern pressure to ask for explicit validation.",
                expected_response="open_text",
                focus_items=focus_items,
                inferred_from=["pattern_pressure"],
            ),
            _action(
                kind="guide",
                prompt="Name the adjustment that would interrupt that pattern today.",
                reason="Patterns only matter if they change the next move.",
                expected_response="plan_outline",
                focus_items=["pattern_interrupt"],
            ),
        ]

    if directive.active_thread == "goal_alignment":
        discrepancy = snapshot.recent_discrepancy_summaries[0] if snapshot.recent_discrepancy_summaries else None
        discrepancy_id = snapshot.recent_discrepancy_ids[0] if snapshot.recent_discrepancy_ids else None
        focus = snapshot.active_goal_titles[0] if snapshot.active_goal_titles else "what you say you want"
        reflect_prompt = "Where is the mismatch between what you want and what your behavior has actually been doing?"
        if discrepancy:
            reflect_prompt = f"`{discrepancy}`. What does that reveal about the gap between intention and follow-through?"
        focus_items = [focus]
        if discrepancy:
            focus_items.append(discrepancy)
        if discrepancy_id:
            focus_items.append(f"discrepancy:{discrepancy_id}")
        return [
            _action(
                kind="reflect",
                prompt=reflect_prompt,
                reason="Recent discrepancy memory says the system should name the mismatch explicitly.",
                expected_response="open_text",
                focus_items=focus_items,
                inferred_from=["goal_alignment_pressure"],
            ),
            _action(
                kind="commit",
                prompt="State the version you will actually follow through on next, in one concrete line.",
                reason="A named mismatch should end in a believable commitment, not a vague intention.",
                expected_response="plan_outline",
                focus_items=focus_items + ["alignment_commitment"],
                inferred_from=["goal_alignment_pressure"],
            ),
        ]

    if directive.active_thread == "daily_focus":
        focus = snapshot.active_goal_titles[0] if snapshot.active_goal_titles else "today"
        return [
            _action(
                kind="guide",
                prompt=f"What does the day need to revolve around if `{focus}` is going to move?",
                reason="There is enough continuity to shape the day around an active aim.",
                expected_response="plan_outline",
                focus_items=[focus],
            ),
            _action(
                kind="commit",
                prompt="State the concrete version you are actually willing to do, not the idealized one.",
                reason="Declared plans should be grounded in likely follow-through.",
                expected_response="plan_outline",
                focus_items=[focus, "daily_commitment"],
            ),
        ]

    if directive.active_thread == "general_query":
        return [
            _action(
                kind="guide",
                prompt="If you want, ask a narrower question and I'll anchor it to the underlying data.",
                reason="Queries are more useful when the scope is explicit.",
                expected_response="open_text",
            )
        ]

    return [
        _action(
            kind="clarify",
            prompt="Give me the current state in plain language, and I'll decide what matters most next.",
            reason="No stronger thread is active yet.",
            expected_response="open_text",
        )
    ]
