from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import CompanionDirective, TaskCreate, TaskUpdate
from ..storage.repository import Repository


_CANCEL_RE = re.compile(r"\b(?:kill|drop|cancel|remove|delete|not real|not anymore|let it go|scrap)\b", re.I)
_DONE_RE = re.compile(r"\b(?:done|finished|completed|already did|wrapped)\b", re.I)
_KEEP_RE = re.compile(r"\b(?:keep|still real|yes|doing it|continue|keep it|still matters)\b", re.I)
_DEFER_RE = re.compile(r"\b(?:later|not today|tomorrow|this week|next week|defer|renegotiate|push it)\b", re.I)


@dataclass
class CompanionExecutionResult:
    applied: bool = False
    should_advance: bool = True
    keep_pending: bool = False
    assistant_note: str | None = None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _resolve_task(repo: Repository, user_id: str, focus_items: list[str]):
    candidates = repo.list_open_tasks(user_id=user_id, limit=20)
    requested_titles = [_normalize(item) for item in focus_items if item and "_" not in item]
    if not requested_titles:
        return candidates[0] if candidates else None

    for requested in requested_titles:
        exact = next((task for task in candidates if _normalize(task.title) == requested), None)
        if exact is not None:
            return exact
    for requested in requested_titles:
        loose = next(
            (
                task for task in candidates
                if requested in _normalize(task.title) or _normalize(task.title) in requested
            ),
            None,
        )
        if loose is not None:
            return loose
    return candidates[0] if candidates else None


def _extract_commitment_title(message: str) -> str | None:
    cleaned = message.strip().strip("`").strip()
    if not cleaned:
        return None

    cleaned = re.sub(r"^(?:i will|i'll|plan(?: is)? to|today(?: i will)?|just|keep it as)\s+", "", cleaned, flags=re.I)
    cleaned = cleaned.splitlines()[0].strip()
    cleaned = re.split(r"[.?!]", cleaned, maxsplit=1)[0].strip(" ,;:-")
    if len(cleaned) < 8:
        return None
    if _normalize(cleaned) in {"yes", "no", "maybe", "later", "tomorrow"}:
        return None
    return cleaned


def _focus_discrepancy_id(focus_items: list[str]) -> str | None:
    for item in focus_items:
        if item.startswith("discrepancy:"):
            return item.split(":", 1)[1]
    return None


def _resolve_related_discrepancy(repo: Repository, user_id: str, *, action_focus_items: list[str], related_task_id: str | None) -> None:
    discrepancy_id = _focus_discrepancy_id(action_focus_items)
    if discrepancy_id is not None:
        repo.resolve_discrepancy_event(discrepancy_id=discrepancy_id, user_id=user_id)
        return
    if related_task_id is None:
        return
    open_events = repo.list_discrepancy_events(user_id=user_id, status="open", limit=20)
    match = next((event for event in open_events if event.related_task_id == related_task_id), None)
    if match is not None:
        repo.resolve_discrepancy_event(discrepancy_id=match.id, user_id=user_id)


def execute_pending_companion(
    *,
    repo: Repository,
    user_id: str,
    pending: CompanionDirective | None,
    user_message: str,
) -> CompanionExecutionResult:
    if pending is None or not pending.actions:
        return CompanionExecutionResult()

    action = pending.actions[0]
    text = user_message.strip()

    if action.expected_response == "task_status":
        task = _resolve_task(repo, user_id, action.focus_items)
        if task is None:
            return CompanionExecutionResult(
                applied=False,
                should_advance=False,
                keep_pending=True,
                assistant_note="I need the task to be identifiable before I can change it.",
            )

        if _CANCEL_RE.search(text):
            repo.update_task(task_id=task.id, user_id=user_id, payload=TaskUpdate(status="canceled"))
            if pending.active_thread == "stale_commitment":
                repo.create_discrepancy_event(
                    user_id=user_id,
                    kind="commitment_drift",
                    summary=f"Canceled `{task.title}` after it stayed open without follow-through.",
                    detail=text,
                    related_task_id=task.id,
                    evidence=[task.title, text],
                    metadata={"source_thread": pending.active_thread, "resolution": "canceled"},
                )
            return CompanionExecutionResult(
                applied=True,
                should_advance=False,
                assistant_note=f"Marked `{task.title}` as canceled.",
            )
        if _DONE_RE.search(text):
            repo.update_task(task_id=task.id, user_id=user_id, payload=TaskUpdate(status="done"))
            return CompanionExecutionResult(
                applied=True,
                should_advance=False,
                assistant_note=f"Marked `{task.title}` as done.",
            )
        if _KEEP_RE.search(text):
            repo.update_task(task_id=task.id, user_id=user_id, payload=TaskUpdate(status="in_progress"))
            return CompanionExecutionResult(
                applied=True,
                should_advance=True,
                assistant_note=f"Keeping `{task.title}` active.",
            )
        if _DEFER_RE.search(text):
            repo.update_task(task_id=task.id, user_id=user_id, payload=TaskUpdate(status="todo"))
            if pending.active_thread == "stale_commitment":
                repo.create_discrepancy_event(
                    user_id=user_id,
                    kind="commitment_drift",
                    summary=f"Deferred `{task.title}` after it stayed open without follow-through.",
                    detail=text,
                    related_task_id=task.id,
                    evidence=[task.title, text],
                    metadata={"source_thread": pending.active_thread, "resolution": "deferred"},
                )
            return CompanionExecutionResult(
                applied=True,
                should_advance=True,
                assistant_note=f"Leaving `{task.title}` open, but not treating it as active right now.",
            )
        return CompanionExecutionResult(
            applied=False,
            should_advance=False,
            keep_pending=True,
            assistant_note=(
                f"I need a clean status on `{task.title}`: keep it, renegotiate it, or kill it."
            ),
        )

    if action.expected_response == "plan_outline":
        title = _extract_commitment_title(text)
        if title is None:
            return CompanionExecutionResult(
                applied=False,
                should_advance=False,
                keep_pending=True,
                assistant_note="Give me the concrete next step in one clear line.",
            )

        existing = _resolve_task(repo, user_id, action.focus_items)
        if pending.active_thread == "stale_commitment" and existing is not None:
            repo.update_task(
                task_id=existing.id,
                user_id=user_id,
                payload=TaskUpdate(title=title, status="in_progress"),
            )
            _resolve_related_discrepancy(
                repo,
                user_id,
                action_focus_items=action.focus_items,
                related_task_id=existing.id,
            )
            return CompanionExecutionResult(
                applied=True,
                should_advance=False,
                assistant_note=f"Updated `{existing.title}` to `{title}` and kept it active.",
            )

        open_tasks = repo.list_open_tasks(user_id=user_id, limit=20)
        duplicate = next((task for task in open_tasks if _normalize(task.title) == _normalize(title)), None)
        if duplicate is not None:
            repo.update_task(task_id=duplicate.id, user_id=user_id, payload=TaskUpdate(status="in_progress"))
            _resolve_related_discrepancy(
                repo,
                user_id,
                action_focus_items=action.focus_items,
                related_task_id=duplicate.id,
            )
            return CompanionExecutionResult(
                applied=True,
                should_advance=False,
                assistant_note=f"`{duplicate.title}` was already open, so I marked it active.",
            )

        repo.create_task(TaskCreate(user_id=user_id, title=title))
        _resolve_related_discrepancy(
            repo,
            user_id,
            action_focus_items=action.focus_items,
            related_task_id=None,
        )
        return CompanionExecutionResult(
            applied=True,
            should_advance=False,
            assistant_note=f"Created a task for `{title}`.",
        )

    return CompanionExecutionResult()
