from __future__ import annotations

import re

from ..schemas import CompanionDirective
from ..storage.repository import Repository
from .context_snapshot import ContextSnapshot
from .intent import ClassificationResult


_HELP_RE = re.compile(r"\b(?:what can you do|who are you|help|how do you work)\b", re.I)


def load_pending_companion(conversation) -> CompanionDirective | None:
    payload = getattr(conversation, "metadata", {}).get("pending_companion")
    if not payload:
        return None
    try:
        return CompanionDirective.model_validate(payload)
    except Exception:
        return None


def should_consume_pending_companion(
    *,
    user_message: str,
    classification: ClassificationResult,
    pending: CompanionDirective | None,
) -> bool:
    if pending is None or not pending.actions:
        return False

    if classification.intent == "query":
        return False

    if _HELP_RE.search(user_message):
        return False

    if classification.intent == "log":
        return pending.actions[0].expected_response == "checkin_state"

    return classification.intent == "chat"


def apply_pending_action_intent(
    *,
    classification: ClassificationResult,
    pending: CompanionDirective | None,
) -> ClassificationResult:
    if pending is None or not pending.actions:
        return classification

    primary = pending.actions[0]
    if classification.intent == "chat" and primary.expected_response == "checkin_state":
        return ClassificationResult(
            intent="log",
            confidence=max(classification.confidence, 0.92),
            reasoning="pending companion check-in response",
            query_params=classification.query_params,
        )

    return classification


def advance_pending_companion(
    *,
    pending: CompanionDirective,
    snapshot: ContextSnapshot,
) -> CompanionDirective | None:
    remaining_actions = pending.actions[1:]
    if not remaining_actions:
        return None

    return CompanionDirective(
        mode=remaining_actions[0].kind,
        active_thread=pending.active_thread,
        rationale=[
            *pending.rationale,
            "User is responding to the pending companion prompt, so the thread advances to the next step.",
        ],
        signals=pending.signals,
        actions=remaining_actions,
    )


def persist_pending_companion(
    *,
    repo: Repository,
    conversation,
    user_id: str,
    companion: CompanionDirective | None,
) -> None:
    metadata = dict(getattr(conversation, "metadata", {}) or {})
    if companion is None or not companion.actions:
        metadata.pop("pending_companion", None)
    else:
        metadata["pending_companion"] = companion.model_dump(mode="json")
    updated = repo.update_conversation_metadata(
        conversation_id=conversation.id,
        user_id=user_id,
        metadata=metadata,
    )
    if updated is not None:
        conversation.metadata = updated.metadata
