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
            content_hash TEXT NOT NULL UNIQUE,
            provenance TEXT NOT NULL DEFAULT 'user'
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
            provenance TEXT NOT NULL DEFAULT 'user',
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
            provenance TEXT NOT NULL DEFAULT 'user',
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_document_id TEXT,
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            title TEXT NOT NULL,
            description TEXT,
            notes TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            provenance TEXT NOT NULL DEFAULT 'user',
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS metric_observations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_document_id TEXT,
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT,
            value_type TEXT NOT NULL DEFAULT 'number',
            notes TEXT,
            provenance TEXT NOT NULL DEFAULT 'user',
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS protocols (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            steps_json TEXT NOT NULL DEFAULT '[]',
            target_metrics_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            provenance TEXT NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS protocol_executions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            source_document_id TEXT,
            created_at TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            completion_status TEXT NOT NULL DEFAULT 'completed',
            notes TEXT,
            provenance TEXT NOT NULL DEFAULT 'user',
            FOREIGN KEY (protocol_id) REFERENCES protocols(id),
            FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
        );

        CREATE TABLE IF NOT EXISTS insights (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'candidate',
            evidence_ids_json TEXT NOT NULL DEFAULT '[]',
            counterevidence_ids_json TEXT NOT NULL DEFAULT '[]',
            time_window_start TEXT,
            time_window_end TEXT,
            provenance TEXT NOT NULL DEFAULT 'system_inferred'
        );

        CREATE TABLE IF NOT EXISTS heuristics (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            rule TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'validated_pattern',
            confidence REAL,
            active INTEGER NOT NULL DEFAULT 1,
            evidence_ids_json TEXT NOT NULL DEFAULT '[]',
            counterevidence_ids_json TEXT NOT NULL DEFAULT '[]',
            validation_notes TEXT,
            insight_id TEXT,
            provenance TEXT NOT NULL DEFAULT 'system_inferred',
            FOREIGN KEY (insight_id) REFERENCES insights(id)
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
            target_date TEXT,
            provenance TEXT NOT NULL DEFAULT 'user'
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
            provenance TEXT NOT NULL DEFAULT 'user',
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
            confidence REAL,
            provenance TEXT NOT NULL DEFAULT 'system_aggregated'
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

        -- FTS5 search index (contentless — we manage content manually)
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            object_type,
            object_id UNINDEXED,
            user_id UNINDEXED,
            content,
            effective_at UNINDEXED
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

        CREATE INDEX IF NOT EXISTS idx_activities_user_effective
        ON activities (user_id, effective_at);

        CREATE INDEX IF NOT EXISTS idx_metric_observations_user_effective
        ON metric_observations (user_id, effective_at);

        CREATE INDEX IF NOT EXISTS idx_insights_user_status
        ON insights (user_id, status);

        CREATE INDEX IF NOT EXISTS idx_heuristics_user_active
        ON heuristics (user_id, active);

        CREATE INDEX IF NOT EXISTS idx_protocol_executions_user_protocol
        ON protocol_executions (user_id, protocol_id);
        """
    )

    # Migration: add provenance column to tables that predate this schema version
    _migrate_add_column(conn, "source_documents", "provenance", "TEXT NOT NULL DEFAULT 'user'")
    _migrate_add_column(conn, "journal_entries", "provenance", "TEXT NOT NULL DEFAULT 'user'")
    _migrate_add_column(conn, "daily_checkins", "provenance", "TEXT NOT NULL DEFAULT 'user'")
    _migrate_add_column(conn, "goals", "provenance", "TEXT NOT NULL DEFAULT 'user'")
    _migrate_add_column(conn, "tasks", "provenance", "TEXT NOT NULL DEFAULT 'user'")
    _migrate_add_column(conn, "weekly_reviews", "provenance", "TEXT NOT NULL DEFAULT 'system_aggregated'")

    # Legacy migration: engagement_notes_json on weekly_reviews
    _migrate_add_column(conn, "weekly_reviews", "engagement_notes_json", "TEXT NOT NULL DEFAULT '[]'")

    conn.commit()


def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't already exist."""
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
