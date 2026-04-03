"""Phase 2 tests: insight detection, promotion, status lifecycle.

Tests cover:
  - Sleep-mood detection with realistic data
  - Idempotent re-detection (no duplicates)
  - Rejected detector_key blocks re-creation
  - Promote endpoint (success + threshold failures)
  - Status transitions (valid + invalid)
  - Promotion snapshot stored on heuristic
  - Pearson correlation correctness
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient

from memorychain_api.main import create_app
from memorychain_api.schemas import DailyCheckinCreate, SourceDocumentCreate
from memorychain_api.services.insight_detection import _pearson, _r_to_confidence

AUTH = {"X-API-Key": "dev-key"}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _seed_checkins(
    client: TestClient,
    user_id: str,
    count: int = 20,
    sleep_mood_correlated: bool = True,
) -> None:
    """Seed daily checkins with sleep/mood data directly via the repo.

    If sleep_mood_correlated is True, high sleep → high mood (positive r).
    If False, random-ish data with no clear pattern.
    """
    app = client.app
    repo = app.state.repo

    base_date = date.today() - timedelta(days=count)

    for i in range(count):
        d = base_date + timedelta(days=i)
        effective = datetime(d.year, d.month, d.day, 8, 0, tzinfo=timezone.utc)

        # Create source document (unique text per checkin to avoid content_hash collision)
        src = repo.create_source_document(
            SourceDocumentCreate(
                user_id=user_id,
                source_type="chat_message",
                effective_at=effective,
                raw_text=f"Test checkin for {user_id} on {d} #{uuid.uuid4().hex[:8]}",
            )
        )

        if sleep_mood_correlated:
            # Strong positive: sleep 5–9h, mood tracks sleep linearly
            sleep = 5.0 + (i % 5)  # cycles 5, 6, 7, 8, 9
            mood = max(1, min(10, int(sleep - 1)))  # 4, 5, 6, 7, 8
        else:
            # No correlation: alternating pattern
            sleep = 7.0 if i % 2 == 0 else 5.0
            mood = 5  # constant mood regardless of sleep

        repo.create_checkin(
            DailyCheckinCreate(
                user_id=user_id,
                source_document_id=src.id,
                date=d,
                effective_at=effective,
                sleep_hours=sleep,
                mood=mood,
            )
        )


# -- Pearson correlation unit tests --


def test_pearson_perfect_positive() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    r = _pearson(xs, ys)
    assert abs(r - 1.0) < 0.001


def test_pearson_perfect_negative() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [10.0, 8.0, 6.0, 4.0, 2.0]
    r = _pearson(xs, ys)
    assert abs(r - (-1.0)) < 0.001


def test_pearson_no_correlation() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [5.0, 5.0, 5.0, 5.0, 5.0]  # constant → stdev=0 → r=0
    r = _pearson(xs, ys)
    assert r == 0.0


def test_r_to_confidence_mapping() -> None:
    assert _r_to_confidence(0.1) == 0.0  # below threshold
    assert 0.4 <= _r_to_confidence(0.35) <= 0.6  # moderate
    assert 0.6 <= _r_to_confidence(0.55) <= 0.8  # strong
    assert 0.8 <= _r_to_confidence(0.75) <= 0.95  # very strong


# -- Detection endpoint tests --


def test_detect_produces_insight() -> None:
    """Detection with correlated data should produce a candidate insight."""
    client = TestClient(create_app())
    user_id = _uid("det")
    _seed_checkins(client, user_id, count=20, sleep_mood_correlated=True)

    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    insights = resp.json()
    assert len(insights) >= 1

    insight = insights[0]
    assert insight["detector_key"] == "sleep_mood_v1"
    assert insight["status"] == "candidate"
    assert insight["confidence"] > 0.0
    assert len(insight["evidence_ids"]) >= 7
    assert "sleep" in insight["title"].lower()
    assert insight["time_window_start"] is not None
    assert insight["time_window_end"] is not None


def test_detect_idempotent() -> None:
    """Running detection twice should not create duplicate insights."""
    client = TestClient(create_app())
    user_id = _uid("idem")
    _seed_checkins(client, user_id, count=20, sleep_mood_correlated=True)

    resp1 = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp1.status_code == 200
    first_run = resp1.json()
    assert len(first_run) >= 1

    resp2 = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp2.status_code == 200
    second_run = resp2.json()
    assert len(second_run) == 0  # No new insights — already exists


def test_detect_no_correlation() -> None:
    """Detection with uncorrelated data should produce no insights."""
    client = TestClient(create_app())
    user_id = _uid("nocor")
    _seed_checkins(client, user_id, count=20, sleep_mood_correlated=False)

    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_detect_insufficient_data() -> None:
    """Detection with <7 data points should produce no insights."""
    client = TestClient(create_app())
    user_id = _uid("few")
    _seed_checkins(client, user_id, count=3, sleep_mood_correlated=True)

    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_detect_blocked_by_rejection() -> None:
    """After rejecting an insight, re-detection should not re-create it."""
    client = TestClient(create_app())
    user_id = _uid("rej")
    _seed_checkins(client, user_id, count=20, sleep_mood_correlated=True)

    # Detect
    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    insight_id = resp.json()[0]["id"]

    # Reject it
    resp = client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "rejected", "reason": "Not meaningful to me"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # Re-detect — should produce nothing
    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


# -- Status transition tests --


def test_status_candidate_to_active() -> None:
    client = TestClient(create_app())
    user_id = _uid("sta")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Test", "summary": "Test insight"},
    )
    insight_id = created.json()["id"]

    resp = client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_status_invalid_transition() -> None:
    """Rejected → active should be blocked."""
    client = TestClient(create_app())
    user_id = _uid("inv")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Test", "summary": "Test insight"},
    )
    insight_id = created.json()["id"]

    # candidate → rejected
    client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "rejected"},
    )

    # rejected → active (invalid)
    resp = client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )
    assert resp.status_code == 409


def test_status_promoted_via_status_blocked() -> None:
    """Cannot set status to 'promoted' directly — must use /promote."""
    client = TestClient(create_app())
    user_id = _uid("pblk")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Test", "summary": "Test insight"},
    )
    insight_id = created.json()["id"]

    # Try to set status directly to promoted
    resp = client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "promoted"},
    )
    assert resp.status_code == 400
    assert "promote" in resp.json()["detail"].lower()


# -- Promotion tests --


def test_promote_success() -> None:
    """Full lifecycle: detect → activate → promote → heuristic created."""
    client = TestClient(create_app())
    user_id = _uid("promo")
    _seed_checkins(client, user_id, count=30, sleep_mood_correlated=True)

    # Detect
    resp = client.post(
        "/api/v1/insights/detect",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert resp.status_code == 200
    insight = resp.json()[0]
    insight_id = insight["id"]

    # Activate
    resp = client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )
    assert resp.status_code == 200

    # Promote
    resp = client.post(
        f"/api/v1/insights/{insight_id}/promote",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert resp.status_code == 200
    heuristic = resp.json()
    assert heuristic["insight_id"] == insight_id
    assert heuristic["source_type"] == "validated_pattern"
    assert heuristic["confidence"] == insight["confidence"]
    assert heuristic["promotion_snapshot"] is not None
    assert "thresholds" in heuristic["promotion_snapshot"]
    assert "values_at_promotion" in heuristic["promotion_snapshot"]
    assert heuristic["active"] is True

    # Verify insight is now promoted
    resp = client.get(
        f"/api/v1/insights/{insight_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert resp.json()["status"] == "promoted"


def test_promote_fails_not_active() -> None:
    """Cannot promote a candidate insight — must be active first."""
    client = TestClient(create_app())
    user_id = _uid("pna")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Test",
            "summary": "Test",
            "evidence_ids": [f"e{i}" for i in range(10)],
            "time_window_start": "2025-01-01",
            "time_window_end": "2025-03-01",
        },
    )
    insight_id = created.json()["id"]

    resp = client.post(
        f"/api/v1/insights/{insight_id}/promote",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "active" in str(detail).lower()


def test_promote_fails_insufficient_evidence() -> None:
    """Cannot promote with <5 evidence items."""
    client = TestClient(create_app())
    user_id = _uid("pie")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Test",
            "summary": "Test",
            "evidence_ids": ["e1", "e2"],  # only 2
            "time_window_start": "2025-01-01",
            "time_window_end": "2025-03-01",
        },
    )
    insight_id = created.json()["id"]

    # Activate first
    client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )

    resp = client.post(
        f"/api/v1/insights/{insight_id}/promote",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "evidence" in str(detail).lower()


def test_promote_fails_insufficient_span() -> None:
    """Cannot promote if time span < 3 weeks."""
    client = TestClient(create_app())
    user_id = _uid("pis")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Test",
            "summary": "Test",
            "evidence_ids": [f"e{i}" for i in range(10)],
            "time_window_start": "2025-01-01",
            "time_window_end": "2025-01-10",  # only 9 days
        },
    )
    insight_id = created.json()["id"]

    # Activate
    client.put(
        f"/api/v1/insights/{insight_id}/status",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )

    resp = client.post(
        f"/api/v1/insights/{insight_id}/promote",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "span" in str(detail).lower() or "week" in str(detail).lower()


# -- detector_key field tests --


def test_detector_key_persisted() -> None:
    """detector_key should be stored and returned."""
    client = TestClient(create_app())
    user_id = _uid("dkey")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Test",
            "summary": "Test",
            "detector_key": "custom_detector_v1",
        },
    )
    assert created.status_code == 200
    assert created.json()["detector_key"] == "custom_detector_v1"

    # Fetch and verify persisted
    insight_id = created.json()["id"]
    fetched = client.get(
        f"/api/v1/insights/{insight_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.json()["detector_key"] == "custom_detector_v1"
