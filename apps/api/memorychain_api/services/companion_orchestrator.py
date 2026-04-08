from __future__ import annotations

import re

from ..schemas import CompanionDirective, CompanionSignal
from .context_snapshot import ContextSnapshot
from .intent import ClassificationResult


_GREETING_RE = re.compile(r"^\s*(?:hey|hi|hello|yo|sup|good morning|morning|good evening)\b[!?.\s]*$", re.I)
_HELP_RE = re.compile(r"\b(?:what can you do|who are you|help|how do you work)\b", re.I)
_NEGATIVE_RE = re.compile(r"\b(?:tired|drained|rough|fried|stressed|anxious|overwhelmed|ugh|fuck|bad)\b", re.I)
_POSITIVE_RE = re.compile(r"\b(?:good|solid|sharp|ready|locked in|great|energized)\b", re.I)
_TREND_RE = re.compile(r"\b(?:trend|pattern|why|week|month|review|progress|lately)\b", re.I)


def _infer_signals(message: str, snapshot: ContextSnapshot) -> list[CompanionSignal]:
    signals: list[CompanionSignal] = []
    text = message.strip().lower()

    if _NEGATIVE_RE.search(text):
        signals.append(
            CompanionSignal(
                key="stress_signal",
                summary="Language suggests friction or low internal bandwidth.",
                confidence=0.82,
            )
        )
    elif _POSITIVE_RE.search(text):
        signals.append(
            CompanionSignal(
                key="positive_activation",
                summary="Language suggests forward energy or readiness.",
                confidence=0.72,
            )
        )

    if _GREETING_RE.match(text) and not snapshot.has_checkin_today and snapshot.period in {
        "early morning",
        "morning",
        "early afternoon",
    }:
        signals.append(
            CompanionSignal(
                key="brief_opening",
                summary="A minimal opening likely means the user wants the system to lead.",
                confidence=0.7,
            )
        )

    if not snapshot.has_checkin_today and snapshot.is_morning_window:
        signals.append(
            CompanionSignal(
                key="missing_checkin",
                summary="There is no check-in for today yet.",
                confidence=0.95,
            )
        )

    if snapshot.likely_low_recovery:
        signals.append(
            CompanionSignal(
                key="low_recovery",
                summary="Recent sleep or energy signals suggest reduced recovery capacity.",
                confidence=0.76,
            )
        )

    if snapshot.likely_low_mood:
        signals.append(
            CompanionSignal(
                key="low_mood_risk",
                summary="Recent mood signals are low enough to warrant extra context before planning hard.",
                confidence=0.68,
            )
        )

    if snapshot.has_stale_commitment_pressure:
        signals.append(
            CompanionSignal(
                key="stale_commitment_pressure",
                summary="Older open tasks suggest commitment drag is building.",
                confidence=0.84,
            )
        )

    if snapshot.longest_nonresponse_streak_days >= 2 and (snapshot.adherence_rate_7d or 0.0) < 0.6:
        signals.append(
            CompanionSignal(
                key="continuity_gap",
                summary="Recent adherence has slipped enough to affect continuity.",
                confidence=0.88,
            )
        )

    if snapshot.has_pattern_pressure:
        signals.append(
            CompanionSignal(
                key="pattern_pressure",
                summary="Existing patterns or heuristics are relevant to the current conversation.",
                confidence=0.66,
            )
        )

    if snapshot.has_goal_alignment_pressure:
        signals.append(
            CompanionSignal(
                key="goal_alignment_pressure",
                summary="Recent commitment drift events suggest stated direction and follow-through are diverging.",
                confidence=0.79,
            )
        )

    return signals


def orchestrate_companion(
    *,
    user_message: str,
    classification: ClassificationResult,
    snapshot: ContextSnapshot,
) -> CompanionDirective:
    signals = _infer_signals(user_message, snapshot)
    rationale: list[str] = []
    text = user_message.strip().lower()

    if classification.intent == "log":
        rationale.append("User is providing capture-worthy data.")
        if re.search(r"\b(?:todo|goal)\s*:", text):
            rationale.append("The log includes a declared commitment or direction.")
            return CompanionDirective(
                mode="commit",
                active_thread="daily_capture",
                rationale=rationale,
                signals=signals,
            )
        return CompanionDirective(
            mode="intake",
            active_thread="daily_capture",
            rationale=rationale,
            signals=signals,
        )

    if classification.intent == "query":
        rationale.append("User is asking for retrieval or synthesis.")
        if _TREND_RE.search(text):
            rationale.append("The question asks for broader review rather than a single lookup.")
        return CompanionDirective(
            mode="review",
            active_thread="general_query",
            rationale=rationale,
            signals=signals,
        )

    if _HELP_RE.search(text):
        rationale.append("User is asking about system capabilities.")
        return CompanionDirective(
            mode="guide",
            active_thread="general",
            rationale=rationale,
            signals=signals,
        )

    if not snapshot.has_checkin_today and snapshot.is_morning_window:
        rationale.append("No check-in has been logged for today.")
        rationale.append("This time window makes current-state intake the highest-value thread.")
        if snapshot.likely_low_recovery:
            rationale.append("Recent recovery signals suggest today's state should be established before planning.")
        return CompanionDirective(
            mode="intake",
            active_thread="daily_checkin",
            rationale=rationale,
            signals=signals,
        )

    adherence = snapshot.adherence_rate_7d if snapshot.adherence_rate_7d is not None else 1.0
    if snapshot.longest_nonresponse_streak_days >= 2 and adherence < 0.6:
        rationale.append("Recent continuity is weak enough to warrant reflection before planning.")
        if snapshot.has_stale_commitment_pressure:
            rationale.append("Open loops are still present, which increases the cost of drift.")
        return CompanionDirective(
            mode="reflect",
            active_thread="continuity_gap",
            rationale=rationale,
            signals=signals,
        )

    if snapshot.has_stale_commitment_pressure:
        rationale.append("There are stale open loops competing with new planning.")
        if snapshot.active_goal_count > 0:
            rationale.append("Those stale loops likely affect goal alignment for today.")
        return CompanionDirective(
            mode="guide",
            active_thread="stale_commitment",
            rationale=rationale,
            signals=signals,
        )

    if snapshot.has_pattern_pressure and snapshot.candidate_insight_count > 0:
        rationale.append("There are unresolved candidate patterns that may matter right now.")
        if snapshot.active_heuristic_count > 0:
            rationale.append("Validated heuristics already exist, so pattern review can shape today's guidance.")
        return CompanionDirective(
            mode="reflect",
            active_thread="pattern_review",
            rationale=rationale,
            signals=signals,
        )

    if snapshot.has_goal_alignment_pressure:
        rationale.append("There are unresolved commitment mismatches that should be named before ordinary planning.")
        if snapshot.active_goal_count > 0:
            rationale.append("Those mismatches matter because they can distort the shape of current goals.")
        return CompanionDirective(
            mode="reflect",
            active_thread="goal_alignment",
            rationale=rationale,
            signals=signals,
        )

    if snapshot.active_goal_count > 0:
        rationale.append("Active goals exist, so the companion should help shape the day's focus.")
        return CompanionDirective(
            mode="guide",
            active_thread="daily_focus",
            rationale=rationale,
            signals=signals,
        )

    rationale.append("No stronger thread is available, so the system should open a general companion exchange.")
    return CompanionDirective(
        mode="guide",
        active_thread="general",
        rationale=rationale,
        signals=signals,
    )
