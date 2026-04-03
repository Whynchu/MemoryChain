"""Tests for Phase 8: onboarding, adaptive check-ins, custom dimensions."""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone

import pytest

from memorychain_api.schemas import (
    DailyCheckinCreate,
    QuestionDef,
    SourceDocumentCreate,
    UserProfileCreate,
)
from memorychain_api.storage.db import connect, initialize
from memorychain_api.storage.repository import Repository


def _uid() -> str:
    return f"p8_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def repo():
    """Create an in-memory repository for testing."""
    conn = connect(":memory:")
    initialize(conn)
    return Repository(conn)


# ── User Profile CRUD ────────────────────────────────────────


class TestUserProfile:
    """Test user profile CRUD."""

    def test_create_and_get_profile(self, repo):
        profile = repo.create_user_profile(UserProfileCreate(
            user_id="u1",
            display_name="Sam",
            sleep_target=8.0,
            custom_dimensions=[{"name": "meditation", "unit": "minutes", "type": "numeric"}],
        ))
        assert profile.display_name == "Sam"
        assert profile.sleep_target == 8.0
        assert len(profile.custom_dimensions) == 1
        assert profile.custom_dimensions[0]["name"] == "meditation"

        fetched = repo.get_user_profile("u1")
        assert fetched is not None
        assert fetched.display_name == "Sam"

    def test_get_nonexistent_profile(self, repo):
        assert repo.get_user_profile("nonexistent") is None

    def test_update_profile(self, repo):
        repo.create_user_profile(UserProfileCreate(user_id="u1", display_name="Sam"))
        updated = repo.update_user_profile("u1", display_name="Samuel", sleep_target=7.5)
        assert updated.display_name == "Samuel"
        assert updated.sleep_target == 7.5

    def test_update_onboarded_at(self, repo):
        repo.create_user_profile(UserProfileCreate(user_id="u1"))
        now = datetime.now(timezone.utc)
        updated = repo.update_user_profile("u1", onboarded_at=now)
        assert updated.onboarded_at is not None

    def test_custom_dimensions_round_trip(self, repo):
        dims = [
            {"name": "meditation", "unit": "minutes", "type": "numeric"},
            {"name": "caffeine", "unit": "cups", "type": "numeric"},
        ]
        repo.create_user_profile(UserProfileCreate(user_id="u1", custom_dimensions=dims))
        profile = repo.get_user_profile("u1")
        assert len(profile.custom_dimensions) == 2
        names = {d["name"] for d in profile.custom_dimensions}
        assert names == {"meditation", "caffeine"}

    def test_update_custom_dimensions(self, repo):
        repo.create_user_profile(UserProfileCreate(user_id="u1"))
        dims = [{"name": "yoga", "unit": "minutes", "type": "numeric"}]
        updated = repo.update_user_profile("u1", custom_dimensions=dims)
        assert len(updated.custom_dimensions) == 1
        assert updated.custom_dimensions[0]["name"] == "yoga"

    def test_profile_defaults(self, repo):
        repo.create_user_profile(UserProfileCreate(user_id="u1"))
        profile = repo.get_user_profile("u1")
        assert profile.sleep_target == 8.0
        assert profile.checkin_time_pref == "morning"
        assert profile.custom_dimensions == []
        assert profile.onboarded_at is None


# ── Expanded Check-in Fields ─────────────────────────────────


class TestExpandedCheckin:
    """Test new check-in fields like stress, dreams, thought_loops."""

    def test_checkin_with_stress_dreams(self, repo):
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1", source_type="chat_message",
            effective_at=now, raw_text="test",
        ))
        checkin = repo.create_checkin(DailyCheckinCreate(
            user_id="u1",
            source_document_id=source.id,
            date=now.date(),
            effective_at=now,
            sleep_hours=7,
            mood=6,
            stress_level=8,
            dreams="Weird dream about flying",
            thought_loops="Can't stop thinking about project deadline",
        ))
        assert checkin.stress_level == 8
        assert checkin.dreams == "Weird dream about flying"
        assert checkin.thought_loops == "Can't stop thinking about project deadline"

    def test_checkin_minimal_fields(self, repo):
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1", source_type="chat_message",
            effective_at=now, raw_text="test",
        ))
        checkin = repo.create_checkin(DailyCheckinCreate(
            user_id="u1",
            source_document_id=source.id,
            date=now.date(),
            effective_at=now,
        ))
        assert checkin.stress_level is None
        assert checkin.dreams is None
        assert checkin.thought_loops is None


# ── Adaptive Question Logic ──────────────────────────────────


