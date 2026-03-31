from datetime import date, timedelta
import uuid

from fastapi.testclient import TestClient

from memorychain_api.main import create_app


AUTH = {"X-API-Key": "dev-key"}


def test_health_open() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_required() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/goals", params={"user_id": "sam"})
    assert response.status_code == 401


def test_chat_creates_memory_objects() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": "sam",
            "message": "Sleep 6.5h mood 4/10. todo: send the outline. goal: finish v1 spec",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["conversation_id"]
    assert payload["assistant_message"]
    assert payload["extraction"]["source_document_id"]
    assert payload["extraction"]["journal_entry_id"]
    assert len(payload["extraction"]["task_ids"]) == 1
    assert len(payload["extraction"]["goal_ids"]) == 1


def test_search_filters_by_type_and_keyword() -> None:
    client = TestClient(create_app())
    user_id = f"search_{uuid.uuid4().hex[:8]}"

    chat_response = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "Sleep 7h mood 7/10. todo: outline the search API. goal: ship v1 search",
        },
    )
    assert chat_response.status_code == 200

    response = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "q": "outline", "type": "task", "limit": 10},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["results"]
    assert all(item["object_type"] == "task" for item in payload["results"])
    assert any("outline" in item["snippet"].lower() for item in payload["results"])


def test_search_tag_and_date_filters() -> None:
    client = TestClient(create_app())
    user_id = f"search_{uuid.uuid4().hex[:8]}"

    chat_response = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "today log with tags via chat pipeline",
        },
    )
    assert chat_response.status_code == 200

    tagged = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "type": "journal_entry", "tag": "chat"},
    )
    assert tagged.status_code == 200
    tagged_payload = tagged.json()
    assert tagged_payload["results"]
    assert all("chat" in item["tags"] for item in tagged_payload["results"])

    future_date = (date.today() + timedelta(days=30)).isoformat()
    future = client.get(
        "/api/v1/search",
        headers=AUTH,
        params={"user_id": user_id, "from": future_date, "limit": 10},
    )
    assert future.status_code == 200
    assert future.json()["results"] == []


def test_guided_prompts_returns_bundles() -> None:
    client = TestClient(create_app())
    user_id = f"prompt_{uuid.uuid4().hex[:8]}"

    seed = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "Sleep 7h mood 8/10. todo: ship guided prompts endpoint. goal: improve retrieval UX",
        },
    )
    assert seed.status_code == 200

    response = client.get("/api/v1/prompts", headers=AUTH, params={"user_id": user_id})
    assert response.status_code == 200

    payload = response.json()
    ids = [item["id"] for item in payload["prompts"]]
    assert ids == ["open_tasks", "recent_checkins", "recent_journal", "active_goals"]

    by_id = {item["id"]: item for item in payload["prompts"]}
    assert any(r["object_type"] == "task" for r in by_id["open_tasks"]["results"])
    assert any(r["object_type"] == "daily_checkin" for r in by_id["recent_checkins"]["results"])
    assert any(r["object_type"] == "journal_entry" for r in by_id["recent_journal"]["results"])
    assert any(r["object_type"] == "goal" for r in by_id["active_goals"]["results"])

