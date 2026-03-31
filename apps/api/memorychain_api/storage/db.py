from __future__ import annotations

import sqlite3


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            title TEXT,
            raw_text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            title TEXT,
            text TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS daily_checkins (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            sleep_hours REAL,
            sleep_quality INTEGER,
            mood INTEGER,
            energy INTEGER,
            body_weight REAL,
            body_weight_unit TEXT,
            immediate_thoughts TEXT,
            pain_notes TEXT,
            hydration_start REAL,
            hydration_unit TEXT,
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            target_date TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            goal_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            due_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        );

        CREATE TABLE IF NOT EXISTS weekly_reviews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            summary TEXT NOT NULL,
            wins_json TEXT NOT NULL,
            slips_json TEXT NOT NULL,
            open_loops_json TEXT NOT NULL,
            recommended_next_actions_json TEXT NOT NULL,
            engagement_notes_json TEXT NOT NULL DEFAULT '[]',
            source_ids_json TEXT NOT NULL,
            confidence REAL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT
        );

        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source_document_id TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS prompt_cycles (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            cycle_date TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            sent_at TEXT,
            expires_at TEXT,
            status TEXT NOT NULL,
            response_source_document_id TEXT,
            response_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (response_source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS engagement_events (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            prompt_cycle_id TEXT,
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (prompt_cycle_id) REFERENCES prompt_cycles(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            changed_fields_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
        ON conversation_messages (conversation_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_messages_user_created
        ON conversation_messages (user_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_prompt_cycles_user_date
        ON prompt_cycles (user_id, cycle_date);

        CREATE INDEX IF NOT EXISTS idx_engagement_events_user_time
        ON engagement_events (user_id, event_at);

        CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created
        ON audit_logs (user_id, created_at);
        """
    )

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(weekly_reviews)").fetchall()
    }
    if "engagement_notes_json" not in columns:
        conn.execute(
            "ALTER TABLE weekly_reviews ADD COLUMN engagement_notes_json TEXT NOT NULL DEFAULT '[]'"
        )

    conn.commit()
