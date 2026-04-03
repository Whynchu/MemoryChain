from datetime import date, datetime, timedelta, timezone
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
        json={"user_id": user_id, "message": "Slept 7h, mood 8/10. Did a detailed log with tags via the chat pipeline for testing purposes"},
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
    assert ids == ["open_tasks", "recent_checkins", "recent_journal", "active_goals", "attendance_this_week"]

    by_id = {item["id"]: item for item in payload["prompts"]}
    assert any(r["object_type"] == "task" for r in by_id["open_tasks"]["results"])
    assert any(r["object_type"] == "daily_checkin" for r in by_id["recent_checkins"]["results"])
    assert any(r["object_type"] == "journal_entry" for r in by_id["recent_journal"]["results"])
    assert any(r['object_type'] == 'goal' for r in by_id['active_goals']['results'])
    attendance = by_id['attendance_this_week']
    assert attendance['metadata']['window_days'] == 7
    assert 'adherence_rate' in attendance['metadata']



def test_update_goal() -> None:
    client = TestClient(create_app())
    user_id = f"goal_{uuid.uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/goals",
        headers=AUTH,
        json={"user_id": user_id, "title": "Ship backend", "status": "active", "priority": "medium"},
    )
    assert created.status_code == 200
    goal_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/goals/{goal_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "completed", "priority": "high"},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "completed"
    assert payload["priority"] == "high"


def test_update_task_status_sets_and_clears_completed_at() -> None:
    client = TestClient(create_app())
    user_id = f"task_{uuid.uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/tasks",
        headers=AUTH,
        json={"user_id": user_id, "title": "Finish tests", "status": "todo"},
    )
    assert created.status_code == 200
    task_id = created.json()["id"]

    done = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "done"},
    )
    assert done.status_code == 200
    done_payload = done.json()
    assert done_payload["status"] == "done"
    assert done_payload["completed_at"] is not None

    reopened = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "todo"},
    )
    assert reopened.status_code == 200
    reopened_payload = reopened.json()
    assert reopened_payload["status"] == "todo"
    assert reopened_payload["completed_at"] is None


