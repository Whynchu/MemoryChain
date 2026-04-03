"""Tests for the interactive REPL mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from memorychain_cli.repl import _ExitREPL, _handle_chat, _handle_slash


def _mock_response(json_data, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status.return_value = None
    return resp


# ── Slash command dispatch ───────────────────────────────────
class TestSlashDispatch:
    def test_help_does_not_crash(self, capsys) -> None:
        conv = _handle_slash("/help", None)
        assert conv is None  # unchanged

    def test_quit_raises_exit(self) -> None:
        with pytest.raises(_ExitREPL):
            _handle_slash("/quit", None)

    def test_exit_raises_exit(self) -> None:
        with pytest.raises(_ExitREPL):
            _handle_slash("/exit", None)

    def test_unknown_command(self, capsys) -> None:
        conv = _handle_slash("/foobar", None)
        assert conv is None

    def test_today(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.side_effect = [
                _mock_response([{"mood_score": 7, "sleep_hours": 7, "energy_level": 6, "notes": ""}]),
                _mock_response([]),
                _mock_response([]),
            ]
            conv = _handle_slash("/today", None)
            assert conv is None
            assert mock_get.call_count == 3

    def test_search_no_arg(self, capsys) -> None:
        conv = _handle_slash("/search", None)
        assert conv is None

    def test_search_with_query(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"results": []})
            conv = _handle_slash("/search running", None)
            assert conv is None

    def test_insights_list(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            conv = _handle_slash("/insights", None)
            assert conv is None

    def test_detect(self) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post, \
             patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_post.return_value = _mock_response([])
            mock_get.return_value = _mock_response([])
            conv = _handle_slash("/detect", None)
            assert conv is None

    def test_goals(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            _handle_slash("/goals", None)

    def test_tasks(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            _handle_slash("/tasks", None)

    def test_heuristics(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([])
            _handle_slash("/heuristics", None)

    def test_status(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"status": "ok"})
            _handle_slash("/status", None)

    def test_review_show(self) -> None:
        with patch("memorychain_cli.client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response([{
                "id": "wr-1", "week_label": "W01", "summary": "Good week",
                "wins": [], "slips": [], "open_loops": [],
                "insight_mentions": [], "activity_summary": [],
                "metric_highlights": [], "sparse_data_flags": [],
                "notable_entries": [], "llm_narrative": None,
                "recommended_next_actions": [],
            }])
            _handle_slash("/review", None)

    def test_review_generate(self) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({
                "id": "wr-2", "week_label": "W02", "summary": "Generated",
                "wins": [], "slips": [], "open_loops": [],
                "insight_mentions": [], "activity_summary": [],
                "metric_highlights": [], "sparse_data_flags": [],
                "notable_entries": [], "llm_narrative": None,
                "recommended_next_actions": [],
            })
            _handle_slash("/review generate", None)

    def test_promote_no_arg(self) -> None:
        conv = _handle_slash("/promote", None)
        assert conv is None

    def test_promote_with_id(self) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "heur-123"})
            _handle_slash("/promote ins-abc123", None)

    def test_accept_with_id(self) -> None:
        with patch("memorychain_cli.client.httpx.put") as mock_put:
            mock_put.return_value = _mock_response({"id": "ins-1", "status": "active"})
            _handle_slash("/accept ins-1", None)

    def test_reject_with_id(self) -> None:
        with patch("memorychain_cli.client.httpx.put") as mock_put:
            mock_put.return_value = _mock_response({"id": "ins-1", "status": "rejected"})
            _handle_slash("/reject ins-1", None)

    def test_connection_error_handled(self) -> None:
        import httpx as _httpx
        with patch("memorychain_cli.client.httpx.get", side_effect=_httpx.ConnectError("refused")):
            conv = _handle_slash("/today", None)
            assert conv is None  # doesn't crash


# ── Chat handler ─────────────────────────────────────────────
class TestChatHandler:
    def test_chat_returns_conversation_id(self) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({
                "conversation_id": "conv-abc",
                "assistant_message": "Logged your entry.",
                "assistant_message_id": "msg-1",
                "extraction": {
                    "source_document_id": "sd-1",
                    "journal_entry_id": None,
                    "checkin_id": None,
                    "task_ids": [], "goal_ids": [],
                    "activity_ids": [], "metric_ids": [],
                },
                "memory_context": [],
            })
            result = _handle_chat("slept 7 hours", None)
            assert result == "conv-abc"

    def test_chat_preserves_conversation_id(self) -> None:
        with patch("memorychain_cli.client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({
                "conversation_id": "conv-abc",
                "assistant_message": "Got it.",
                "assistant_message_id": "msg-2",
                "extraction": {
                    "source_document_id": "sd-2",
                    "journal_entry_id": None,
                    "checkin_id": None,
                    "task_ids": [], "goal_ids": [],
                    "activity_ids": [], "metric_ids": [],
                },
                "memory_context": [],
            })
            result = _handle_chat("mood is 8", "conv-abc")
            assert result == "conv-abc"
            # Verify conversation_id was passed to API
            call_kwargs = mock_post.call_args
            body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert body["conversation_id"] == "conv-abc"

    def test_chat_connection_error(self) -> None:
        import httpx as _httpx
        with patch("memorychain_cli.client.httpx.post", side_effect=_httpx.ConnectError("refused")):
            result = _handle_chat("test", "conv-existing")
            assert result == "conv-existing"  # preserved despite error