class TestAdaptiveQuestions:
    """Test conditional show_if question logic."""

    def _make_svc(self, repo):
        from memorychain_api.services.questionnaire import QuestionnaireService
        return QuestionnaireService(repo)

    def test_show_if_condition_met(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="Dreams?", question_type="text",
            show_if={"question_id": "dc_sleep_quality", "operator": "lt", "value": 6},
        )
        assert svc._should_show_question(q, {"dc_sleep_quality": "4"}) is True

    def test_show_if_condition_not_met(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="Dreams?", question_type="text",
            show_if={"question_id": "dc_sleep_quality", "operator": "lt", "value": 6},
        )
        assert svc._should_show_question(q, {"dc_sleep_quality": "8"}) is False

    def test_no_show_if_always_shows(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="Mood?", question_type="scale",
        )
        assert svc._should_show_question(q, {}) is True

    def test_show_if_gt_operator(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="What went well?", question_type="text",
            show_if={"question_id": "dc_mood", "operator": "gt", "value": 7},
        )
        assert svc._should_show_question(q, {"dc_mood": "9"}) is True
        assert svc._should_show_question(q, {"dc_mood": "5"}) is False

    def test_show_if_eq_operator(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="Details?", question_type="text",
            show_if={"question_id": "dc_mood", "operator": "eq", "value": 5},
        )
        assert svc._should_show_question(q, {"dc_mood": "5"}) is True
        assert svc._should_show_question(q, {"dc_mood": "6"}) is False

    def test_show_if_dependency_not_answered(self, repo):
        svc = self._make_svc(repo)
        q = QuestionDef(
            id="test", question_text="Dreams?", question_type="text",
            show_if={"question_id": "dc_sleep_quality", "operator": "lt", "value": 6},
        )
        assert svc._should_show_question(q, {}) is False

    def test_find_next_showable_skips_hidden(self, repo):
        svc = self._make_svc(repo)
        questions = [
            QuestionDef(id="q1", question_text="Mood?", question_type="scale"),
            QuestionDef(id="q2", question_text="Dreams?", question_type="text",
                        show_if={"question_id": "q1", "operator": "lt", "value": 5}),
            QuestionDef(id="q3", question_text="Notes?", question_type="text"),
        ]
        # With q1=8 (>= 5), q2 should be skipped → next is q3 at index 2
        idx = svc._find_next_showable_question(questions, 1, {"q1": "8"})
        assert idx == 2

    def test_count_visible_questions(self, repo):
        svc = self._make_svc(repo)
        questions = [
            QuestionDef(id="q1", question_text="Mood?", question_type="scale"),
            QuestionDef(id="q2", question_text="Dreams?", question_type="text",
                        show_if={"question_id": "q1", "operator": "lt", "value": 5}),
            QuestionDef(id="q3", question_text="Notes?", question_type="text"),
        ]
        # With q1=8, q2 is hidden → 2 visible
        assert svc._count_visible_questions(questions, {"q1": "8"}) == 2
        # With q1=3, q2 is shown → 3 visible
        assert svc._count_visible_questions(questions, {"q1": "3"}) == 3


# ── Seed Templates ───────────────────────────────────────────


