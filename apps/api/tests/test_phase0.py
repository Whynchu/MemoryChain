"""Tests for Phase 0 additions: activities, metrics, protocols, insights, heuristics, and search."""

from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from memorychain_api.main import create_app


AUTH = {"X-API-Key": "dev-key"}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Activity CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_activity() -> None:
    client = TestClient(create_app())
    user_id = _uid("act")

    created = client.post(
        "/api/v1/activities",
        headers=AUTH,
        json={
            "user_id": user_id,
            "effective_at": _now_iso(),
            "activity_type": "workout",
            "title": "Morning run",
            "description": "Easy 5k jog",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["activity_type"] == "workout"
    assert payload["title"] == "Morning run"
    activity_id = payload["id"]

    fetched = client.get(
        f"/api/v1/activities/{activity_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == activity_id


def test_list_activities() -> None:
    client = TestClient(create_app())
    user_id = _uid("act")

    for title in ["Run A", "Run B"]:
        resp = client.post(
            "/api/v1/activities",
            headers=AUTH,
            json={
                "user_id": user_id,
                "effective_at": _now_iso(),
                "activity_type": "workout",
                "title": title,
            },
        )
        assert resp.status_code == 200

    listed = client.get(
        "/api/v1/activities",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) >= 2
    titles = {a["title"] for a in items}
    assert "Run A" in titles
    assert "Run B" in titles


# ---------------------------------------------------------------------------
# Metric Observation CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_metric() -> None:
    client = TestClient(create_app())
    user_id = _uid("met")

    created = client.post(
        "/api/v1/metrics",
        headers=AUTH,
        json={
            "user_id": user_id,
            "effective_at": _now_iso(),
            "metric_type": "body_weight",
            "value": "185",
            "unit": "lbs",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["metric_type"] == "body_weight"
    assert payload["value"] == "185"
    metric_id = payload["id"]

    fetched = client.get(
        f"/api/v1/metrics/{metric_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == metric_id


def test_list_metrics() -> None:
    client = TestClient(create_app())
    user_id = _uid("met")

    for val in ["185", "186"]:
        resp = client.post(
            "/api/v1/metrics",
            headers=AUTH,
            json={
                "user_id": user_id,
                "effective_at": _now_iso(),
                "metric_type": "body_weight",
                "value": val,
                "unit": "lbs",
            },
        )
        assert resp.status_code == 200

    listed = client.get(
        "/api/v1/metrics",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) >= 2


# ---------------------------------------------------------------------------
# Protocol CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_protocol() -> None:
    client = TestClient(create_app())
    user_id = _uid("proto")

    created = client.post(
        "/api/v1/protocols",
        headers=AUTH,
        json={
            "user_id": user_id,
            "name": "Morning routine",
            "category": "daily",
            "description": "Stretching, breathwork, cold shower",
            "steps": ["Stretch 10 min", "Breathwork 5 min", "Cold shower 3 min"],
            "status": "active",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["name"] == "Morning routine"
    assert payload["status"] == "active"
    protocol_id = payload["id"]

    fetched = client.get(
        f"/api/v1/protocols/{protocol_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == protocol_id


def test_list_protocols() -> None:
    client = TestClient(create_app())
    user_id = _uid("proto")

    for name in ["Routine A", "Routine B"]:
        resp = client.post(
            "/api/v1/protocols",
            headers=AUTH,
            json={"user_id": user_id, "name": name, "category": "daily"},
        )
        assert resp.status_code == 200

    listed = client.get(
        "/api/v1/protocols",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_update_protocol() -> None:
    client = TestClient(create_app())
    user_id = _uid("proto")

    created = client.post(
        "/api/v1/protocols",
        headers=AUTH,
        json={"user_id": user_id, "name": "Draft routine", "status": "draft"},
    )
    assert created.status_code == 200
    protocol_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/protocols/{protocol_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active", "description": "Now live"},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "active"
    assert payload["description"] == "Now live"


# ---------------------------------------------------------------------------
# Protocol Execution
# ---------------------------------------------------------------------------

def test_create_and_list_protocol_executions() -> None:
    client = TestClient(create_app())
    user_id = _uid("exec")

    protocol = client.post(
        "/api/v1/protocols",
        headers=AUTH,
        json={"user_id": user_id, "name": "Cold plunge protocol"},
    )
    assert protocol.status_code == 200
    protocol_id = protocol.json()["id"]

    exec_resp = client.post(
        f"/api/v1/protocols/{protocol_id}/executions",
        headers=AUTH,
        json={
            "user_id": user_id,
            "protocol_id": protocol_id,
            "executed_at": _now_iso(),
            "completion_status": "completed",
            "notes": "Felt great",
        },
    )
    assert exec_resp.status_code == 200
    execution = exec_resp.json()
    assert execution["protocol_id"] == protocol_id
    assert execution["completion_status"] == "completed"

    listed = client.get(
        f"/api/v1/protocols/{protocol_id}/executions",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) >= 1
    assert items[0]["protocol_id"] == protocol_id


# ---------------------------------------------------------------------------
# Insight CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_insight() -> None:
    client = TestClient(create_app())
    user_id = _uid("ins")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Sleep affects mood",
            "summary": "Mood is consistently higher on days with 7+ hours sleep",
            "confidence": 0.85,
            "status": "candidate",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["title"] == "Sleep affects mood"
    assert payload["status"] == "candidate"
    insight_id = payload["id"]

    fetched = client.get(
        f"/api/v1/insights/{insight_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == insight_id


def test_list_insights() -> None:
    client = TestClient(create_app())
    user_id = _uid("ins")

    for title in ["Insight A", "Insight B"]:
        resp = client.post(
            "/api/v1/insights",
            headers=AUTH,
            json={"user_id": user_id, "title": title, "summary": f"Summary for {title}"},
        )
        assert resp.status_code == 200

    listed = client.get(
        "/api/v1/insights",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_update_insight() -> None:
    client = TestClient(create_app())
    user_id = _uid("ins")

    created = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Tentative insight", "summary": "Initial observation"},
    )
    assert created.status_code == 200
    insight_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/insights/{insight_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active", "confidence": 0.92},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "active"
    assert payload["confidence"] == 0.92


def test_list_insights_filter_by_status() -> None:
    client = TestClient(create_app())
    user_id = _uid("ins")

    # Create one candidate, then promote it to active
    resp_a = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Active insight", "summary": "Confirmed pattern"},
    )
    assert resp_a.status_code == 200
    insight_a_id = resp_a.json()["id"]
    client.put(
        f"/api/v1/insights/{insight_a_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "active"},
    )

    # Create a second that stays candidate
    resp_b = client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={"user_id": user_id, "title": "Still candidate", "summary": "Needs validation"},
    )
    assert resp_b.status_code == 200

    active_only = client.get(
        "/api/v1/insights",
        headers=AUTH,
        params={"user_id": user_id, "status": "active"},
    )
    assert active_only.status_code == 200
    items = active_only.json()
    assert all(i["status"] == "active" for i in items)
    assert any(i["id"] == insight_a_id for i in items)


# ---------------------------------------------------------------------------
# Heuristic CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_heuristic() -> None:
    client = TestClient(create_app())
    user_id = _uid("heur")

    created = client.post(
        "/api/v1/heuristics",
        headers=AUTH,
        json={
            "user_id": user_id,
            "rule": "If sleep < 6h then expect low mood next day",
            "source_type": "validated_pattern",
            "confidence": 0.78,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["rule"] == "If sleep < 6h then expect low mood next day"
    assert payload["active"] is True
    heuristic_id = payload["id"]

    fetched = client.get(
        f"/api/v1/heuristics/{heuristic_id}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == heuristic_id


def test_list_heuristics() -> None:
    client = TestClient(create_app())
    user_id = _uid("heur")

    for rule in ["Rule Alpha", "Rule Beta"]:
        resp = client.post(
            "/api/v1/heuristics",
            headers=AUTH,
            json={"user_id": user_id, "rule": rule},
        )
        assert resp.status_code == 200

    listed = client.get(
        "/api/v1/heuristics",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_list_heuristics_active_only() -> None:
    client = TestClient(create_app())
    user_id = _uid("heur")

    # All heuristics start active=True (per the schema default)
    for rule in ["Active rule 1", "Active rule 2"]:
        resp = client.post(
            "/api/v1/heuristics",
            headers=AUTH,
            json={"user_id": user_id, "rule": rule},
        )
        assert resp.status_code == 200

    # With active_only=true, all should come back
    active = client.get(
        "/api/v1/heuristics",
        headers=AUTH,
        params={"user_id": user_id, "active_only": "true"},
    )
    assert active.status_code == 200
    items = active.json()
    assert len(items) >= 2
    assert all(h["active"] is True for h in items)


# ---------------------------------------------------------------------------
# Search: activities and metrics appear in results
# ---------------------------------------------------------------------------

def test_search_finds_activity() -> None:
    client = TestClient(create_app())
    user_id = _uid("srch")

    client.post(
        "/api/v1/activities",
        headers=AUTH,
        json={
            "user_id": user_id,
            "effective_at": _now_iso(),
            "activity_type": "mobility",
            "title": "Flexibility stretching session",
        },
    )

    results = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "q": "stretching", "type": "activity", "limit": 10},
    )
    assert results.status_code == 200
    payload = results.json()
    assert payload["results"]
    assert all(r["object_type"] == "activity" for r in payload["results"])
    assert any("stretching" in r["snippet"].lower() for r in payload["results"])


def test_search_finds_metric() -> None:
    client = TestClient(create_app())
    user_id = _uid("srch")

    client.post(
        "/api/v1/metrics",
        headers=AUTH,
        json={
            "user_id": user_id,
            "effective_at": _now_iso(),
            "metric_type": "body_weight",
            "value": "185",
            "unit": "lbs",
            "notes": "morning fasted weigh-in",
        },
    )

    results = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "q": "body_weight", "type": "metric_observation", "limit": 10},
    )
    assert results.status_code == 200
    payload = results.json()
    assert payload["results"]
    assert all(r["object_type"] == "metric_observation" for r in payload["results"])


# ---------------------------------------------------------------------------
# FTS5 search across object types
# ---------------------------------------------------------------------------

def test_fts5_search_keyword() -> None:
    client = TestClient(create_app())
    user_id = _uid("fts")

    # Seed an activity
    client.post(
        "/api/v1/activities",
        headers=AUTH,
        json={
            "user_id": user_id,
            "effective_at": _now_iso(),
            "activity_type": "breathwork",
            "title": "Wim Hof breathing protocol",
        },
    )

    # Seed an insight
    client.post(
        "/api/v1/insights",
        headers=AUTH,
        json={
            "user_id": user_id,
            "title": "Unrelated observation",
            "summary": "Nothing about breathing here",
        },
    )

    results = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "q": "breathing", "limit": 25},
    )
    assert results.status_code == 200
    payload = results.json()
    assert payload["results"]
    assert any("breathing" in r["snippet"].lower() for r in payload["results"])


# ---------------------------------------------------------------------------
# Extraction service: chat → activity
# ---------------------------------------------------------------------------

def test_chat_extracts_activity() -> None:
    client = TestClient(create_app())
    user_id = _uid("ext")

    resp = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "did 30 minutes of mobility today, felt loose afterwards",
        },
    )
    assert resp.status_code == 200
    extraction = resp.json()["extraction"]
    assert len(extraction["activity_ids"]) >= 1

    # Verify the activity exists via the list endpoint
    activities = client.get(
        "/api/v1/activities",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert activities.status_code == 200
    items = activities.json()
    assert len(items) >= 1
    assert any(a["id"] in extraction["activity_ids"] for a in items)


# ---------------------------------------------------------------------------
# Extraction service: chat → metric
# ---------------------------------------------------------------------------

def test_chat_extracts_metric() -> None:
    client = TestClient(create_app())
    user_id = _uid("ext")

    resp = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "body weight 185 lbs this morning, feeling good",
        },
    )
    assert resp.status_code == 200
    extraction = resp.json()["extraction"]
    assert len(extraction["metric_ids"]) >= 1

    # Verify the metric exists via the list endpoint
    metrics = client.get(
        "/api/v1/metrics",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert metrics.status_code == 200
    items = metrics.json()
    assert len(items) >= 1
    assert any(m["metric_type"] == "body_weight" for m in items)
    assert any(m["value"] == "185" for m in items)
