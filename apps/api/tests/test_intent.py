"""Tests for Phase 5: intent classification, query handling, and chat routing."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timezone
from types import SimpleNamespace

from memorychain_api.services.intent import classify_intent, _classify_local, ClassificationResult
from memorychain_api.services.query_handler import handle_query, _detect_topics, _recent_date_range, QueryResult


# ── Intent Classifier Tests ──────────────────────────────────

class TestLocalClassifier:
    """Test keyword-based intent classification (no LLM)."""

    @pytest.mark.parametrize("message,expected", [
        ("hey!", "chat"),
        ("hi", "chat"),
        ("hello!", "chat"),
        ("thanks", "chat"),
        ("ok", "chat"),
        ("yes", "chat"),
    ])
    def test_short_chat_messages(self, message, expected):
        result = _classify_local(message)
        assert result.intent == expected

    @pytest.mark.parametrize("message,expected", [
        ("Slept 7h, mood 8/10", "log"),
        ("Sleep 6.5 hours, energy 7/10", "log"),
        ("mood 9 energy 8", "log"),
        ("Did 3 rounds of bagwork", "log"),
        ("Body weight: 183 lbs", "log"),
        ("Woke up feeling great, trained hard today", "log"),
        ("todo: finish the API refactor", "log"),
    ])
    def test_log_messages(self, message, expected):
        result = _classify_local(message)
        assert result.intent == expected

    @pytest.mark.parametrize("message,expected", [
        ("How's my sleep been?", "query"),
        ("Show my goals", "query"),
        ("What are my active tasks?", "query"),
        ("How much did I sleep this week?", "query"),
        ("What's my average mood?", "query"),
        ("List my insights", "query"),
        ("show me my daily checkins", "query"),
        ("what's my progress this month?", "query"),
    ])
    def test_query_messages(self, message, expected):
        result = _classify_local(message)
        assert result.intent == expected

    def test_ambiguous_defaults_to_chat(self):
        result = _classify_local("hmm not sure")
        assert result.intent == "chat"

    def test_question_mark_boosts_query(self):
        result = _classify_local("what happened?")
        assert result.intent == "query"

    def test_confidence_increases_with_matches(self):
        weak = _classify_local("mood 8")
        strong = _classify_local("Slept 7h, mood 8/10, energy 9/10, weight 183 lbs")
        assert strong.confidence >= weak.confidence


class TestClassifyIntent:
    """Test the top-level classify_intent function."""

    @patch("memorychain_api.services.intent._classify_llm", return_value=None)
    def test_falls_back_to_local(self, mock_llm):
        result = classify_intent("hey!")
        assert result.intent == "chat"
        mock_llm.assert_called_once()

    @patch("memorychain_api.services.intent._classify_llm")
    def test_uses_llm_when_available(self, mock_llm):
        mock_llm.return_value = ClassificationResult(intent="query", confidence=0.95, reasoning="test")
        result = classify_intent("How's my sleep?")
        assert result.intent == "query"
        assert result.confidence == 0.95


# ── Topic Detection Tests ────────────────────────────────────

class TestTopicDetection:
    def test_sleep_topic(self):
        assert "sleep" in _detect_topics("how did I sleep?")

    def test_mood_topic(self):
        assert "mood" in _detect_topics("what's my mood been like?")

    def test_goals_topic(self):
        assert "goals" in _detect_topics("show my goals")

    def test_tasks_topic(self):
        assert "tasks" in _detect_topics("list my tasks")

    def test_multiple_topics(self):
        topics = _detect_topics("how's my sleep and mood?")
        assert "sleep" in topics
        assert "mood" in topics

    def test_general_fallback(self):
        topics = _detect_topics("xyz random stuff")
        assert topics == ["general"]


# ── Date Range Tests ─────────────────────────────────────────

class TestDateRange:
    def test_today(self):
        start, end = _recent_date_range("what happened today?")
        assert start == end == date.today()

    def test_this_week(self):
        start, end = _recent_date_range("how was this week?")
        assert end == date.today()
        assert (end - start).days == 7

    def test_last_month(self):
        start, end = _recent_date_range("show last month")
        assert (end - start).days == 30

    def test_default_7_days(self):
        start, end = _recent_date_range("how am I doing?")
        assert (end - start).days == 7


# ── Query Handler Tests ──────────────────────────────────────

class TestQueryHandler:
    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list_checkins.return_value = []
        repo.list_goals.return_value = []
        repo.list_tasks.return_value = []
        repo.list_insights.return_value = []
        repo.list_heuristics.return_value = []
        repo.list_activities.return_value = []
        repo.list_discrepancy_events.return_value = []
        repo.get_engagement_summary.return_value = SimpleNamespace(
            adherence_rate=None,
            longest_nonresponse_streak_days=0,
        )
        repo.get_user_profile.return_value = None
        return repo

    def test_sleep_query_empty(self, mock_repo):
        results = handle_query(mock_repo, "user1", "how did I sleep?")
        assert len(results) >= 1
        assert "No sleep data" in results[0].summary or results[0].object_count == 0

    def test_sleep_query_with_data(self, mock_repo):
        checkin = MagicMock()
        checkin.date = date.today()
        checkin.sleep_hours = 7.5
        checkin.mood = None
        checkin.energy = None
        mock_repo.list_checkins.return_value = [checkin]

        results = handle_query(mock_repo, "user1", "how did I sleep today?")
        assert any("7.5" in r.summary or any("7.5" in l for l in r.data_lines) for r in results)

    def test_goals_query(self, mock_repo):
        goal = MagicMock()
        goal.status = "active"
        goal.title = "Get fit"
        goal.created_at = "2025-01-01"
        mock_repo.list_goals.return_value = [goal]

        results = handle_query(mock_repo, "user1", "what are my goals?")
        assert any("Get fit" in " ".join(r.data_lines) for r in results)

    def test_general_query(self, mock_repo):
        results = handle_query(mock_repo, "user1", "how am I doing?")
        assert len(results) >= 1


# ── Chat Router Integration Tests ────────────────────────────

class TestChatRouter:
    """Test that the refactored handle_chat routes correctly by intent."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        conv = MagicMock()
        conv.id = "conv_123"
        conv.metadata = {}
        repo.get_or_create_conversation.return_value = conv
        repo.update_conversation_metadata.side_effect = (
            lambda conversation_id, user_id, metadata: SimpleNamespace(
                id=conversation_id,
                user_id=user_id,
                metadata=metadata,
            )
        )

        q_service_mock = MagicMock()
        q_service_mock.check_active_session.return_value = None
        repo.list_questionnaire_templates.return_value = []

        msg = MagicMock()
        msg.id = "msg_1"
        msg.role = "user"
        msg.content = "test"
        repo.list_conversation_messages.return_value = [msg]
        repo.append_conversation_message.return_value = MagicMock(id="msg_2")
        repo.list_open_tasks.return_value = []
        repo.list_checkins.return_value = []
        repo.list_goals.return_value = []
        repo.list_tasks.return_value = []
        repo.list_insights.return_value = []
        repo.list_heuristics.return_value = []
        repo.list_activities.return_value = []
        repo.list_discrepancy_events.return_value = []
        repo.get_engagement_summary.return_value = SimpleNamespace(
            adherence_rate=None,
            longest_nonresponse_streak_days=0,
        )
        repo.get_user_profile.return_value = None
        return repo

    @patch("memorychain_api.services.chat.build_context_snapshot")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_chat_intent_no_storage(self, MockQS, mock_classify, mock_snapshot, mock_repo):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="chat", confidence=0.9)
        mock_snapshot.return_value = SimpleNamespace(
            has_checkin_today=False,
            period="morning",
            is_morning_window=True,
            longest_nonresponse_streak_days=0,
            adherence_rate_7d=None,
            stale_task_count=0,
            has_stale_commitment_pressure=False,
            candidate_insight_count=0,
            active_heuristic_count=0,
            unresolved_discrepancy_count=0,
            has_pattern_pressure=False,
            has_goal_alignment_pressure=False,
            active_goal_count=0,
            days_since_checkin=None,
            open_task_titles=[],
            active_goal_titles=[],
            active_heuristic_rules=[],
            candidate_insight_titles=[],
            likely_low_recovery=False,
            likely_low_mood=False,
            to_memory_context=lambda: ["Current time: Tuesday 9:00 AM (morning)"],
        )

        payload = ChatRequest(user_id="u1", message="hey!")
        response = handle_chat(mock_repo, payload)

        assert response.assistant_message
        assert response.extraction.source_document_id is None
        assert response.companion is not None
        assert response.companion.active_thread == "daily_checkin"
        assert response.companion.mode == "intake"
        assert response.companion.actions[0].kind == "clarify"
        assert response.companion.actions[0].expected_response == "checkin_state"
        assert "sleep" in response.assistant_message.lower()
        assert "pending_companion" in mock_repo.update_conversation_metadata.call_args.kwargs["metadata"]
        mock_repo.create_source_document.assert_not_called()

    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_query_intent_no_storage(self, MockQS, mock_classify, mock_repo):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="query", confidence=0.9)

        payload = ChatRequest(user_id="u1", message="How's my sleep?")
        response = handle_chat(mock_repo, payload)

        assert response.assistant_message
        assert response.extraction.source_document_id is None
        assert response.companion is not None
        assert response.companion.mode == "review"
        assert response.companion.actions[0].kind == "guide"
        mock_repo.create_source_document.assert_not_called()

    @patch("memorychain_api.services.chat.extract_objects")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_log_intent_creates_source_doc(self, MockQS, mock_classify, mock_extract, mock_repo):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="log", confidence=0.9)

        extraction_result = MagicMock()
        extraction_result.journal_entry = None
        extraction_result.checkin = None
        extraction_result.goals = []
        extraction_result.tasks = []
        extraction_result.activities = []
        extraction_result.metrics = []
        mock_extract.return_value = extraction_result

        source_doc = MagicMock()
        source_doc.id = "src_1"
        mock_repo.create_source_document.return_value = source_doc
        mock_repo.find_active_log_source.return_value = None

        payload = ChatRequest(user_id="u1", message="Slept 7h, mood 8/10")
        response = handle_chat(mock_repo, payload)

        assert response.extraction.source_document_id == "src_1"
        assert response.companion is not None
        assert response.companion.mode in ("intake", "commit")
        assert response.companion.actions
        assert response.companion.actions[0].kind == "clarify"
        mock_repo.create_source_document.assert_called_once()
        mock_extract.assert_called_once()

    @patch("memorychain_api.services.chat.build_context_snapshot")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.extract_objects")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_pending_checkin_forces_followup_into_log(
        self,
        MockQS,
        mock_extract,
        mock_classify,
        mock_snapshot,
        mock_repo,
    ):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="chat", confidence=0.7)
        mock_repo.get_or_create_conversation.return_value.metadata = {
            "pending_companion": {
                "mode": "intake",
                "active_thread": "daily_checkin",
                "rationale": ["No check-in has been logged yet."],
                "signals": [],
                "actions": [
                    {
                        "kind": "clarify",
                        "prompt": "Give me sleep, mood, energy, and the main tone of the morning.",
                        "reason": "The highest-value move is to establish today's state before planning.",
                        "expected_response": "checkin_state",
                        "focus_items": ["sleep_hours", "mood", "energy"],
                        "inferred_from": ["brief_opening"],
                    }
                ],
            }
        }

        mock_snapshot.side_effect = [
            SimpleNamespace(
                has_checkin_today=False,
                period="morning",
                is_morning_window=True,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=None,
                stale_task_count=0,
                has_stale_commitment_pressure=False,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=0,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=False,
                active_goal_count=0,
                days_since_checkin=1,
                open_task_titles=[],
                active_goal_titles=[],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Current time: Tuesday 9:00 AM (morning)"],
            ),
            SimpleNamespace(
                has_checkin_today=True,
                period="morning",
                is_morning_window=True,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=None,
                stale_task_count=0,
                has_stale_commitment_pressure=False,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=0,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=False,
                active_goal_count=1,
                days_since_checkin=0,
                open_task_titles=[],
                active_goal_titles=["Train cleanly"],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Active goals (1): Train cleanly"],
            ),
        ]

        extraction_result = MagicMock()
        extraction_result.journal_entry = None
        extraction_result.checkin = None
        extraction_result.goals = []
        extraction_result.tasks = []
        extraction_result.activities = []
        extraction_result.metrics = []
        mock_extract.return_value = extraction_result

        source_doc = MagicMock()
        source_doc.id = "src_1"
        mock_repo.create_source_document.return_value = source_doc
        mock_repo.find_active_log_source.return_value = None

        payload = ChatRequest(user_id="u1", message="feeling rough and tired")
        response = handle_chat(mock_repo, payload)

        assert response.extraction.source_document_id == "src_1"
        assert response.companion is not None
        assert response.companion.active_thread == "daily_focus"
        assert response.companion.actions[0].kind == "guide"
        mock_repo.create_source_document.assert_called_once()
        mock_extract.assert_called_once()

    @patch("memorychain_api.services.chat.build_context_snapshot")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_pending_task_status_updates_task_and_rethreads_companion(
        self,
        MockQS,
        mock_classify,
        mock_snapshot,
        mock_repo,
    ):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="chat", confidence=0.7)
        mock_repo.get_or_create_conversation.return_value.metadata = {
            "pending_companion": {
                "mode": "guide",
                "active_thread": "stale_commitment",
                "rationale": ["There are stale open loops competing with new planning."],
                "signals": [],
                "actions": [
                    {
                        "kind": "commit",
                        "prompt": "Decide whether `Finish refactor` is still real.",
                        "reason": "Stale commitments distort planning until they are made explicit.",
                        "expected_response": "task_status",
                        "focus_items": ["Finish refactor", "Ship companion"],
                        "inferred_from": ["stale_commitment_pressure"],
                    }
                ],
            }
        }
        mock_repo.list_open_tasks.return_value = [
            SimpleNamespace(id="task_1", title="Finish refactor", status="todo")
        ]
        mock_repo.update_task.return_value = SimpleNamespace(id="task_1", title="Finish refactor", status="canceled")
        mock_repo.create_discrepancy_event.return_value = SimpleNamespace(id="disc_1")

        mock_snapshot.side_effect = [
            SimpleNamespace(
                has_checkin_today=True,
                period="afternoon",
                is_morning_window=False,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=0.8,
                stale_task_count=1,
                has_stale_commitment_pressure=True,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=0,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=False,
                active_goal_count=1,
                days_since_checkin=0,
                open_task_titles=["Finish refactor"],
                active_goal_titles=["Ship companion"],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Open tasks (1): Finish refactor"],
            ),
            SimpleNamespace(
                has_checkin_today=True,
                period="afternoon",
                is_morning_window=False,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=0.8,
                stale_task_count=0,
                has_stale_commitment_pressure=False,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=1,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=True,
                active_goal_count=1,
                days_since_checkin=0,
                open_task_titles=[],
                active_goal_titles=["Ship companion"],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                recent_discrepancy_ids=["disc_1"],
                recent_discrepancy_summaries=["Canceled `Finish refactor` after it stayed open without follow-through."],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Active goals (1): Ship companion"],
            ),
        ]

        payload = ChatRequest(user_id="u1", message="kill it")
        response = handle_chat(mock_repo, payload)

        assert response.companion is not None
        assert response.companion.active_thread == "goal_alignment"
        assert "canceled" in response.assistant_message.lower()
        assert mock_repo.create_discrepancy_event.called
        assert mock_repo.update_task.call_args.kwargs["payload"].status == "canceled"
        mock_repo.create_source_document.assert_not_called()

    @patch("memorychain_api.services.chat.build_context_snapshot")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_pending_plan_outline_creates_task(
        self,
        MockQS,
        mock_classify,
        mock_snapshot,
        mock_repo,
    ):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="chat", confidence=0.7)
        mock_repo.get_or_create_conversation.return_value.metadata = {
            "pending_companion": {
                "mode": "commit",
                "active_thread": "goal_alignment",
                "rationale": ["Recent commitment drift should be named before ordinary planning."],
                "signals": [],
                "actions": [
                    {
                        "kind": "commit",
                        "prompt": "State the concrete version you are actually willing to do.",
                        "reason": "Declared plans should be grounded in likely follow-through.",
                        "expected_response": "plan_outline",
                        "focus_items": ["Ship companion", "Canceled `Finish refactor` after it stayed open without follow-through.", "discrepancy:disc_1", "alignment_commitment"],
                        "inferred_from": [],
                    }
                ],
            }
        }
        mock_repo.list_open_tasks.return_value = []
        mock_repo.create_task.return_value = SimpleNamespace(id="task_2", title="Write the CLI morning flow")
        mock_repo.resolve_discrepancy_event.return_value = SimpleNamespace(id="disc_1", status="resolved")

        mock_snapshot.side_effect = [
            SimpleNamespace(
                has_checkin_today=True,
                period="afternoon",
                is_morning_window=False,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=0.8,
                stale_task_count=0,
                has_stale_commitment_pressure=False,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=1,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=True,
                active_goal_count=1,
                days_since_checkin=0,
                open_task_titles=[],
                active_goal_titles=["Ship companion"],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                recent_discrepancy_ids=["disc_1"],
                recent_discrepancy_summaries=["Canceled `Finish refactor` after it stayed open without follow-through."],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Active goals (1): Ship companion"],
            ),
            SimpleNamespace(
                has_checkin_today=True,
                period="afternoon",
                is_morning_window=False,
                longest_nonresponse_streak_days=0,
                adherence_rate_7d=0.8,
                stale_task_count=0,
                has_stale_commitment_pressure=False,
                candidate_insight_count=0,
                active_heuristic_count=0,
                unresolved_discrepancy_count=0,
                has_pattern_pressure=False,
                has_goal_alignment_pressure=False,
                active_goal_count=1,
                days_since_checkin=0,
                open_task_titles=["Write the CLI morning flow"],
                active_goal_titles=["Ship companion"],
                active_heuristic_rules=[],
                candidate_insight_titles=[],
                recent_discrepancy_ids=[],
                recent_discrepancy_summaries=[],
                likely_low_recovery=False,
                likely_low_mood=False,
                to_memory_context=lambda: ["Open tasks (1): Write the CLI morning flow"],
            ),
        ]

        payload = ChatRequest(user_id="u1", message="I will write the CLI morning flow.")
        response = handle_chat(mock_repo, payload)

        assert response.companion is not None
        assert "created a task" in response.assistant_message.lower()
        assert mock_repo.create_task.call_args.args[0].title == "write the CLI morning flow"
        assert mock_repo.resolve_discrepancy_event.call_args.kwargs["discrepancy_id"] == "disc_1"
        mock_repo.create_source_document.assert_not_called()

    @patch("memorychain_api.services.chat.build_context_snapshot")
    @patch("memorychain_api.services.chat.classify_intent")
    @patch("memorychain_api.services.chat.QuestionnaireService")
    def test_ambiguous_task_status_keeps_pending_action(
        self,
        MockQS,
        mock_classify,
        mock_snapshot,
        mock_repo,
    ):
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        qs_instance = MagicMock()
        qs_instance.check_active_session.return_value = None
        MockQS.return_value = qs_instance

        mock_classify.return_value = ClassificationResult(intent="chat", confidence=0.7)
        mock_repo.get_or_create_conversation.return_value.metadata = {
            "pending_companion": {
                "mode": "guide",
                "active_thread": "stale_commitment",
                "rationale": ["There are stale open loops competing with new planning."],
                "signals": [],
                "actions": [
                    {
                        "kind": "commit",
                        "prompt": "Decide whether `Finish refactor` is still real.",
                        "reason": "Stale commitments distort planning until they are made explicit.",
                        "expected_response": "task_status",
                        "focus_items": ["Finish refactor", "Ship companion"],
                        "inferred_from": ["stale_commitment_pressure"],
                    }
                ],
            }
        }
        mock_repo.list_open_tasks.return_value = [
            SimpleNamespace(id="task_1", title="Finish refactor", status="todo")
        ]
        mock_snapshot.return_value = SimpleNamespace(
            has_checkin_today=True,
            period="afternoon",
            is_morning_window=False,
            longest_nonresponse_streak_days=0,
            adherence_rate_7d=0.8,
            stale_task_count=1,
            has_stale_commitment_pressure=True,
            candidate_insight_count=0,
            active_heuristic_count=0,
            unresolved_discrepancy_count=0,
            has_pattern_pressure=False,
            has_goal_alignment_pressure=False,
            active_goal_count=1,
            days_since_checkin=0,
            open_task_titles=["Finish refactor"],
            active_goal_titles=["Ship companion"],
            active_heuristic_rules=[],
            candidate_insight_titles=[],
            recent_discrepancy_ids=[],
            recent_discrepancy_summaries=[],
            likely_low_recovery=False,
            likely_low_mood=False,
            to_memory_context=lambda: ["Open tasks (1): Finish refactor"],
        )

        payload = ChatRequest(user_id="u1", message="maybe")
        response = handle_chat(mock_repo, payload)

        assert response.companion is not None
        assert response.companion.active_thread == "stale_commitment"
        assert "keep it, renegotiate it, or kill it" in response.assistant_message.lower()
        mock_repo.update_task.assert_not_called()

    @patch("memorychain_api.services.chat.classify_intent")
    def test_questionnaire_bypasses_intent(self, mock_classify, mock_repo):
        """Active questionnaire sessions should skip intent classification."""
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        # Setup active questionnaire
        session = MagicMock()
        session.id = "qs_1"

        source = MagicMock()
        source.id = "src_q"
        mock_repo.create_source_document.return_value = source

        with patch("memorychain_api.services.chat.QuestionnaireService") as MockQS:
            qs_instance = MagicMock()
            qs_instance.check_active_session.return_value = session
            qs_instance.process_answer.return_value = ("Next question?", False)
            MockQS.return_value = qs_instance

            payload = ChatRequest(user_id="u1", message="yes")
            response = handle_chat(mock_repo, payload)

            mock_classify.assert_not_called()
            assert "Next question?" in response.assistant_message
            assert response.companion is not None
            assert response.companion.active_thread == "questionnaire"
            assert response.companion.actions[0].expected_response == "questionnaire_answer"
