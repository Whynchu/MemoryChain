"""Thin httpx wrapper for the MemoryChain API."""

from __future__ import annotations

from typing import Any

import httpx

from .config import API_BASE_URL, API_KEY


def _headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def _url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


_TIMEOUT = 30.0


# ── Chat / Log ───────────────────────────────────────────────
def post_chat(message: str, *, user_id: str, conversation_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"message": message, "user_id": user_id}
    if conversation_id:
        body["conversation_id"] = conversation_id
    r = httpx.post(
        _url("/api/v1/chat"),
        headers=_headers(),
        json=body,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Checkins ─────────────────────────────────────────────────
def list_checkins(*, limit: int = 7) -> list[dict[str, Any]]:
    r = httpx.get(
        _url("/api/v1/checkins"),
        headers=_headers(),
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Goals ────────────────────────────────────────────────────
def list_goals(*, limit: int = 50) -> list[dict[str, Any]]:
    r = httpx.get(
        _url("/api/v1/goals"),
        headers=_headers(),
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Tasks ────────────────────────────────────────────────────
def list_tasks(*, limit: int = 50) -> list[dict[str, Any]]:
    r = httpx.get(
        _url("/api/v1/tasks"),
        headers=_headers(),
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Search ───────────────────────────────────────────────────
def search(query: str, *, user_id: str, limit: int = 20) -> dict[str, Any]:
    r = httpx.get(
        _url("/api/v1/search"),
        headers=_headers(),
        params={"q": query, "user_id": user_id, "limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Weekly Reviews ───────────────────────────────────────────
def generate_review(*, user_id: str, week_start: str, week_end: str) -> dict[str, Any]:
    r = httpx.post(
        _url("/api/v1/weekly-reviews/generate"),
        headers=_headers(),
        json={"user_id": user_id, "week_start": week_start, "week_end": week_end},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()


def list_reviews(*, limit: int = 5) -> list[dict[str, Any]]:
    r = httpx.get(
        _url("/api/v1/weekly-reviews"),
        headers=_headers(),
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Insights ─────────────────────────────────────────────────
def list_insights(*, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    r = httpx.get(
        _url("/api/v1/insights"),
        headers=_headers(),
        params=params,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def run_detectors(*, user_id: str) -> list[dict[str, Any]]:
    r = httpx.post(
        _url("/api/v1/insights/detect"),
        headers=_headers(),
        params={"user_id": user_id},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def change_insight_status(insight_id: str, status: str, *, user_id: str) -> dict[str, Any]:
    r = httpx.put(
        _url(f"/api/v1/insights/{insight_id}/status"),
        headers=_headers(),
        json={"status": status},
        params={"user_id": user_id},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def promote_insight(insight_id: str, *, user_id: str) -> dict[str, Any]:
    r = httpx.post(
        _url(f"/api/v1/insights/{insight_id}/promote"),
        headers=_headers(),
        params={"user_id": user_id},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Heuristics ───────────────────────────────────────────────
def list_heuristics(*, limit: int = 50) -> list[dict[str, Any]]:
    r = httpx.get(
        _url("/api/v1/heuristics"),
        headers=_headers(),
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Health ───────────────────────────────────────────────────
def health() -> dict[str, Any]:
    r = httpx.get(_url("/health"), timeout=5.0)
    r.raise_for_status()
    return r.json()


# ── User Profile ─────────────────────────────────────────────
def get_user_profile(*, user_id: str | None = None) -> dict[str, Any]:
    from .config import USER_ID
    uid = user_id or USER_ID
    r = httpx.get(
        _url(f"/api/v1/users/{uid}/profile"),
        headers=_headers(),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