class TestSeedTemplates:
    """Test template seeding."""

    def test_seed_creates_templates(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        result = seed_default_templates(repo)
        assert "onboarding" in result
        assert "daily_checkin" in result

        templates = repo.list_questionnaire_templates("system", active_only=True)
        names = {t.name for t in templates}
        assert "onboarding" in names
        assert "daily_checkin" in names

    def test_seed_idempotent(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        r1 = seed_default_templates(repo)
        r2 = seed_default_templates(repo)
        assert len(r2) == 0  # No new templates created
        templates = repo.list_questionnaire_templates("system", active_only=True)
        onboarding_count = sum(1 for t in templates if t.name == "onboarding")
        assert onboarding_count == 1

    def test_daily_checkin_template_has_show_if(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        conditional = [q for q in dc.questions if q.show_if]
        assert len(conditional) >= 2  # dreams and mood_why at minimum

    def test_onboarding_template_has_target_fields(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        ob = next(t for t in templates if t.name == "onboarding")
        fields = [q.target_field for q in ob.questions if q.target_field]
        assert "display_name" in fields
        assert "sleep_target" in fields


# ── Custom Dimensions ────────────────────────────────────────


class TestCustomDimensions:
    """Test custom tracking dimensions in check-ins."""

    def _make_svc(self, repo):
        from memorychain_api.services.questionnaire import QuestionnaireService
        return QuestionnaireService(repo)

    def test_parse_tracking_preferences_custom_only(self, repo):
        svc = self._make_svc(repo)
        result = svc._parse_tracking_preferences("1, 2, 3, meditation, caffeine")
        custom_names = [d["name"] for d in result]
        assert "meditation" in custom_names
        assert "caffeine" in custom_names
        # Predefined dimensions should not be in the custom list
        assert "sleep" not in custom_names
        assert "mood" not in custom_names
        assert "energy" not in custom_names

    def test_parse_tracking_preferences_empty(self, repo):
        svc = self._make_svc(repo)
        assert svc._parse_tracking_preferences("") == []

    def test_parse_tracking_preferences_all_predefined(self, repo):
        svc = self._make_svc(repo)
        result = svc._parse_tracking_preferences("1, 2, sleep, mood")
        assert result == []

    def test_parse_tracking_preferences_deduplicates(self, repo):
        svc = self._make_svc(repo)
        result = svc._parse_tracking_preferences("meditation, meditation, caffeine")
        names = [d["name"] for d in result]
        assert names.count("meditation") == 1

    def test_effective_questions_no_profile(self, repo):
        """Without a user profile, effective questions == template questions."""
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        qs = svc._get_effective_questions(dc, "unknown_user")
        assert len(qs) == len(dc.questions)

    def test_effective_questions_with_custom_dims(self, repo):
        """Custom dimensions are appended to daily check-in questions."""
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        repo.create_user_profile(UserProfileCreate(
            user_id="u1",
            custom_dimensions=[
                {"name": "meditation", "unit": "minutes", "type": "numeric"},
                {"name": "caffeine", "unit": "cups", "type": "numeric"},
            ],
        ))
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        qs = svc._get_effective_questions(dc, "u1")
        assert len(qs) == len(dc.questions) + 2
        ids = [q.id for q in qs]
        assert "custom_meditation" in ids
        assert "custom_caffeine" in ids

    def test_effective_questions_only_for_daily_checkin(self, repo):
        """Custom dimensions should NOT be injected into onboarding template."""
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        repo.create_user_profile(UserProfileCreate(
            user_id="u1",
            custom_dimensions=[{"name": "meditation", "unit": "minutes", "type": "numeric"}],
        ))
        templates = repo.list_questionnaire_templates("system", active_only=True)
        ob = next(t for t in templates if t.name == "onboarding")
        qs = svc._get_effective_questions(ob, "u1")
        assert len(qs) == len(ob.questions)  # No injection

    def test_custom_dim_question_format(self, repo):
        """Custom dimension questions should have correct text and type."""
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        repo.create_user_profile(UserProfileCreate(
            user_id="u1",
            custom_dimensions=[
                {"name": "meditation", "unit": "minutes", "type": "numeric"},
                {"name": "journal", "unit": "", "type": "text"},
            ],
        ))
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        qs = svc._get_effective_questions(dc, "u1")

        med_q = next(q for q in qs if q.id == "custom_meditation")
        assert "meditation" in med_q.question_text.lower()
        assert "minutes" in med_q.question_text
        assert med_q.question_type == "numeric"
        assert med_q.required is False

        journal_q = next(q for q in qs if q.id == "custom_journal")
        assert journal_q.question_type == "text"


# ── Questionnaire Session Integration ────────────────────────


class TestQuestionnaireSessionIntegration:
    """Integration tests for questionnaire start/process flow."""

    def _make_svc(self, repo):
        from memorychain_api.services.questionnaire import QuestionnaireService
        return QuestionnaireService(repo)

    def test_start_checkin_questionnaire(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        result = seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")

        conv = repo.get_or_create_conversation(user_id="u1", conversation_id="conv1")
        session, first_q = svc.start_questionnaire("u1", dc.id, conv.id)
        assert session.status == "in_progress"
        assert session.current_question_index == 0
        assert "sleep" in first_q.lower()

    def test_start_checkin_with_custom_dims_adds_questions(self, repo):
        """Starting a check-in with custom dims should produce more questions."""
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        repo.create_user_profile(UserProfileCreate(
            user_id="u1",
            custom_dimensions=[{"name": "meditation", "unit": "minutes", "type": "numeric"}],
        ))
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        qs = svc._get_effective_questions(dc, "u1")
        assert any(q.id == "custom_meditation" for q in qs)

    def test_process_answer_advances(self, repo):
        from memorychain_api.services.seed_templates import seed_default_templates
        svc = self._make_svc(repo)
        seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")

        conv = repo.get_or_create_conversation(user_id="u1", conversation_id="conv1")
        session, _ = svc.start_questionnaire("u1", dc.id, conv.id)
        # Answer first question (sleep hours)
        next_q, done = svc.process_answer(session, "7")
        assert done is False
        assert next_q is not None
        # Session should have advanced
        updated = repo.get_questionnaire_session(session.id, "u1")
        assert updated.current_question_index > 0
        assert "dc_sleep" in updated.answers

    def test_format_question_includes_progress(self, repo):
        svc = self._make_svc(repo)
        from memorychain_api.services.seed_templates import seed_default_templates
        seed_default_templates(repo)
        templates = repo.list_questionnaire_templates("system", active_only=True)
        dc = next(t for t in templates if t.name == "daily_checkin")
        text = svc._format_question(dc.questions[0], dc, 1, 10)
        assert "1 of 10" in text