def test_prompt_cycle_lifecycle() -> None:
    client = TestClient(create_app())
    user_id = f"cycle_{uuid.uuid4().hex[:8]}"

    seed = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={"user_id": user_id, "message": "Slept 8h, mood 7/10. Seed source for prompt response"},
    )
    assert seed.status_code == 200
    source_id = seed.json()["extraction"]["source_document_id"]

    scheduled = client.post(
        "/api/v1/prompt-cycles/schedule",
        headers=AUTH,
        json={
            "user_id": user_id,
            "cycle_date": date.today().isoformat(),
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert scheduled.status_code == 200
    cycle = scheduled.json()
    cycle_id = cycle["id"]
    assert cycle["status"] == "pending"

    sent = client.post(
        f"/api/v1/prompt-cycles/{cycle_id}/send",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert sent.status_code == 200
    assert sent.json()["sent_at"] is not None

    viewed = client.post(
        f"/api/v1/prompt-cycles/{cycle_id}/viewed",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert viewed.status_code == 200
    assert viewed.json()["status"] == "viewed_no_response"

    responded = client.post(
        f"/api/v1/prompt-cycles/{cycle_id}/responded",
        headers=AUTH,
        json={"user_id": user_id, "response_source_document_id": source_id},
    )
    assert responded.status_code == 200
    payload = responded.json()
    assert payload["status"] == "responded"
    assert payload["response_source_document_id"] == source_id
    assert payload["response_at"] is not None

    listed = client.get(
        "/api/v1/prompt-cycles",
        headers=AUTH,
        params={"user_id": user_id, "from": date.today().isoformat()},
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_prompt_cycle_invalid_transition_returns_conflict() -> None:
    client = TestClient(create_app())
    user_id = f"cycle_{uuid.uuid4().hex[:8]}"

    scheduled = client.post(
        "/api/v1/prompt-cycles/schedule",
        headers=AUTH,
        json={
            "user_id": user_id,
            "cycle_date": date.today().isoformat(),
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert scheduled.status_code == 200
    cycle_id = scheduled.json()["id"]

    missed = client.post(
        f"/api/v1/prompt-cycles/{cycle_id}/missed",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert missed.status_code == 200
    assert missed.json()["status"] == "missed"

    invalid = client.post(
        f"/api/v1/prompt-cycles/{cycle_id}/viewed",
        headers=AUTH,
        json={"user_id": user_id},
    )
    assert invalid.status_code == 409




def test_engagement_summary_metrics() -> None:
    client = TestClient(create_app())
    user_id = f"eng_{uuid.uuid4().hex[:8]}"

    seed = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={"user_id": user_id, "message": "Slept 6h, mood 9/10. Seed source for engagement summary"},
    )
    assert seed.status_code == 200
    source_id = seed.json()["extraction"]["source_document_id"]

    base_date = date.today() - timedelta(days=3)

    def schedule_cycle(day_offset: int) -> str:
        cycle_date = (base_date + timedelta(days=day_offset))
        scheduled_for = datetime.now(timezone.utc).replace(
            year=cycle_date.year,
            month=cycle_date.month,
            day=cycle_date.day,
            hour=12,
            minute=0,
            second=0,
            microsecond=0,
        )
        scheduled = client.post(
            "/api/v1/prompt-cycles/schedule",
            headers=AUTH,
            json={
                "user_id": user_id,
                "cycle_date": cycle_date.isoformat(),
                "scheduled_for": scheduled_for.isoformat(),
            },
        )
        assert scheduled.status_code == 200
        return scheduled.json()["id"]

    cycle_1 = schedule_cycle(0)
    send_1_at = datetime.now(timezone.utc)
    response_1_at = send_1_at + timedelta(minutes=10)
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_1}/send",
        headers=AUTH,
        json={"user_id": user_id, "event_at": send_1_at.isoformat()},
    ).status_code == 200
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_1}/responded",
        headers=AUTH,
        json={"user_id": user_id, "response_source_document_id": source_id, "event_at": response_1_at.isoformat()},
    ).status_code == 200

    cycle_2 = schedule_cycle(1)
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_2}/viewed",
        headers=AUTH,
        json={"user_id": user_id},
    ).status_code == 200
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_2}/responded",
        headers=AUTH,
        json={"user_id": user_id, "response_source_document_id": source_id},
    ).status_code == 200

    cycle_3 = schedule_cycle(2)
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_3}/missed",
        headers=AUTH,
        json={"user_id": user_id},
    ).status_code == 200

    cycle_4 = schedule_cycle(3)
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_4}/viewed",
        headers=AUTH,
        json={"user_id": user_id},
    ).status_code == 200

    summary = client.get(
        "/api/v1/engagement/summary",
        headers=AUTH,
        params={"user_id": user_id, "window": "7d"},
    )
    assert summary.status_code == 200
    payload = summary.json()

    assert payload["total_cycles"] == 4
    assert payload["responded_cycles"] == 2
    assert payload["missed_cycles"] == 1
    assert payload["viewed_no_response_cycles"] == 1
    assert payload["pending_cycles"] == 0
    assert payload["adherence_rate"] == 0.5
    assert payload["open_without_entry_rate"] == 0.25
    assert payload["longest_nonresponse_streak_days"] == 2
    assert payload["streak_resume_count"] >= 1
    assert payload["avg_response_delay_minutes"] is not None




