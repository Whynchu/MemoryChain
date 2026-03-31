from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import sqlite3
import uuid

from ..schemas import (
    Conversation,
    ConversationMessage,
    DailyCheckin,
    DailyCheckinCreate,
    Goal,
    GoalCreate,
    JournalEntry,
    JournalEntryCreate,
    SearchResult,
    SourceDocument,
    SourceDocumentCreate,
    Task,
    TaskCreate,
    WeeklyReview,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_to_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _to_json(value: dict | list) -> str:
    return json.dumps(value, ensure_ascii=True)


def _hash_source(raw_text: str, effective_at: datetime) -> str:
    payload = f"{effective_at.isoformat()}::{raw_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_source_by_hash(self, content_hash: str) -> SourceDocument | None:
        row = self.conn.execute(
            "SELECT * FROM source_documents WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()
        return self._row_to_source(row) if row else None

    def find_duplicate_source(
        self, *, raw_text: str, effective_at: datetime
    ) -> SourceDocument | None:
        return self.get_source_by_hash(_hash_source(raw_text, effective_at))

    def create_source_document(self, payload: SourceDocumentCreate) -> SourceDocument:
        now = _now_iso()
        source_id = _new_id("src")
        content_hash = _hash_source(payload.raw_text, payload.effective_at)
        self.conn.execute(
            """
            INSERT INTO source_documents (
                id, user_id, source_type, created_at, effective_at, title,
                raw_text, metadata_json, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                payload.user_id,
                payload.source_type,
                now,
                payload.effective_at.isoformat(),
                payload.title,
                payload.raw_text,
                _to_json(payload.metadata),
                content_hash,
            ),
        )
        self.conn.commit()
        return self.get_source_by_hash(content_hash)  # type: ignore[return-value]

    def create_journal_entry(self, payload: JournalEntryCreate) -> JournalEntry:
        now = _now_iso()
        entry_id = _new_id("je")
        self.conn.execute(
            """
            INSERT INTO journal_entries (
                id, user_id, source_document_id, created_at, effective_at,
                entry_type, title, text, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                payload.user_id,
                payload.source_document_id,
                now,
                payload.effective_at.isoformat(),
                payload.entry_type,
                payload.title,
                payload.text,
                _to_json(payload.tags),
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_journal(row)

    def list_journal_entries(self, user_id: str) -> list[JournalEntry]:
        rows = self.conn.execute(
            "SELECT * FROM journal_entries WHERE user_id = ? ORDER BY effective_at DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_journal(row) for row in rows]

    def create_checkin(self, payload: DailyCheckinCreate) -> DailyCheckin:
        now = _now_iso()
        checkin_id = _new_id("dc")
        self.conn.execute(
            """
            INSERT INTO daily_checkins (
                id, user_id, source_document_id, date, created_at, effective_at,
                sleep_hours, sleep_quality, mood, energy, body_weight,
                body_weight_unit, immediate_thoughts, pain_notes,
                hydration_start, hydration_unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkin_id,
                payload.user_id,
                payload.source_document_id,
                payload.date.isoformat(),
                now,
                payload.effective_at.isoformat(),
                payload.sleep_hours,
                payload.sleep_quality,
                payload.mood,
                payload.energy,
                payload.body_weight,
                payload.body_weight_unit,
                payload.immediate_thoughts,
                payload.pain_notes,
                payload.hydration_start,
                payload.hydration_unit,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM daily_checkins WHERE id = ?", (checkin_id,)
        ).fetchone()
        return self._row_to_checkin(row)

    def list_checkins(self, user_id: str) -> list[DailyCheckin]:
        rows = self.conn.execute(
            "SELECT * FROM daily_checkins WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_checkin(row) for row in rows]

    def create_goal(self, payload: GoalCreate) -> Goal:
        now = _now_iso()
        goal_id = _new_id("goal")
        self.conn.execute(
            """
            INSERT INTO goals (
                id, user_id, created_at, updated_at, title,
                description, status, priority, target_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                goal_id,
                payload.user_id,
                now,
                now,
                payload.title,
                payload.description,
                payload.status,
                payload.priority,
                _date_to_iso(payload.target_date),
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return self._row_to_goal(row)

    def list_goals(self, user_id: str) -> list[Goal]:
        rows = self.conn.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [self._row_to_goal(row) for row in rows]

    def create_task(self, payload: TaskCreate) -> Task:
        now = _now_iso()
        completed_at = now if payload.status == "done" else None
        task_id = _new_id("task")
        self.conn.execute(
            """
            INSERT INTO tasks (
                id, user_id, goal_id, created_at, updated_at, title, description,
                status, priority, due_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload.user_id,
                payload.goal_id,
                now,
                now,
                payload.title,
                payload.description,
                payload.status,
                payload.priority,
                payload.due_at.isoformat() if payload.due_at else None,
                completed_at,
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row)

    def list_tasks(self, user_id: str) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [self._row_to_task(row) for row in rows]


    def search(
        self,
        *,
        user_id: str,
        query: str | None = None,
        object_types: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        selected = set(object_types or ["source_document", "journal_entry", "daily_checkin", "task", "goal"])
        normalized_query = query.strip().lower() if query else None
        results: list[SearchResult] = []

        if "source_document" in selected:
            sql = """
                SELECT id, user_id, effective_at, title, raw_text, NULL AS source_document_id
                FROM source_documents
                WHERE user_id = ?
            """
            params: list[object] = [user_id]
            if date_from:
                sql += " AND date(effective_at) >= ?"
                params.append(date_from.isoformat())
            if date_to:
                sql += " AND date(effective_at) <= ?"
                params.append(date_to.isoformat())
            if normalized_query:
                sql += " AND (lower(raw_text) LIKE ? OR lower(COALESCE(title, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            sql += " ORDER BY effective_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                results.append(
                    SearchResult(
                        object_type="source_document",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["effective_at"]),
                        title=row["title"],
                        snippet=row["raw_text"][:220],
                        source_document_id=row["source_document_id"],
                    )
                )

        if "journal_entry" in selected:
            sql = """
                SELECT id, user_id, source_document_id, effective_at, title, text, tags_json
                FROM journal_entries
                WHERE user_id = ?
            """
            params = [user_id]
            if date_from:
                sql += " AND date(effective_at) >= ?"
                params.append(date_from.isoformat())
            if date_to:
                sql += " AND date(effective_at) <= ?"
                params.append(date_to.isoformat())
            if normalized_query:
                sql += " AND (lower(text) LIKE ? OR lower(COALESCE(title, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            if tag:
                sql += " AND lower(tags_json) LIKE ?"
                params.append(f'%"{tag.strip().lower()}"%')
            sql += " ORDER BY effective_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                tags = json.loads(row["tags_json"])
                results.append(
                    SearchResult(
                        object_type="journal_entry",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["effective_at"]),
                        title=row["title"],
                        snippet=row["text"][:220],
                        source_document_id=row["source_document_id"],
                        tags=tags,
                    )
                )

        if "daily_checkin" in selected:
            sql = """
                SELECT id, user_id, source_document_id, effective_at, date,
                       sleep_hours, mood, energy, immediate_thoughts, pain_notes
                FROM daily_checkins
                WHERE user_id = ?
            """
            params = [user_id]
            if date_from:
                sql += " AND date >= ?"
                params.append(date_from.isoformat())
            if date_to:
                sql += " AND date <= ?"
                params.append(date_to.isoformat())
            if normalized_query:
                sql += " AND (lower(COALESCE(immediate_thoughts, '')) LIKE ? OR lower(COALESCE(pain_notes, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            sql += " ORDER BY date DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                summary_parts: list[str] = []
                if row["sleep_hours"] is not None:
                    summary_parts.append(f"sleep {row['sleep_hours']}h")
                if row["mood"] is not None:
                    summary_parts.append(f"mood {row['mood']}/10")
                if row["energy"] is not None:
                    summary_parts.append(f"energy {row['energy']}/10")
                if row["immediate_thoughts"]:
                    summary_parts.append(str(row["immediate_thoughts"]))
                if row["pain_notes"]:
                    summary_parts.append(str(row["pain_notes"]))
                snippet = "; ".join(summary_parts) if summary_parts else "daily check-in"
                results.append(
                    SearchResult(
                        object_type="daily_checkin",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["effective_at"]),
                        title=f"Check-in {row['date']}",
                        snippet=snippet[:220],
                        source_document_id=row["source_document_id"],
                    )
                )

        if "task" in selected:
            sql = """
                SELECT id, user_id, goal_id, created_at, title, description, status
                FROM tasks
                WHERE user_id = ?
            """
            params = [user_id]
            if date_from:
                sql += " AND date(created_at) >= ?"
                params.append(date_from.isoformat())
            if date_to:
                sql += " AND date(created_at) <= ?"
                params.append(date_to.isoformat())
            if normalized_query:
                sql += " AND (lower(title) LIKE ? OR lower(COALESCE(description, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                description = row["description"] or ""
                snippet = f"[{row['status']}] {row['title']}"
                if description:
                    snippet += f" - {description}"
                results.append(
                    SearchResult(
                        object_type="task",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["created_at"]),
                        title=row["title"],
                        snippet=snippet[:220],
                        source_document_id=None,
                    )
                )

        if "goal" in selected:
            sql = """
                SELECT id, user_id, created_at, title, description, status
                FROM goals
                WHERE user_id = ?
            """
            params = [user_id]
            if date_from:
                sql += " AND date(created_at) >= ?"
                params.append(date_from.isoformat())
            if date_to:
                sql += " AND date(created_at) <= ?"
                params.append(date_to.isoformat())
            if normalized_query:
                sql += " AND (lower(title) LIKE ? OR lower(COALESCE(description, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                description = row["description"] or ""
                snippet = f"[{row['status']}] {row['title']}"
                if description:
                    snippet += f" - {description}"
                results.append(
                    SearchResult(
                        object_type="goal",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["created_at"]),
                        title=row["title"],
                        snippet=snippet[:220],
                        source_document_id=None,
                    )
                )

        results.sort(key=lambda item: item.effective_at, reverse=True)
        return results[:limit]
    def list_open_tasks(self, user_id: str, limit: int = 5) -> list[Task]:
        rows = self.conn.execute(
            """
            SELECT * FROM tasks
            WHERE user_id = ? AND status IN ('todo', 'in_progress')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_or_create_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        title: str | None = None,
    ) -> Conversation:
        if conversation_id:
            row = self.conn.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if row:
                return self._row_to_conversation(row)

        now = _now_iso()
        conv_id = _new_id("conv") if not conversation_id else conversation_id
        self.conn.execute(
            """
            INSERT INTO conversations (id, user_id, created_at, updated_at, title)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conv_id, user_id, now, now, title),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return self._row_to_conversation(row)

    def append_conversation_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        source_document_id: str | None = None,
    ) -> ConversationMessage:
        now = _now_iso()
        msg_id = _new_id("msg")
        self.conn.execute(
            """
            INSERT INTO conversation_messages (
                id, conversation_id, user_id, role, content, created_at, source_document_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, conversation_id, user_id, role, content, now, source_document_id),
        )
        self.conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM conversation_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        return self._row_to_message(row)

    def list_conversation_messages(
        self,
        *,
        conversation_id: str,
        limit: int = 12,
        user_id: str | None = None,
    ) -> list[ConversationMessage]:
        if user_id is None:
            rows = self.conn.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT m.*
                FROM conversation_messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE m.conversation_id = ? AND c.user_id = ?
                ORDER BY m.created_at DESC
                LIMIT ?
                """,
                (conversation_id, user_id, limit),
            ).fetchall()

        messages = [self._row_to_message(row) for row in rows]
        messages.reverse()
        return messages

    def list_recent_user_messages(
        self, *, user_id: str, limit: int = 10
    ) -> list[ConversationMessage]:
        rows = self.conn.execute(
            """
            SELECT * FROM conversation_messages
            WHERE user_id = ? AND role = 'user'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        messages = [self._row_to_message(row) for row in rows]
        messages.reverse()
        return messages

    def get_records_for_week(
        self, user_id: str, week_start: date, week_end: date
    ) -> tuple[list[JournalEntry], list[DailyCheckin], list[Task]]:
        entries = self.conn.execute(
            """
            SELECT * FROM journal_entries
            WHERE user_id = ? AND date(effective_at) BETWEEN ? AND ?
            ORDER BY effective_at ASC
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        checkins = self.conn.execute(
            """
            SELECT * FROM daily_checkins
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        tasks = self.conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return (
            [self._row_to_journal(row) for row in entries],
            [self._row_to_checkin(row) for row in checkins],
            [self._row_to_task(row) for row in tasks],
        )

    def create_weekly_review(
        self,
        *,
        user_id: str,
        week_start: date,
        week_end: date,
        summary: str,
        wins: list[str],
        slips: list[str],
        open_loops: list[str],
        recommended_next_actions: list[str],
        source_ids: list[str],
        confidence: float | None,
    ) -> WeeklyReview:
        review_id = _new_id("wr")
        now = _now_iso()
        self.conn.execute(
            """
            INSERT INTO weekly_reviews (
                id, user_id, created_at, week_start, week_end, summary,
                wins_json, slips_json, open_loops_json,
                recommended_next_actions_json, source_ids_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                user_id,
                now,
                week_start.isoformat(),
                week_end.isoformat(),
                summary,
                _to_json(wins),
                _to_json(slips),
                _to_json(open_loops),
                _to_json(recommended_next_actions),
                _to_json(source_ids),
                confidence,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM weekly_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return self._row_to_weekly_review(row)

    def list_weekly_reviews(self, user_id: str) -> list[WeeklyReview]:
        rows = self.conn.execute(
            "SELECT * FROM weekly_reviews WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [self._row_to_weekly_review(row) for row in rows]

    def _row_to_source(self, row: sqlite3.Row) -> SourceDocument:
        return SourceDocument(
            id=row["id"],
            user_id=row["user_id"],
            source_type=row["source_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            effective_at=datetime.fromisoformat(row["effective_at"]),
            title=row["title"],
            raw_text=row["raw_text"],
            metadata=json.loads(row["metadata_json"]),
            content_hash=row["content_hash"],
        )

    def _row_to_journal(self, row: sqlite3.Row) -> JournalEntry:
        return JournalEntry(
            id=row["id"],
            user_id=row["user_id"],
            source_document_id=row["source_document_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            effective_at=datetime.fromisoformat(row["effective_at"]),
            entry_type=row["entry_type"],
            title=row["title"],
            text=row["text"],
            tags=json.loads(row["tags_json"]),
        )

    def _row_to_checkin(self, row: sqlite3.Row) -> DailyCheckin:
        return DailyCheckin(
            id=row["id"],
            user_id=row["user_id"],
            source_document_id=row["source_document_id"],
            date=date.fromisoformat(row["date"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            effective_at=datetime.fromisoformat(row["effective_at"]),
            sleep_hours=row["sleep_hours"],
            sleep_quality=row["sleep_quality"],
            mood=row["mood"],
            energy=row["energy"],
            body_weight=row["body_weight"],
            body_weight_unit=row["body_weight_unit"],
            immediate_thoughts=row["immediate_thoughts"],
            pain_notes=row["pain_notes"],
            hydration_start=row["hydration_start"],
            hydration_unit=row["hydration_unit"],
        )

    def _row_to_goal(self, row: sqlite3.Row) -> Goal:
        return Goal(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            title=row["title"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            target_date=date.fromisoformat(row["target_date"]) if row["target_date"] else None,
        )

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            user_id=row["user_id"],
            goal_id=row["goal_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            title=row["title"],
            description=row["description"],
            status=row["status"],
            priority=row["priority"],
            due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )

    def _row_to_weekly_review(self, row: sqlite3.Row) -> WeeklyReview:
        return WeeklyReview(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            week_start=date.fromisoformat(row["week_start"]),
            week_end=date.fromisoformat(row["week_end"]),
            summary=row["summary"],
            wins=json.loads(row["wins_json"]),
            slips=json.loads(row["slips_json"]),
            open_loops=json.loads(row["open_loops_json"]),
            recommended_next_actions=json.loads(row["recommended_next_actions_json"]),
            source_ids=json.loads(row["source_ids_json"]),
            confidence=row["confidence"],
        )

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        return Conversation(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            title=row["title"],
        )

    def _row_to_message(self, row: sqlite3.Row) -> ConversationMessage:
        return ConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            source_document_id=row["source_document_id"],
        )





