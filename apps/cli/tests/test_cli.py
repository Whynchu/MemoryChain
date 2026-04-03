"""Phase 4 tests — CLI commands via Click CliRunner with mocked httpx calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from memorychain_cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Helpers ──────────────────────────────────────────────────
def _mock_response(json_data, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status.return_value = None
    return resp


# ── status command ───────────────────────────────────────────
class TestStatus:
    def test_status_ok(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"status": "ok"})
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "ok" in result.output

    def test_status_connection_error(self, runner: CliRunner) -> None:
        import httpx as _httpx

        with patch("memorychain_cli.client.httpx.get", side_effect=_httpx.ConnectError("refused")):
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "Cannot connect" in result.output


# ── log command ──────────────────────────────────────────────
class TestLog:
    def test_log_basic(self, runner: CliRunner) -> None:
        chat_resp = {
            "conversation_id": "conv-1",
            "assistant_message": "Got it! Logged your morning entry.",
            "assistant_message_id": "msg-1",
            "extraction": {
                "source_document_id": "sd-123",
                "journal_entry_id": "je-456",
                "checkin_id": None,
                "task_ids": [],
                "goal_ids": [],
                "activity_ids": ["act-1"],
                "metric_ids": [],
            },
            "memory_context": [],
        }
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(chat_resp)
            result = runner.invoke(cli, ["log", "-y", "Had a great morning run"])
            assert result.exit_code == 0
            assert "Got it!" in result.output
            assert "Journal Entry" in result.output
            assert "1 Activities" in result.output

    def test_log_no_extractions(self, runner: CliRunner) -> None:
        chat_resp = {
            "conversation_id": "conv-2",
            "assistant_message": "Interesting thought.",
            "assistant_message_id": "msg-2",
            "extraction": {
                "source_document_id": "sd-789",
                "journal_entry_id": None,
                "checkin_id": None,
                "task_ids": [],
                "goal_ids": [],
                "activity_ids": [],
                "metric_ids": [],
            },
            "memory_context": [],
        }
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(chat_resp)
            result = runner.invoke(cli, ["log", "-y", "just thinking out loud"])
            assert result.exit_code == 0
            assert "Source Document" in result.output

    def test_log_connection_error(self, runner: CliRunner) -> None:
        import httpx as _httpx

        with patch("memorychain_cli.client.httpx.post", side_effect=_httpx.ConnectError("refused")):
            result = runner.invoke(cli, ["log", "test"])
            assert result.exit_code == 1
            assert "Cannot connect" in result.output


# ── today command ────────────────────────────────────────────
class TestToday:
    def test_today_with_data(self, runner: CliRunner) -> None:
        checkins = [{"mood_score": 7, "sleep_hours": 7.5, "energy_level": 6, "notes": "Good day"}]
        tasks = [
            {"id": "t-111111111", "title": "Write CLI tests", "status": "in_progress", "due_date": None},
            {"id": "t-222222222", "title": "Done task", "status": "completed", "due_date": None},
        ]
        goals = [
            {"id": "g-111111111", "title": "Ship v1.0", "status": "active", "target_date": "2025-06-01"},
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(checkins),
                _mock_response(tasks),
                _mock_response(goals),
            ]
            result = runner.invoke(cli, ["today"])
            assert result.exit_code == 0
            assert "Mood" in result.output
            assert "7.5" in result.output
            assert "Write CLI tests" in result.output
            assert "Ship v1.0" in result.output
            # Completed task should still appear in raw data but filtered in display
            assert "Done task" not in result.output

    def test_today_empty(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.side_effect = [
                _mock_response([]),  # no checkins
                _mock_response([]),  # no tasks
                _mock_response([]),  # no goals
            ]
            result = runner.invoke(cli, ["today"])
            assert result.exit_code == 0
            assert "No check-in" in result.output


# ── search command ───────────────────────────────────────────
class TestSearch:
    def test_search_results(self, runner: CliRunner) -> None:
        search_data = {
            "results": [
                {
                    "object_type": "journal_entry",
                    "object_id": "je-1",
                    "user_id": "u1",
                    "effective_at": "2025-01-15T10:00:00",
                    "title": "Morning run entry",
                    "snippet": "Went for a 5k run in the park.",
                    "source_document_id": "sd-1",
                    "tags": ["exercise"],
                },
            ]
        }
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(search_data)
            result = runner.invoke(cli, ["search", "running"])
            assert result.exit_code == 0
            assert "1 result" in result.output
            assert "Morning run" in result.output
            assert "exercise" in result.output

    def test_search_empty(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"results": []})
            result = runner.invoke(cli, ["search", "nonexistent"])
            assert result.exit_code == 0
            assert "No results" in result.output


# ── review command ───────────────────────────────────────────
class TestReview:
    def test_review_show_latest(self, runner: CliRunner) -> None:
        review_data = {
            "id": "wr-1",
            "week_label": "2025-W03",
            "summary": "Productive week with consistent exercise.",
            "wins": ["5 workouts completed"],
            "slips": [],
            "open_loops": ["Need to schedule dentist"],
            "insight_mentions": ["Sleep > 7h correlates with high mood"],
            "activity_summary": ["Running: 3x", "Reading: 2x"],
            "metric_highlights": ["Sleep avg 7.5h"],
            "sparse_data_flags": [],
            "notable_entries": [],
            "llm_narrative": None,
            "recommended_next_actions": ["Keep up exercise routine"],
        }
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([review_data])
            result = runner.invoke(cli, ["review"])
            assert result.exit_code == 0
            assert "Productive week" in result.output
            assert "5 workouts" in result.output
            assert "Sleep > 7h" in result.output

    def test_review_generate(self, runner: CliRunner) -> None:
        review_data = {
            "id": "wr-2",
            "week_label": "2025-W04",
            "summary": "Good energy levels this week.",
            "wins": [],
            "slips": [],
            "open_loops": [],
            "insight_mentions": [],
            "activity_summary": [],
            "metric_highlights": [],
            "sparse_data_flags": ["Only 3 checkins this week"],
            "notable_entries": [],
            "llm_narrative": "An interesting pattern emerged this week...",
            "recommended_next_actions": [],
        }
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(review_data)
            result = runner.invoke(cli, ["review", "--generate"])
            assert result.exit_code == 0
            assert "Good energy" in result.output
            assert "Sparse Data" in result.output
            assert "interesting pattern" in result.output

    def test_review_no_reviews(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            result = runner.invoke(cli, ["review"])
            assert result.exit_code == 0
            assert "No reviews yet" in result.output


# ── insights command ─────────────────────────────────────────
class TestInsights:
    def test_insights_list(self, runner: CliRunner) -> None:
        insights_data = [
            {
                "id": "ins-11111111-aaaa-bbbb-cccc-dddddddddddd",
                "title": "Sleep > 7h → mood ≥ 7",
                "status": "candidate",
                "confidence": 0.72,
                "evidence_ids": ["ev1", "ev2", "ev3"],
                "created_at": "2025-01-10T12:00:00",
            },
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(insights_data)
            result = runner.invoke(cli, ["insights"])
            assert result.exit_code == 0
            assert "Sleep > 7h" in result.output
            assert "0.72" in result.output

    def test_insights_with_detect(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post, \
             patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_post.return_value = _mock_response([{"id": "new-insight"}])
            mock_get.return_value = _mock_response([])
            result = runner.invoke(cli, ["insights", "--detect"])
            assert result.exit_code == 0
            assert "1 new insight" in result.output


# ── promote command ──────────────────────────────────────────
class TestPromote:
    def test_promote_success(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "heur-abc12345"})
            result = runner.invoke(cli, ["promote", "ins-11111111"])
            assert result.exit_code == 0
            assert "promoted" in result.output

    def test_promote_not_found(self, runner: CliRunner) -> None:
        import httpx as _httpx

        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not found"
        resp.json.return_value = {"detail": "Not found"}
        resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "404", request=MagicMock(), response=resp
        )
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = resp
            result = runner.invoke(cli, ["promote", "ins-nonexist"])
            assert result.exit_code == 1
            assert "not found" in result.output.lower()


# ── reject / accept ─────────────────────────────────────────
class TestStatusTransitions:
    def test_reject(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.put") as mock_put:
            mock_put.return_value = _mock_response({"id": "ins-1", "status": "rejected"})
            result = runner.invoke(cli, ["reject", "ins-1"])
            assert result.exit_code == 0
            assert "rejected" in result.output

    def test_accept(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.put") as mock_put:
            mock_put.return_value = _mock_response({"id": "ins-1", "status": "active"})
            result = runner.invoke(cli, ["accept", "ins-1"])
            assert result.exit_code == 0
            assert "active" in result.output


# ── goals command ────────────────────────────────────────────
class TestGoals:
    def test_goals_list(self, runner: CliRunner) -> None:
        goals_data = [
            {"id": "g-11111111", "title": "Ship v1.0", "status": "active", "target_date": "2025-06-01"},
            {"id": "g-22222222", "title": "Learn Rust", "status": "active", "target_date": None},
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(goals_data)
            result = runner.invoke(cli, ["goals"])
            assert result.exit_code == 0
            assert "Ship v1.0" in result.output
            assert "Learn Rust" in result.output

    def test_goals_empty(self, runner: CliRunner) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            result = runner.invoke(cli, ["goals"])
            assert result.exit_code == 0
            assert "No goals" in result.output


# ── tasks command ────────────────────────────────────────────
class TestTasks:
    def test_tasks_filters_completed(self, runner: CliRunner) -> None:
        tasks_data = [
            {"id": "t-111", "title": "Open task", "status": "in_progress", "priority": "high", "due_date": None},
            {"id": "t-222", "title": "Completed task", "status": "completed", "priority": "low", "due_date": None},
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(tasks_data)
            result = runner.invoke(cli, ["tasks"])
            assert result.exit_code == 0
            assert "Open task" in result.output
            assert "Completed task" not in result.output

    def test_tasks_show_all(self, runner: CliRunner) -> None:
        tasks_data = [
            {"id": "t-111", "title": "Open task", "status": "in_progress", "priority": "high", "due_date": None},
            {"id": "t-222", "title": "Completed task", "status": "completed", "priority": "low", "due_date": None},
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(tasks_data)
            result = runner.invoke(cli, ["tasks", "--all"])
            assert result.exit_code == 0
            assert "Open task" in result.output
            assert "Completed task" in result.output


# ── heuristics command ───────────────────────────────────────
class TestHeuristics:
    def test_heuristics_list(self, runner: CliRunner) -> None:
        heur_data = [
            {"id": "h-11111111", "rule_text": "Sleep > 7h for best mood", "source_type": "validated_pattern", "is_active": True},
        ]
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(heur_data)
            result = runner.invoke(cli, ["heuristics"])
            assert result.exit_code == 0
            assert "Sleep > 7h" in result.output


# ── version ──────────────────────────────────────────────────
class TestVersion:
    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output