def test_weekly_review_includes_engagement_signals() -> None:
    client = TestClient(create_app())
    user_id = f"wr_{uuid.uuid4().hex[:8]}"

    # Seed at least one source/check-in via chat extraction.
    seed = client.post(
        "/api/v1/chat",
        headers=AUTH,
        json={
            "user_id": user_id,
            "message": "Sleep 7h mood 6/10. todo: review weekly plan. goal: maintain consistency",
        },
    )
    assert seed.status_code == 200
    source_id = seed.json()["extraction"]["source_document_id"]

    week_end = date.today()
    week_start = week_end - timedelta(days=6)

    # One responded cycle.
    cycle_1_date = week_start + timedelta(days=1)
    scheduled_1 = client.post(
        "/api/v1/prompt-cycles/schedule",
        headers=AUTH,
        json={
            "user_id": user_id,
            "cycle_date": cycle_1_date.isoformat(),
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert scheduled_1.status_code == 200
    cycle_1_id = scheduled_1.json()["id"]
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_1_id}/send",
        headers=AUTH,
        json={"user_id": user_id, "event_at": datetime.now(timezone.utc).isoformat()},
    ).status_code == 200
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_1_id}/responded",
        headers=AUTH,
        json={
            "user_id": user_id,
            "response_source_document_id": source_id,
            "event_at": datetime.now(timezone.utc).isoformat(),
        },
    ).status_code == 200

    # One missed cycle.
    cycle_2_date = week_start + timedelta(days=2)
    scheduled_2 = client.post(
        "/api/v1/prompt-cycles/schedule",
        headers=AUTH,
        json={
            "user_id": user_id,
            "cycle_date": cycle_2_date.isoformat(),
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert scheduled_2.status_code == 200
    cycle_2_id = scheduled_2.json()["id"]
    assert client.post(
        f"/api/v1/prompt-cycles/{cycle_2_id}/missed",
        headers=AUTH,
        json={"user_id": user_id, "event_at": datetime.now(timezone.utc).isoformat()},
    ).status_code == 200

    review = client.post(
        "/api/v1/weekly-reviews/generate",
        headers=AUTH,
        json={
            "user_id": user_id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
    )
    assert review.status_code == 200
    payload = review.json()

    assert "Prompt adherence:" in payload["summary"]
    assert any("Missed" in item for item in payload["slips"])



def test_audit_log_records_goal_and_task_updates() -> None:
    client = TestClient(create_app())
    user_id = f"audit_{uuid.uuid4().hex[:8]}"

    goal = client.post(
        "/api/v1/goals",
        headers=AUTH,
        json={"user_id": user_id, "title": "Improve consistency", "status": "active", "priority": "medium"},
    )
    assert goal.status_code == 200
    goal_id = goal.json()["id"]

    task = client.post(
        "/api/v1/tasks",
        headers=AUTH,
        json={"user_id": user_id, "title": "Daily check-in", "status": "todo", "priority": "medium"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]

    goal_update = client.put(
        f"/api/v1/goals/{goal_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "completed", "priority": "high"},
    )
    assert goal_update.status_code == 200

    task_update = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "in_progress", "description": "Started"},
    )
    assert task_update.status_code == 200

    logs = client.get(
        "/api/v1/audit-log",
        headers=AUTH,
        params={"user_id": user_id, "limit": 10, "offset": 0},
    )
    assert logs.status_code == 200
    payload = logs.json()
    assert len(payload) >= 2

    entity_types = {entry["entity_type"] for entry in payload}
    assert "goal" in entity_types
    assert "task" in entity_types

    goal_entry = next(entry for entry in payload if entry["entity_type"] == "goal")
    assert goal_entry["entity_id"] == goal_id
    assert "status" in goal_entry["changed_fields"]
    assert goal_entry["before"]["status"] == "active"
    assert goal_entry["after"]["status"] == "completed"

    task_entry = next(entry for entry in payload if entry["entity_type"] == "task")
    assert task_entry["entity_id"] == task_id
    assert "status" in task_entry["changed_fields"]
    assert task_entry["after"]["status"] == "in_progress"


def test_audit_log_rollback_restores_goal_state() -> None:
    client = TestClient(create_app())
    user_id = f"rollback_{uuid.uuid4().hex[:8]}"

    goal = client.post(
        "/api/v1/goals",
        headers=AUTH,
        json={"user_id": user_id, "title": "Keep momentum", "status": "active", "priority": "medium"},
    )
    assert goal.status_code == 200
    goal_id = goal.json()["id"]

    first_update = client.put(
        f"/api/v1/goals/{goal_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "completed", "priority": "high"},
    )
    assert first_update.status_code == 200

    second_update = client.put(
        f"/api/v1/goals/{goal_id}",
        headers=AUTH,
        params={"user_id": user_id},
        json={"status": "paused", "priority": "low"},
    )
    assert second_update.status_code == 200

    logs = client.get(
        "/api/v1/audit-log",
        headers=AUTH,
        params={"user_id": user_id, "limit": 10, "offset": 0},
    )
    assert logs.status_code == 200
    update_to_rollback = next(
        entry
        for entry in logs.json()
        if entry["entity_type"] == "goal"
        and entry["entity_id"] == goal_id
        and entry["action"] == "update"
        and entry["after"]["status"] == "paused"
    )

    rollback = client.post(
        f"/api/v1/audit-log/{update_to_rollback['id']}/rollback",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert rollback.status_code == 200
    rollback_payload = rollback.json()
    assert rollback_payload["action"] == "rollback"
    assert rollback_payload["entity_type"] == "goal"
    assert rollback_payload["entity_id"] == goal_id
    assert rollback_payload["after"]["status"] == "completed"

    goals = client.get(
        "/api/v1/goals",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert goals.status_code == 200
    restored_goal = next(item for item in goals.json() if item["id"] == goal_id)
    assert restored_goal["status"] == "completed"
    assert restored_goal["priority"] == "high"


def test_goal_detail_and_pagination() -> None:
    client = TestClient(create_app())
    user_id = f"goal_page_{uuid.uuid4().hex[:8]}"

    goal_ids: list[str] = []
    for idx in range(3):
        created = client.post(
            "/api/v1/goals",
            headers=AUTH,
            json={"user_id": user_id, "title": f"Goal {idx}", "status": "active", "priority": "medium"},
        )
        assert created.status_code == 200
        goal_ids.append(created.json()["id"])

    first_page = client.get(
        "/api/v1/goals",
        headers=AUTH,
        params={"user_id": user_id, "limit": 2, "offset": 0},
    )
    assert first_page.status_code == 200
    first_items = first_page.json()
    assert len(first_items) == 2

    second_page = client.get(
        "/api/v1/goals",
        headers=AUTH,
        params={"user_id": user_id, "limit": 2, "offset": 2},
    )
    assert second_page.status_code == 200
    second_items = second_page.json()
    assert len(second_items) == 1

    detail = client.get(
        f"/api/v1/goals/{goal_ids[0]}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == goal_ids[0]

    missing = client.get(
        "/api/v1/goals/goal_missing",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert missing.status_code == 404


def test_task_detail_and_pagination() -> None:
    client = TestClient(create_app())
    user_id = f"task_page_{uuid.uuid4().hex[:8]}"

    task_ids: list[str] = []
    for idx in range(3):
        created = client.post(
            "/api/v1/tasks",
            headers=AUTH,
            json={"user_id": user_id, "title": f"Task {idx}", "status": "todo"},
        )
        assert created.status_code == 200
        task_ids.append(created.json()["id"])

    first_page = client.get(
        "/api/v1/tasks",
        headers=AUTH,
        params={"user_id": user_id, "limit": 2, "offset": 0},
    )
    assert first_page.status_code == 200
    first_items = first_page.json()
    assert len(first_items) == 2

    second_page = client.get(
        "/api/v1/tasks",
        headers=AUTH,
        params={"user_id": user_id, "limit": 2, "offset": 2},
    )
    assert second_page.status_code == 200
    second_items = second_page.json()
    assert len(second_items) == 1

    detail = client.get(
        f"/api/v1/tasks/{task_ids[0]}",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == task_ids[0]

    missing = client.get(
        "/api/v1/tasks/task_missing",
        headers=AUTH,
        params={"user_id": user_id},
    )
    assert missing.status_code == 404


def test_questionnaire_template_crud() -> None:
    """Test questionnaire template CRUD operations."""
    client = TestClient(create_app())
    user_id = f"q_user_{uuid.uuid4().hex[:8]}"
    
    # Create a template
    template_data = {
        "user_id": user_id,
        "name": "Morning Check-in",
        "description": "Daily morning questionnaire",
        "questions": [
            {
                "id": "sleep_hours",
                "question_text": "How many hours did you sleep?",
                "question_type": "numeric",
                "min_value": 0,
                "max_value": 12,
                "required": True
            },
            {
                "id": "mood",
                "question_text": "How's your mood today?",
                "question_type": "scale",
                "min_value": 1,
                "max_value": 10,
                "required": True
            }
        ],
        "target_objects": ["daily_checkin"]
    }
    
    # Create template
    create_response = client.post("/api/v1/questionnaires/templates", headers=AUTH, json=template_data)
    assert create_response.status_code == 200
    template = create_response.json()
    assert template["name"] == "Morning Check-in"
    assert len(template["questions"]) == 2
    template_id = template["id"]
    
    # List templates
    list_response = client.get(f"/api/v1/questionnaires/templates?user_id={user_id}", headers=AUTH)
    assert list_response.status_code == 200
    templates = list_response.json()
    assert len(templates) >= 1
    assert any(t["id"] == template_id for t in templates)
    
    # Get specific template
    get_response = client.get(f"/api/v1/questionnaires/templates/{template_id}?user_id={user_id}", headers=AUTH)
    assert get_response.status_code == 200
    retrieved_template = get_response.json()
    assert retrieved_template["id"] == template_id
    assert retrieved_template["name"] == "Morning Check-in"


def test_answer_parser() -> None:
    """Test answer parsing for different question types."""
    from memorychain_api.services.answer_parser import parse_answer, AnswerParsingError
    
    # Test numeric parsing
    assert parse_answer("7", "numeric") == 7.0
    assert parse_answer("7.5", "numeric") == 7.5
    assert parse_answer("seven", "numeric") == 7.0
    assert parse_answer("~7 hours", "numeric") == 7.0
    
    # Test scale parsing
    assert parse_answer("8/10", "scale", min_value=1, max_value=10) == 8
    assert parse_answer("8 out of 10", "scale", min_value=1, max_value=10) == 8
    assert parse_answer("8", "scale", min_value=1, max_value=10) == 8
    
    # Test boolean parsing
    assert parse_answer("yes", "boolean") == True
    assert parse_answer("no", "boolean") == False
    assert parse_answer("true", "boolean") == True
    assert parse_answer("false", "boolean") == False
    
    # Test choice parsing
    choices = ["good", "okay", "bad"]
    assert parse_answer("good", "choice", choices=choices) == "good"
    assert parse_answer("ok", "choice", choices=choices) == "okay"  # partial match
    
    # Test text parsing
    assert parse_answer("This is some text", "text") == "This is some text"
    
    # Test error cases
    try:
        parse_answer("invalid", "numeric")
        assert False, "Should have raised AnswerParsingError"
    except AnswerParsingError:
        pass


def test_questionnaire_chat_flow() -> None:
    """Test questionnaire integration with chat flow."""
    client = TestClient(create_app())
    user_id = f"q_chat_{uuid.uuid4().hex[:8]}"
    
    # First create a template
    template_data = {
        "user_id": user_id,
        "name": "morning_checkin", 
        "description": "Morning check-in",
        "questions": [
            {
                "id": "sleep",
                "question_text": "How many hours did you sleep?",
                "question_type": "numeric",
                "min_value": 0,
                "max_value": 12,
                "required": True
            },
            {
                "id": "mood",
                "question_text": "How's your mood? (1-10)",
                "question_type": "scale", 
                "min_value": 1,
                "max_value": 10,
                "required": True
            }
        ],
        "target_objects": ["daily_checkin"]
    }
    
    create_response = client.post("/api/v1/questionnaires/templates", headers=AUTH, json=template_data)
    assert create_response.status_code == 200
    
    # Start questionnaire via chat command
    chat_data = {"user_id": user_id, "message": "/morning"}
    start_response = client.post("/api/v1/chat", headers=AUTH, json=chat_data)
    assert start_response.status_code == 200
    
    chat_result = start_response.json()
    assert "morning_checkin" in chat_result["assistant_message"]  # Template name, not description
    assert "How many hours did you sleep?" in chat_result["assistant_message"]
    conversation_id = chat_result["conversation_id"]
    
    # Answer first question
    answer1_data = {"user_id": user_id, "message": "7.5", "conversation_id": conversation_id}
    answer1_response = client.post("/api/v1/chat", headers=AUTH, json=answer1_data)
    assert answer1_response.status_code == 200
    
    answer1_result = answer1_response.json()
    assert "How's your mood?" in answer1_result["assistant_message"]
    assert "Question 2 of 2" in answer1_result["assistant_message"]
    
    # Answer second question
    answer2_data = {"user_id": user_id, "message": "8", "conversation_id": conversation_id}
    answer2_response = client.post("/api/v1/chat", headers=AUTH, json=answer2_data)
    assert answer2_response.status_code == 200
    
    answer2_result = answer2_response.json()
    assert "completed" in answer2_result["assistant_message"].lower()
    assert "summary" in answer2_result["assistant_message"].lower()


# ---------------------------------------------------------------------------
# WHYNN parser + extractor tests
# ---------------------------------------------------------------------------

from memorychain_api.services.whynn_parser import split_entries, parse_entry
from memorychain_api.services.whynn_extractor import (
    extract_system_metrics,
    extract_breathwork_metrics,
    extract_training,
    extract_nutrition,
    extract_entry,
)


SAMPLE_COMPREHENSIVE = """April 15, 2025

SYSTEM METRICS:
    \u2022 Morning Body Weight: ~137.2 lbs (estimated AM)
    \u2022 Total Sleep: 7\u20138 hrs (minor interruption)
    \u2022 Sleep Quality: 8/10
    \u2022 Mood: 6\u20137/10 (minor emotional turbulence)
    \u2022 Energy: 7\u20138/10 (slight morning grogginess)
    \u2022 Immediate Thoughts: Conflict processing

BREATHWORK & PHYSICAL METRICS:
    \u2022 CO? Hold: 31.22 seconds (Post-Gate)
    \u2022 Max Expiratory Pressure: [Not recorded]

TRAINING EXECUTION:
    \u2022 Training Session Type: Outdoor Tempo Run
    \u2022 Session Notes:
        \u25e6 Distance: 5.09 km
        \u25e6 Duration: 45:26
        \u25e6 Average HR: 144 bpm
        \u25e6 Max HR: 183 bpm
        \u25e6 Total Strikes: 488

NUTRITION & HYDRATION:
    \u2022 Total Hydration: ~165 oz

BUFFS TRIGGERED:
    \u2022 Liquid Core II (Hydration)
    \u2022 Burn Discipline II

XP AWARDS:
    \u2022 Sprint Phase Completion: +25 XP
    \u2022 TOTAL XP GAINED: +65 XP

SYSTEM NOTES:
    Trained through fatigue, managed emotional spikes.

\u2022\u2022 SIGN-OFF:
Logged by: Patternborn Sovereign
"""


SAMPLE_SPARSE = """April 7, 2025

SYSTEM METRICS:
    \u2022 Morning Body Weight: [Not recorded]
    \u2022 Total Sleep: [Not recorded]
    \u2022 Sleep Quality: [Not recorded]
    \u2022 Mood: [Not recorded]
    \u2022 Energy: [Not recorded]

BREATHWORK & PHYSICAL METRICS:
    \u2022 CO? Hold: [Not recorded]

TRAINING EXECUTION:
    \u2022 Training Session Type: Indoor Engine Flow + High Volume Bagwork
    \u2022 Session Notes:
        \u25e6 Total Strikes: 488

NUTRITION & HYDRATION:
    \u2022 Total Hydration: ~140 oz water + IV

SYSTEM NOTES:
    Trained in solitude.
"""


SAMPLE_NUMERIC_VARIANTS = """April 18, 2025

SYSTEM METRICS:
    \u2022 Morning Body Weight: 138.1 lbs (underwear + shirt)
    \u2022 Total Sleep: 8 hours (5 core + 3 hr nap)
    \u2022 Sleep Quality: 7/10
    \u2022 Mood: 8/10 (excited, training focus)
    \u2022 Energy: 8/10

BREATHWORK & PHYSICAL METRICS:
    \u2022 Max CO? Hold: 43.15 seconds (non-formal trial)

TRAINING EXECUTION:
    \u2022 Training Session Type: Heavy Bag Session
    \u2022 Session Notes:
        \u25e6 Total Strikes: 208

NUTRITION & HYDRATION:
    \u2022 Total Hydration: 161 oz (balanced with salt/fuel intake)
"""


SAMPLE_RANGE_NO_SLASH = """April 19, 2025

SYSTEM METRICS:
    \u2022 Morning Body Weight: 138.8 lbs (T-shirt & underwear)
    \u2022 Total Sleep: 8 hours (5 core + 3 hr nap)
    \u2022 Sleep Quality: 8\u20139
    \u2022 Mood: 6\u20137
    \u2022 Energy: 8\u20139

BREATHWORK & PHYSICAL METRICS:
    \u2022 CO? Hold: [Not recorded]

TRAINING EXECUTION:
    \u2022 Training Session Type: Recovery Mobility
    \u2022 Session Notes: Light mobility work only.

NUTRITION & HYDRATION:
    \u2022 Total Hydration: 160 oz
"""


SAMPLE_DESCRIPTIVE_MOOD = """April 13, 2025

SYSTEM METRICS:
    \u2022 Morning Body Weight: [Not recorded]
    \u2022 Total Sleep: [Not recorded]
    \u2022 Mood: Emotional pressure (tax-related) managed to stability
    \u2022 Energy: Stable through tactical cycles

BREATHWORK & PHYSICAL METRICS:
    \u2022 CO? Hold: [Not recorded]

TRAINING EXECUTION:
    \u2022 Training Session Type: Recovery Day

NUTRITION & HYDRATION:
    \u2022 Total Hydration: ~133 oz
"""


def test_whynn_parser_split_entries():
    """split_entries correctly finds date headers."""
    text = SAMPLE_COMPREHENSIVE + "\n\n" + SAMPLE_SPARSE
    entries = split_entries(text)
    assert len(entries) == 2
    assert "April 15, 2025" in entries[0]
    assert "April 7, 2025" in entries[1]


def test_whynn_parser_parse_entry_date():
    """parse_entry correctly parses date and section names."""
    entry = parse_entry(SAMPLE_COMPREHENSIVE)
    assert entry.date == date(2025, 4, 15)
    assert entry.raw_date == "April 15, 2025"
    assert "SYSTEM METRICS" in entry.sections
    assert "TRAINING EXECUTION" in entry.sections
    assert "BREATHWORK & PHYSICAL METRICS" in entry.sections
    assert "NUTRITION & HYDRATION" in entry.sections


def test_whynn_extractor_comprehensive():
    """Comprehensive entry: all key fields extracted correctly."""
    entry = parse_entry(SAMPLE_COMPREHENSIVE)
    sm = extract_system_metrics(entry.sections["SYSTEM METRICS"])
    bw = extract_breathwork_metrics(entry.sections["BREATHWORK & PHYSICAL METRICS"])
    tr = extract_training(entry.sections["TRAINING EXECUTION"])
    nu = extract_nutrition(entry.sections["NUTRITION & HYDRATION"])

    # System metrics
    assert sm.body_weight_lbs == pytest.approx(137.2)
    assert sm.sleep_hours == pytest.approx(7.0)  # lower bound of 7–8
    assert sm.sleep_quality == pytest.approx(8.0)
    assert sm.mood == pytest.approx(6.0)          # lower bound of 6–7
    assert sm.energy == pytest.approx(7.0)
    assert sm.immediate_thoughts == "Conflict processing"

    # Breathwork
    assert bw.co2_hold_seconds == pytest.approx(31.22)

    # Training
    assert tr.session_type == "Outdoor Tempo Run"
    assert tr.distance_km == pytest.approx(5.09)
    assert tr.duration_minutes == pytest.approx(45 + 26 / 60, rel=0.01)
    assert tr.avg_hr_bpm == 144
    assert tr.max_hr_bpm == 183
    assert tr.total_strikes == 488

    # Nutrition
    assert nu.hydration_oz == pytest.approx(165.0)


def test_whynn_extractor_sparse():
    """Sparse entry: [Not recorded] fields return None."""
    entry = parse_entry(SAMPLE_SPARSE)
    sm = extract_system_metrics(entry.sections["SYSTEM METRICS"])
    bw = extract_breathwork_metrics(entry.sections["BREATHWORK & PHYSICAL METRICS"])
    nu = extract_nutrition(entry.sections["NUTRITION & HYDRATION"])

    assert sm.sleep_hours is None
    assert sm.mood is None
    assert sm.energy is None
    assert sm.body_weight_lbs is None
    assert bw.co2_hold_seconds is None
    assert nu.hydration_oz == pytest.approx(140.0)


def test_whynn_extractor_numeric_variants():
    """Handles integer-only mood/energy, plain hours sleep, parenthetical notes."""
    entry = parse_entry(SAMPLE_NUMERIC_VARIANTS)
    sm = extract_system_metrics(entry.sections["SYSTEM METRICS"])
    bw = extract_breathwork_metrics(entry.sections["BREATHWORK & PHYSICAL METRICS"])
    nu = extract_nutrition(entry.sections["NUTRITION & HYDRATION"])
    tr = extract_training(entry.sections["TRAINING EXECUTION"])

    assert sm.body_weight_lbs == pytest.approx(138.1)
    assert sm.sleep_hours == pytest.approx(8.0)
    assert sm.sleep_quality == pytest.approx(7.0)
    assert sm.mood == pytest.approx(8.0)
    assert sm.energy == pytest.approx(8.0)
    assert bw.co2_hold_seconds == pytest.approx(43.15)
    assert nu.hydration_oz == pytest.approx(161.0)
    assert tr.total_strikes == 208


def test_whynn_extractor_range_no_slash():
    """Handles 'X–Y' ranges without /10 denominator."""
    entry = parse_entry(SAMPLE_RANGE_NO_SLASH)
    sm = extract_system_metrics(entry.sections["SYSTEM METRICS"])

    assert sm.body_weight_lbs == pytest.approx(138.8)
    assert sm.sleep_hours == pytest.approx(8.0)
    assert sm.sleep_quality == pytest.approx(8.0)
    assert sm.mood == pytest.approx(6.0)
    assert sm.energy == pytest.approx(8.0)


def test_whynn_extractor_descriptive_mood():
    """Descriptive mood/energy text → None (not a number)."""
    entry = parse_entry(SAMPLE_DESCRIPTIVE_MOOD)
    sm = extract_system_metrics(entry.sections["SYSTEM METRICS"])

    assert sm.mood is None
    assert sm.energy is None
    # Hydration should still work
    nu = extract_nutrition(entry.sections["NUTRITION & HYDRATION"])
    assert nu.hydration_oz == pytest.approx(133.0)


def test_whynn_extract_entry_full():
    """extract_entry top-level produces correct ExtractedWhynnEntry."""
    from memorychain_api.services.whynn_extractor import extract_entry as do_extract
    entry = parse_entry(SAMPLE_COMPREHENSIVE)
    result = do_extract(entry)

    assert result.system.body_weight_lbs == pytest.approx(137.2)
    assert result.breathwork.co2_hold_seconds == pytest.approx(31.22)
    assert result.training.total_strikes == 488
    assert result.nutrition.hydration_oz == pytest.approx(165.0)
    assert result.xp_total == 65
    assert len(result.buffs) == 2
    assert result.system_notes is not None and "fatigue" in result.system_notes.lower()


import pytest
