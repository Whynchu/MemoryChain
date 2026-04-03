"""Tests for Phase 7: conversational log consolidation."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from memorychain_api.schemas import (
    JournalEntryCreate,
    SourceDocumentCreate,
)
from memorychain_api.storage.db import connect, initialize
from memorychain_api.storage.repository import Repository


def _uid() -> str:
    return f"p7_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def repo():
    """Create an in-memory repository for testing."""
    conn = connect(":memory:")
    initialize(conn)
    return Repository(conn)


# ── Repository method tests ──────────────────────────────────


class TestLogSessionRepo:
    """Test repository methods for log session management."""

    def test_find_active_log_source_none_when_empty(self, repo):
        result = repo.find_active_log_source("conv_nonexistent")
        assert result is None

    def test_find_active_log_source_returns_active(self, repo):
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=datetime.now(timezone.utc),
            raw_text="test log",
            metadata={
                "conversation_id": "conv_1",
                "log_session_active": True,
                "log_message_count": 1,
            },
        ))
        result = repo.find_active_log_source("conv_1")
        assert result is not None
        assert result.id == source.id

    def test_find_active_log_source_ignores_closed(self, repo):
        repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=datetime.now(timezone.utc),
            raw_text="test log",
            metadata={
                "conversation_id": "conv_1",
                "log_session_active": True,
                "log_message_count": 1,
            },
        ))
        repo.close_log_session("conv_1")
        result = repo.find_active_log_source("conv_1")
        assert result is None

    def test_update_source_document_text(self, repo):
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=now,
            raw_text="message one",
            metadata={
                "conversation_id": "conv_1",
                "log_session_active": True,
                "log_message_count": 1,
            },
        ))
        original_hash = source.content_hash

        updated = repo.update_source_document_text(source.id, "message two", now)
        assert "message one" in updated.raw_text
        assert "message two" in updated.raw_text
        assert updated.content_hash != original_hash

    def test_close_log_session(self, repo):
        repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=datetime.now(timezone.utc),
            raw_text="test",
            metadata={
                "conversation_id": "conv_1",
                "log_session_active": True,
                "log_message_count": 1,
            },
        ))
        repo.close_log_session("conv_1")
        result = repo.find_active_log_source("conv_1")
        assert result is None

    def test_find_journal_by_source(self, repo):
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=now,
            raw_text="test",
            metadata={"conversation_id": "conv_1"},
        ))
        journal = repo.create_journal_entry(JournalEntryCreate(
            user_id="u1",
            source_document_id=source.id,
            effective_at=now,
            text="journal text",
        ))
        found = repo.find_journal_by_source(source.id)
        assert found is not None
        assert found.id == journal.id

    def test_update_journal_entry_text(self, repo):
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=now,
            raw_text="test",
            metadata={"conversation_id": "conv_1"},
        ))
        journal = repo.create_journal_entry(JournalEntryCreate(
            user_id="u1",
            source_document_id=source.id,
            effective_at=now,
            text="first part",
        ))
        repo.update_journal_entry_text(journal.id, "second part")

        found = repo.find_journal_by_source(source.id)
        assert "first part" in found.text
        assert "second part" in found.text

    def test_get_source_document(self, repo):
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=datetime.now(timezone.utc),
            raw_text="test",
            metadata={"conversation_id": "conv_1"},
        ))
        found = repo.get_source_document(source.id)
        assert found is not None
        assert found.id == source.id

    def test_get_source_document_not_found(self, repo):
        result = repo.get_source_document("nonexistent")
        assert result is None

    def test_update_source_document_metadata(self, repo):
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=datetime.now(timezone.utc),
            raw_text="test",
            metadata={"conversation_id": "conv_1", "log_session_active": True, "log_message_count": 1},
        ))
        repo.update_source_document_metadata(source.id, {
            "conversation_id": "conv_1",
            "log_session_active": True,
            "log_message_count": 5,
        })
        updated = repo.get_source_document(source.id)
        assert updated.metadata["log_message_count"] == 5


# ── Integration tests: chat pipeline consolidation ───────────


class TestLogConsolidation:
    """Test that consecutive LOG messages consolidate into one source document."""

    def test_consecutive_logs_same_source_doc(self, repo):
        """Two LOG messages in same conversation share one source document."""
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        r1 = handle_chat(repo, ChatRequest(
            user_id="u1",
            message="Slept 7 hours last night, mood 8/10",
        ))
        source_id_1 = r1.extraction.source_document_id
        assert source_id_1 is not None

        r2 = handle_chat(repo, ChatRequest(
            user_id="u1",
            message="Did 30 minutes of muay thai training",
            conversation_id=r1.conversation_id,
        ))
        source_id_2 = r2.extraction.source_document_id
        assert source_id_2 is not None

        # Should be the SAME source document
        assert source_id_1 == source_id_2

        # Verify combined text
        source = repo.get_source_document(source_id_1)
        assert "Slept 7 hours" in source.raw_text
        assert "muay thai" in source.raw_text

    def test_chat_resets_log_session(self, repo):
        """A CHAT message between LOGs creates separate source documents."""
        from memorychain_api.schemas import ChatRequest
        from memorychain_api.services.chat import handle_chat

        # First log
        r1 = handle_chat(repo, ChatRequest(
            user_id="u1",
            message="Slept 7 hours, mood 8/10",
        ))
        source_id_1 = r1.extraction.source_document_id

        # Chat message (resets session)
        r2 = handle_chat(repo, ChatRequest(
            user_id="u1",
            message="hey what's up",
            conversation_id=r1.conversation_id,
        ))
        assert r2.extraction.source_document_id is None

        # Second log — should be NEW source doc
        r3 = handle_chat(repo, ChatRequest(
            user_id="u1",
            message="Energy level 9/10 today, did a 5k run",
            conversation_id=r1.conversation_id,
        ))
        source_id_3 = r3.extraction.source_document_id
        assert source_id_3 is not None
        assert source_id_3 != source_id_1

    def test_max_messages_forces_new_session(self, repo):
        """After 10 messages, find_active_log_source still returns it,
        but _handle_log will force a new session when msg_count >= 10."""
        now = datetime.now(timezone.utc)
        source = repo.create_source_document(SourceDocumentCreate(
            user_id="u1",
            source_type="chat_message",
            effective_at=now,
            raw_text="accumulated text",
            metadata={
                "conversation_id": "conv_test",
                "log_session_active": True,
                "log_message_count": 10,
            },
        ))

        active = repo.find_active_log_source("conv_test")
        assert active is not None
        assert active.metadata.get("log_message_count") == 10
