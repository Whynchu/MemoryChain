from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import sqlite3
import uuid

from ..schemas import (
    Activity,
    ActivityCreate,
    AuditLogEntry,
    Conversation,
    ConversationMessage,
    DailyCheckin,
    DailyCheckinCreate,
    EngagementEvent,
    EngagementSummary,
    Goal,
    GoalCreate,
    GoalUpdate,
    Heuristic,
    HeuristicCreate,
    Insight,
    InsightCreate,
    InsightUpdate,
    JournalEntry,
    JournalEntryCreate,
    MetricObservation,
    MetricObservationCreate,
    PromptCycle,
    Protocol,
    ProtocolCreate,
    ProtocolExecution,
    ProtocolExecutionCreate,
    ProtocolUpdate,
    QuestionnaireTemplate,
    QuestionnaireTemplateCreate,
    QuestionnaireSession,
    QuestionnaireSessionCreate,
    SearchResult,
    SourceDocument,
    SourceDocumentCreate,
    Task,
    TaskCreate,
    TaskUpdate,
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
        self._index_for_search(object_type="source_document", object_id=source_id, user_id=payload.user_id, content=f"{payload.title or ''} {payload.raw_text}", effective_at=payload.effective_at.isoformat())
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
        self._index_for_search(object_type="journal_entry", object_id=entry_id, user_id=payload.user_id, content=f"{payload.title or ''} {payload.text}", effective_at=payload.effective_at.isoformat())
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
                hydration_start, hydration_unit, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.provenance,
            ),
        )
        self._index_for_search(object_type="daily_checkin", object_id=checkin_id, user_id=payload.user_id, content=f"{payload.immediate_thoughts or ''} {payload.pain_notes or ''}", effective_at=payload.effective_at.isoformat())
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
                description, status, priority, target_date, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.provenance,
            ),
        )
        self._index_for_search(object_type="goal", object_id=goal_id, user_id=payload.user_id, content=f"{payload.title} {payload.description or ''}", effective_at=now)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return self._row_to_goal(row)

    def list_goals(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Goal]:
        rows = self.conn.execute(
            """
            SELECT * FROM goals
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_goal(row) for row in rows]

    def get_goal(self, *, goal_id: str, user_id: str) -> Goal | None:
        row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id),
        ).fetchone()
        return self._row_to_goal(row) if row else None
    def update_goal(self, *, goal_id: str, user_id: str, payload: GoalUpdate) -> Goal | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            row = self.conn.execute(
                "SELECT * FROM goals WHERE id = ? AND user_id = ?",
                (goal_id, user_id),
            ).fetchone()
            return self._row_to_goal(row) if row else None

        existing_row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id),
        ).fetchone()
        if not existing_row:
            return None
        before_goal = self._row_to_goal(existing_row)

        now = _now_iso()
        fields: list[str] = []
        values: list[object] = []

        if "title" in updates:
            fields.append("title = ?")
            values.append(updates["title"])
        if "description" in updates:
            fields.append("description = ?")
            values.append(updates["description"])
        if "status" in updates:
            fields.append("status = ?")
            values.append(updates["status"])
        if "priority" in updates:
            fields.append("priority = ?")
            values.append(updates["priority"])
        if "target_date" in updates:
            fields.append("target_date = ?")
            values.append(_date_to_iso(updates["target_date"]))

        fields.append("updated_at = ?")
        values.append(now)
        values.extend([goal_id, user_id])

        cursor = self.conn.execute(
            f"UPDATE goals SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        if cursor.rowcount == 0:
            return None

        row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id),
        ).fetchone()
        updated_goal = self._row_to_goal(row) if row else None
        if updated_goal is not None:
            self._record_audit_log(
                user_id=user_id,
                entity_type="goal",
                entity_id=goal_id,
                action="update",
                before=before_goal.model_dump(mode="json"),
                after=updated_goal.model_dump(mode="json"),
                changed_fields=sorted(list(updates.keys())),
            )
            self.conn.commit()
        return updated_goal

    def create_task(self, payload: TaskCreate) -> Task:
        now = _now_iso()
        completed_at = now if payload.status == "done" else None
        task_id = _new_id("task")
        self.conn.execute(
            """
            INSERT INTO tasks (
                id, user_id, goal_id, created_at, updated_at, title, description,
                status, priority, due_at, completed_at, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.provenance,
            ),
        )
        self._index_for_search(object_type="task", object_id=task_id, user_id=payload.user_id, content=f"{payload.title} {payload.description or ''}", effective_at=now)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row)

    def list_tasks(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Task]:
        rows = self.conn.execute(
            """
            SELECT * FROM tasks
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, *, task_id: str, user_id: str) -> Task | None:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        return self._row_to_task(row) if row else None
    def update_task(self, *, task_id: str, user_id: str, payload: TaskUpdate) -> Task | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            row = self.conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
            return self._row_to_task(row) if row else None

        existing_row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        if not existing_row:
            return None
        before_task = self._row_to_task(existing_row)

        now = _now_iso()
        fields: list[str] = []
        values: list[object] = []

        if "title" in updates:
            fields.append("title = ?")
            values.append(updates["title"])
        if "goal_id" in updates:
            fields.append("goal_id = ?")
            values.append(updates["goal_id"])
        if "description" in updates:
            fields.append("description = ?")
            values.append(updates["description"])
        if "status" in updates:
            fields.append("status = ?")
            values.append(updates["status"])
            if updates["status"] == "done":
                fields.append("completed_at = ?")
                values.append(now)
            else:
                fields.append("completed_at = ?")
                values.append(None)
        if "priority" in updates:
            fields.append("priority = ?")
            values.append(updates["priority"])
        if "due_at" in updates:
            fields.append("due_at = ?")
            values.append(updates["due_at"].isoformat() if updates["due_at"] else None)

        fields.append("updated_at = ?")
        values.append(now)
        values.extend([task_id, user_id])

        cursor = self.conn.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        if cursor.rowcount == 0:
            return None

        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        updated_task = self._row_to_task(row) if row else None
        if updated_task is not None:
            self._record_audit_log(
                user_id=user_id,
                entity_type="task",
                entity_id=task_id,
                action="update",
                before=before_task.model_dump(mode="json"),
                after=updated_task.model_dump(mode="json"),
                changed_fields=sorted(list(updates.keys())),
            )
            self.conn.commit()
        return updated_task

    def _record_engagement_event(
        self,
        *,
        user_id: str,
        event_type: str,
        event_at: datetime,
        prompt_cycle_id: str | None = None,
        metadata: dict | None = None,
    ) -> EngagementEvent:
        event_id = _new_id("evt")
        created_at = _now_iso()
        metadata_value = metadata or {}
        self.conn.execute(
            """
            INSERT INTO engagement_events (
                id, user_id, prompt_cycle_id, event_type, event_at, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_id,
                prompt_cycle_id,
                event_type,
                event_at.isoformat(),
                _to_json(metadata_value),
                created_at,
            ),
        )
        row = self.conn.execute("SELECT * FROM engagement_events WHERE id = ?", (event_id,)).fetchone()
        return self._row_to_engagement_event(row)


    def _record_audit_log(
        self,
        *,
        user_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict,
        after: dict,
        changed_fields: list[str],
    ) -> AuditLogEntry:
        log_id = _new_id("audit")
        created_at = _now_iso()
        self.conn.execute(
            """
            INSERT INTO audit_logs (
                id, user_id, entity_type, entity_id, action,
                before_json, after_json, changed_fields_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                user_id,
                entity_type,
                entity_id,
                action,
                _to_json(before),
                _to_json(after),
                _to_json(changed_fields),
                created_at,
            ),
        )
        row = self.conn.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,)).fetchone()
        return self._row_to_audit_log(row)

    def list_audit_logs(
        self,
        *,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        rows = self.conn.execute(
            """
            SELECT * FROM audit_logs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_audit_log(row) for row in rows]

    def rollback_audit_log(
        self,
        *,
        user_id: str,
        audit_log_id: str,
    ) -> AuditLogEntry | None:
        row = self.conn.execute(
            "SELECT * FROM audit_logs WHERE id = ? AND user_id = ?",
            (audit_log_id, user_id),
        ).fetchone()
        if row is None:
            return None

        audit_entry = self._row_to_audit_log(row)
        if not audit_entry.before:
            raise ValueError("Audit entry has no restorable state")

        if audit_entry.entity_type == "goal":
            return self._rollback_goal(audit_entry=audit_entry)
        if audit_entry.entity_type == "task":
            return self._rollback_task(audit_entry=audit_entry)
        raise ValueError(f"Unsupported entity type for rollback: {audit_entry.entity_type}")

    def _rollback_goal(self, *, audit_entry: AuditLogEntry) -> AuditLogEntry:
        row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ? AND user_id = ?",
            (audit_entry.entity_id, audit_entry.user_id),
        ).fetchone()
        if row is None:
            raise ValueError("Goal not found for rollback")

        current_goal = self._row_to_goal(row)
        before_snapshot = audit_entry.before
        now = _now_iso()
        self.conn.execute(
            """
            UPDATE goals
            SET title = ?, description = ?, status = ?, priority = ?, target_date = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                before_snapshot.get("title"),
                before_snapshot.get("description"),
                before_snapshot.get("status"),
                before_snapshot.get("priority"),
                before_snapshot.get("target_date"),
                now,
                audit_entry.entity_id,
                audit_entry.user_id,
            ),
        )

        restored_row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ? AND user_id = ?",
            (audit_entry.entity_id, audit_entry.user_id),
        ).fetchone()
        restored_goal = self._row_to_goal(restored_row)
        rollback_log = self._record_audit_log(
            user_id=audit_entry.user_id,
            entity_type="goal",
            entity_id=audit_entry.entity_id,
            action="rollback",
            before=current_goal.model_dump(mode="json"),
            after=restored_goal.model_dump(mode="json"),
            changed_fields=self._changed_fields(
                before=current_goal.model_dump(mode="json"),
                after=restored_goal.model_dump(mode="json"),
            ),
        )
        self.conn.commit()
        return rollback_log

    def _rollback_task(self, *, audit_entry: AuditLogEntry) -> AuditLogEntry:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (audit_entry.entity_id, audit_entry.user_id),
        ).fetchone()
        if row is None:
            raise ValueError("Task not found for rollback")

        current_task = self._row_to_task(row)
        before_snapshot = audit_entry.before
        now = _now_iso()
        self.conn.execute(
            """
            UPDATE tasks
            SET title = ?, goal_id = ?, description = ?, status = ?, priority = ?,
                due_at = ?, completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                before_snapshot.get("title"),
                before_snapshot.get("goal_id"),
                before_snapshot.get("description"),
                before_snapshot.get("status"),
                before_snapshot.get("priority"),
                before_snapshot.get("due_at"),
                before_snapshot.get("completed_at"),
                now,
                audit_entry.entity_id,
                audit_entry.user_id,
            ),
        )

        restored_row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (audit_entry.entity_id, audit_entry.user_id),
        ).fetchone()
        restored_task = self._row_to_task(restored_row)
        rollback_log = self._record_audit_log(
            user_id=audit_entry.user_id,
            entity_type="task",
            entity_id=audit_entry.entity_id,
            action="rollback",
            before=current_task.model_dump(mode="json"),
            after=restored_task.model_dump(mode="json"),
            changed_fields=self._changed_fields(
                before=current_task.model_dump(mode="json"),
                after=restored_task.model_dump(mode="json"),
            ),
        )
        self.conn.commit()
        return rollback_log

    def _changed_fields(self, *, before: dict, after: dict) -> list[str]:
        all_fields = set(before.keys()) | set(after.keys())
        return sorted([field for field in all_fields if before.get(field) != after.get(field)])

    def create_prompt_cycle(
        self,
        *,
        user_id: str,
        cycle_date: date,
        scheduled_for: datetime,
        expires_at: datetime | None = None,
    ) -> PromptCycle:
        existing = self.conn.execute(
            "SELECT * FROM prompt_cycles WHERE user_id = ? AND cycle_date = ?",
            (user_id, cycle_date.isoformat()),
        ).fetchone()
        if existing:
            return self._row_to_prompt_cycle(existing)

        now = _now_iso()
        cycle_id = _new_id("pc")
        self.conn.execute(
            """
            INSERT INTO prompt_cycles (
                id, user_id, cycle_date, scheduled_for, sent_at, expires_at,
                status, response_source_document_id, response_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                user_id,
                cycle_date.isoformat(),
                scheduled_for.isoformat(),
                None,
                expires_at.isoformat() if expires_at else None,
                "pending",
                None,
                None,
                now,
                now,
            ),
        )
        self._record_engagement_event(
            user_id=user_id,
            event_type="prompt_scheduled",
            event_at=scheduled_for,
            prompt_cycle_id=cycle_id,
            metadata={"cycle_date": cycle_date.isoformat()},
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM prompt_cycles WHERE id = ?", (cycle_id,)).fetchone()
        return self._row_to_prompt_cycle(row)

    def list_prompt_cycles(
        self,
        *,
        user_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[PromptCycle]:
        sql = "SELECT * FROM prompt_cycles WHERE user_id = ?"
        params: list[object] = [user_id]
        if date_from:
            sql += " AND cycle_date >= ?"
            params.append(date_from.isoformat())
        if date_to:
            sql += " AND cycle_date <= ?"
            params.append(date_to.isoformat())
        sql += " ORDER BY cycle_date DESC, created_at DESC"
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_prompt_cycle(row) for row in rows]


    def get_engagement_summary(
        self,
        *,
        user_id: str,
        window_days: int,
        as_of: date | None = None,
    ) -> EngagementSummary:
        if window_days <= 0:
            raise ValueError("window_days must be positive")

        window_end = as_of or datetime.now(timezone.utc).date()
        window_start = window_end - timedelta(days=window_days - 1)

        rows = self.conn.execute(
            """
            SELECT *
            FROM prompt_cycles
            WHERE user_id = ? AND cycle_date BETWEEN ? AND ?
            ORDER BY cycle_date ASC
            """,
            (user_id, window_start.isoformat(), window_end.isoformat()),
        ).fetchall()

        total_cycles = len(rows)
        responded_cycles = 0
        missed_cycles = 0
        viewed_no_response_cycles = 0
        pending_cycles = 0

        response_delays: list[float] = []
        longest_nonresponse_streak = 0
        current_nonresponse_streak = 0

        for row in rows:
            status = row["status"]
            if status == "responded":
                responded_cycles += 1
                current_nonresponse_streak = 0
                if row["sent_at"] and row["response_at"]:
                    sent_at = datetime.fromisoformat(row["sent_at"])
                    response_at = datetime.fromisoformat(row["response_at"])
                    delta_minutes = (response_at - sent_at).total_seconds() / 60.0
                    if delta_minutes >= 0:
                        response_delays.append(delta_minutes)
            elif status == "missed":
                missed_cycles += 1
                current_nonresponse_streak += 1
            elif status == "viewed_no_response":
                viewed_no_response_cycles += 1
                current_nonresponse_streak += 1
            else:
                pending_cycles += 1
                current_nonresponse_streak += 1

            if current_nonresponse_streak > longest_nonresponse_streak:
                longest_nonresponse_streak = current_nonresponse_streak

        streak_resume_row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM engagement_events
            WHERE user_id = ?
              AND event_type = 'streak_resumed'
              AND date(event_at) BETWEEN ? AND ?
            """,
            (user_id, window_start.isoformat(), window_end.isoformat()),
        ).fetchone()
        streak_resume_count = int(streak_resume_row["count"]) if streak_resume_row else 0

        adherence_rate = (responded_cycles / total_cycles) if total_cycles > 0 else None
        open_without_entry_rate = (viewed_no_response_cycles / total_cycles) if total_cycles > 0 else None
        avg_response_delay_minutes = (
            sum(response_delays) / len(response_delays) if response_delays else None
        )

        return EngagementSummary(
            user_id=user_id,
            window_days=window_days,
            window_start=window_start,
            window_end=window_end,
            total_cycles=total_cycles,
            responded_cycles=responded_cycles,
            missed_cycles=missed_cycles,
            viewed_no_response_cycles=viewed_no_response_cycles,
            pending_cycles=pending_cycles,
            adherence_rate=adherence_rate,
            avg_response_delay_minutes=avg_response_delay_minutes,
            longest_nonresponse_streak_days=longest_nonresponse_streak,
            open_without_entry_rate=open_without_entry_rate,
            streak_resume_count=streak_resume_count,
        )
    def _transition_prompt_cycle(
        self,
        *,
        cycle_id: str,
        user_id: str,
        target_status: str | None,
        event_type: str,
        event_at: datetime,
        metadata: dict | None = None,
        response_source_document_id: str | None = None,
    ) -> PromptCycle | None:
        row = self.conn.execute(
            "SELECT * FROM prompt_cycles WHERE id = ? AND user_id = ?",
            (cycle_id, user_id),
        ).fetchone()
        if not row:
            return None

        current = self._row_to_prompt_cycle(row)

        if event_type == "prompt_sent":
            if current.sent_at is not None:
                raise ValueError("Prompt already sent")
        elif event_type == "prompt_viewed_no_response":
            if current.status != "pending":
                raise ValueError("Can only mark viewed from pending")
        elif event_type == "prompt_responded":
            if current.status not in ("pending", "viewed_no_response"):
                raise ValueError("Can only mark responded from pending or viewed_no_response")
            if not response_source_document_id:
                raise ValueError("response_source_document_id is required")
        elif event_type == "missed_checkin":
            if current.status not in ("pending", "viewed_no_response"):
                raise ValueError("Can only mark missed from pending or viewed_no_response")

        fields: list[str] = ["updated_at = ?"]
        values: list[object] = [_now_iso()]

        if event_type == "prompt_sent":
            fields.append("sent_at = ?")
            values.append(event_at.isoformat())

        if target_status is not None:
            fields.append("status = ?")
            values.append(target_status)

        if event_type == "prompt_responded":
            fields.append("response_source_document_id = ?")
            values.append(response_source_document_id)
            fields.append("response_at = ?")
            values.append(event_at.isoformat())

        values.extend([cycle_id, user_id])
        self.conn.execute(
            f"UPDATE prompt_cycles SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )

        self._record_engagement_event(
            user_id=user_id,
            event_type=event_type,
            event_at=event_at,
            prompt_cycle_id=cycle_id,
            metadata=metadata,
        )

        # If this response follows missed/viewed gaps, emit streak resumption signal.
        if event_type == "prompt_responded" and current.status in ("missed", "viewed_no_response"):
            self._record_engagement_event(
                user_id=user_id,
                event_type="streak_resumed",
                event_at=event_at,
                prompt_cycle_id=cycle_id,
                metadata={"from_status": current.status},
            )

        self.conn.commit()
        updated_row = self.conn.execute(
            "SELECT * FROM prompt_cycles WHERE id = ? AND user_id = ?",
            (cycle_id, user_id),
        ).fetchone()
        return self._row_to_prompt_cycle(updated_row) if updated_row else None

    def send_prompt_cycle(
        self,
        *,
        cycle_id: str,
        user_id: str,
        event_at: datetime,
        metadata: dict | None = None,
    ) -> PromptCycle | None:
        return self._transition_prompt_cycle(
            cycle_id=cycle_id,
            user_id=user_id,
            target_status=None,
            event_type="prompt_sent",
            event_at=event_at,
            metadata=metadata,
        )

    def mark_prompt_cycle_viewed(
        self,
        *,
        cycle_id: str,
        user_id: str,
        event_at: datetime,
        metadata: dict | None = None,
    ) -> PromptCycle | None:
        return self._transition_prompt_cycle(
            cycle_id=cycle_id,
            user_id=user_id,
            target_status="viewed_no_response",
            event_type="prompt_viewed_no_response",
            event_at=event_at,
            metadata=metadata,
        )

    def mark_prompt_cycle_responded(
        self,
        *,
        cycle_id: str,
        user_id: str,
        event_at: datetime,
        response_source_document_id: str,
        metadata: dict | None = None,
    ) -> PromptCycle | None:
        return self._transition_prompt_cycle(
            cycle_id=cycle_id,
            user_id=user_id,
            target_status="responded",
            event_type="prompt_responded",
            event_at=event_at,
            metadata=metadata,
            response_source_document_id=response_source_document_id,
        )

    def mark_prompt_cycle_missed(
        self,
        *,
        cycle_id: str,
        user_id: str,
        event_at: datetime,
        metadata: dict | None = None,
    ) -> PromptCycle | None:
        return self._transition_prompt_cycle(
            cycle_id=cycle_id,
            user_id=user_id,
            target_status="missed",
            event_type="missed_checkin",
            event_at=event_at,
            metadata=metadata,
        )

    def _index_for_search(
        self,
        *,
        object_type: str,
        object_id: str,
        user_id: str,
        content: str,
        effective_at: str,
    ) -> None:
        """Insert a row into the FTS5 search index."""
        self.conn.execute(
            "INSERT INTO search_index (object_type, object_id, user_id, content, effective_at) VALUES (?, ?, ?, ?, ?)",
            (object_type, object_id, user_id, content, effective_at),
        )

    def create_activity(self, payload: ActivityCreate) -> Activity:
        now = _now_iso()
        activity_id = _new_id("act")
        self.conn.execute(
            """
            INSERT INTO activities (
                id, user_id, source_document_id, created_at, effective_at,
                activity_type, started_at, ended_at, title, description,
                notes, metadata_json, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                payload.user_id,
                payload.source_document_id,
                now,
                payload.effective_at.isoformat(),
                payload.activity_type,
                payload.started_at.isoformat() if payload.started_at else None,
                payload.ended_at.isoformat() if payload.ended_at else None,
                payload.title,
                payload.description,
                payload.notes,
                _to_json(payload.metadata),
                payload.provenance,
            ),
        )
        self._index_for_search(
            object_type="activity",
            object_id=activity_id,
            user_id=payload.user_id,
            content=f"{payload.title} {payload.description or ''} {payload.notes or ''}",
            effective_at=payload.effective_at.isoformat(),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
        return self._row_to_activity(row)

    def list_activities(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Activity]:
        rows = self.conn.execute(
            "SELECT * FROM activities WHERE user_id = ? ORDER BY effective_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_activity(row) for row in rows]

    def get_activity(self, *, activity_id: str, user_id: str) -> Activity | None:
        row = self.conn.execute(
            "SELECT * FROM activities WHERE id = ? AND user_id = ?",
            (activity_id, user_id),
        ).fetchone()
        return self._row_to_activity(row) if row else None

    def create_metric_observation(self, payload: MetricObservationCreate) -> MetricObservation:
        now = _now_iso()
        metric_id = _new_id("mo")
        self.conn.execute(
            """
            INSERT INTO metric_observations (
                id, user_id, source_document_id, created_at, effective_at,
                metric_type, value, unit, value_type, notes, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric_id,
                payload.user_id,
                payload.source_document_id,
                now,
                payload.effective_at.isoformat(),
                payload.metric_type,
                payload.value,
                payload.unit,
                payload.value_type,
                payload.notes,
                payload.provenance,
            ),
        )
        self._index_for_search(
            object_type="metric_observation",
            object_id=metric_id,
            user_id=payload.user_id,
            content=f"{payload.metric_type}: {payload.value} {payload.unit or ''} {payload.notes or ''}",
            effective_at=payload.effective_at.isoformat(),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM metric_observations WHERE id = ?", (metric_id,)).fetchone()
        return self._row_to_metric_observation(row)

    def list_metric_observations(self, user_id: str, limit: int = 100, offset: int = 0) -> list[MetricObservation]:
        rows = self.conn.execute(
            "SELECT * FROM metric_observations WHERE user_id = ? ORDER BY effective_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_metric_observation(row) for row in rows]

    def get_metric_observation(self, *, metric_id: str, user_id: str) -> MetricObservation | None:
        row = self.conn.execute(
            "SELECT * FROM metric_observations WHERE id = ? AND user_id = ?",
            (metric_id, user_id),
        ).fetchone()
        return self._row_to_metric_observation(row) if row else None

    def create_protocol(self, payload: ProtocolCreate) -> Protocol:
        now = _now_iso()
        protocol_id = _new_id("proto")
        self.conn.execute(
            """
            INSERT INTO protocols (
                id, user_id, created_at, updated_at, name, category,
                description, steps_json, target_metrics_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocol_id,
                payload.user_id,
                now,
                now,
                payload.name,
                payload.category,
                payload.description,
                _to_json(payload.steps),
                _to_json(payload.target_metrics),
                payload.status,
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM protocols WHERE id = ?", (protocol_id,)).fetchone()
        return self._row_to_protocol(row)

    def list_protocols(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Protocol]:
        rows = self.conn.execute(
            "SELECT * FROM protocols WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [self._row_to_protocol(row) for row in rows]

    def get_protocol(self, *, protocol_id: str, user_id: str) -> Protocol | None:
        row = self.conn.execute(
            "SELECT * FROM protocols WHERE id = ? AND user_id = ?",
            (protocol_id, user_id),
        ).fetchone()
        return self._row_to_protocol(row) if row else None

    def update_protocol(self, *, protocol_id: str, user_id: str, payload: ProtocolUpdate) -> Protocol | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self.get_protocol(protocol_id=protocol_id, user_id=user_id)

        row = self.conn.execute(
            "SELECT * FROM protocols WHERE id = ? AND user_id = ?",
            (protocol_id, user_id),
        ).fetchone()
        if not row:
            return None

        now = _now_iso()
        fields: list[str] = []
        values: list[object] = []
        for key in ("name", "category", "description", "status"):
            if key in updates:
                fields.append(f"{key} = ?")
                values.append(updates[key])
        if "steps" in updates:
            fields.append("steps_json = ?")
            values.append(_to_json(updates["steps"]))
        if "target_metrics" in updates:
            fields.append("target_metrics_json = ?")
            values.append(_to_json(updates["target_metrics"]))
        fields.append("updated_at = ?")
        values.append(now)
        values.extend([protocol_id, user_id])
        self.conn.execute(
            f"UPDATE protocols SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        self.conn.commit()
        return self.get_protocol(protocol_id=protocol_id, user_id=user_id)

    def create_protocol_execution(self, payload: ProtocolExecutionCreate) -> ProtocolExecution:
        now = _now_iso()
        exec_id = _new_id("pexec")
        self.conn.execute(
            """
            INSERT INTO protocol_executions (
                id, user_id, protocol_id, source_document_id, created_at,
                executed_at, completion_status, notes, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exec_id,
                payload.user_id,
                payload.protocol_id,
                payload.source_document_id,
                now,
                payload.executed_at.isoformat(),
                payload.completion_status,
                payload.notes,
                payload.provenance,
            ),
        )
        self._index_for_search(
            object_type="protocol_execution",
            object_id=exec_id,
            user_id=payload.user_id,
            content=f"{payload.completion_status} {payload.notes or ''}",
            effective_at=payload.executed_at.isoformat(),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM protocol_executions WHERE id = ?", (exec_id,)).fetchone()
        return self._row_to_protocol_execution(row)

    def list_protocol_executions(self, user_id: str, protocol_id: str | None = None, limit: int = 100, offset: int = 0) -> list[ProtocolExecution]:
        if protocol_id:
            rows = self.conn.execute(
                "SELECT * FROM protocol_executions WHERE user_id = ? AND protocol_id = ? ORDER BY executed_at DESC LIMIT ? OFFSET ?",
                (user_id, protocol_id, limit, offset),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM protocol_executions WHERE user_id = ? ORDER BY executed_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [self._row_to_protocol_execution(row) for row in rows]

    def create_insight(self, payload: InsightCreate) -> Insight:
        now = _now_iso()
        insight_id = _new_id("ins")
        self.conn.execute(
            """
            INSERT INTO insights (
                id, user_id, created_at, title, summary, confidence, status,
                evidence_ids_json, counterevidence_ids_json,
                time_window_start, time_window_end, detector_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight_id,
                payload.user_id,
                now,
                payload.title,
                payload.summary,
                payload.confidence,
                payload.status,
                _to_json(payload.evidence_ids),
                _to_json(payload.counterevidence_ids),
                _date_to_iso(payload.time_window_start),
                _date_to_iso(payload.time_window_end),
                payload.detector_key,
            ),
        )
        self._index_for_search(
            object_type="insight",
            object_id=insight_id,
            user_id=payload.user_id,
            content=f"{payload.title} {payload.summary}",
            effective_at=now,
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()
        insight = self._row_to_insight(row)
        self._record_audit_log(
            user_id=payload.user_id,
            entity_type="insight",
            entity_id=insight_id,
            action="create",
            before={},
            after=insight.model_dump(mode="json"),
            changed_fields=["title", "summary", "confidence", "status", "detector_key"],
        )
        self.conn.commit()
        return insight

    def list_insights(self, user_id: str, status: str | None = None, limit: int = 100, offset: int = 0) -> list[Insight]:
        sql = "SELECT * FROM insights WHERE user_id = ?"
        params: list[object] = [user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_insight(row) for row in rows]

    def get_insight(self, *, insight_id: str, user_id: str) -> Insight | None:
        row = self.conn.execute(
            "SELECT * FROM insights WHERE id = ? AND user_id = ?",
            (insight_id, user_id),
        ).fetchone()
        return self._row_to_insight(row) if row else None

    def update_insight(self, *, insight_id: str, user_id: str, payload: InsightUpdate) -> Insight | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self.get_insight(insight_id=insight_id, user_id=user_id)

        existing = self.get_insight(insight_id=insight_id, user_id=user_id)
        if not existing:
            return None

        fields: list[str] = []
        values: list[object] = []
        for key in ("title", "summary", "confidence", "status"):
            if key in updates:
                fields.append(f"{key} = ?")
                values.append(updates[key])
        values.extend([insight_id, user_id])
        self.conn.execute(
            f"UPDATE insights SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        self._record_audit_log(
            user_id=user_id,
            entity_type="insight",
            entity_id=insight_id,
            action="update",
            before=existing.model_dump(mode="json"),
            after={**existing.model_dump(mode="json"), **updates},
            changed_fields=sorted(list(updates.keys())),
        )
        self.conn.commit()
        return self.get_insight(insight_id=insight_id, user_id=user_id)

    def create_heuristic(self, payload: HeuristicCreate) -> Heuristic:
        now = _now_iso()
        heuristic_id = _new_id("heur")
        self.conn.execute(
            """
            INSERT INTO heuristics (
                id, user_id, created_at, updated_at, rule, source_type,
                confidence, active, evidence_ids_json, counterevidence_ids_json,
                validation_notes, insight_id, promotion_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                heuristic_id,
                payload.user_id,
                now,
                now,
                payload.rule,
                payload.source_type,
                payload.confidence,
                1,
                _to_json(payload.evidence_ids),
                _to_json(payload.counterevidence_ids),
                payload.validation_notes,
                payload.insight_id,
                _to_json(payload.promotion_snapshot) if payload.promotion_snapshot else None,
            ),
        )
        self._index_for_search(
            object_type="heuristic",
            object_id=heuristic_id,
            user_id=payload.user_id,
            content=f"{payload.rule} {payload.validation_notes or ''}",
            effective_at=now,
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM heuristics WHERE id = ?", (heuristic_id,)).fetchone()
        heuristic = self._row_to_heuristic(row)
        self._record_audit_log(
            user_id=payload.user_id,
            entity_type="heuristic",
            entity_id=heuristic_id,
            action="create",
            before={},
            after=heuristic.model_dump(mode="json"),
            changed_fields=["rule", "source_type", "confidence", "active", "insight_id"],
        )
        self.conn.commit()
        return heuristic

    def list_heuristics(self, user_id: str, active_only: bool = False, limit: int = 100, offset: int = 0) -> list[Heuristic]:
        sql = "SELECT * FROM heuristics WHERE user_id = ?"
        params: list[object] = [user_id]
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [self._row_to_heuristic(row) for row in rows]

    def get_heuristic(self, *, heuristic_id: str, user_id: str) -> Heuristic | None:
        row = self.conn.execute(
            "SELECT * FROM heuristics WHERE id = ? AND user_id = ?",
            (heuristic_id, user_id),
        ).fetchone()
        return self._row_to_heuristic(row) if row else None

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
        selected = set(object_types or [
            "source_document", "journal_entry", "daily_checkin", "task", "goal",
            "activity", "metric_observation",
        ])
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

        if "activity" in selected:
            sql = """
                SELECT id, user_id, source_document_id, effective_at, title, description, activity_type
                FROM activities
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
                sql += " AND (lower(title) LIKE ? OR lower(COALESCE(description, '')) LIKE ? OR lower(COALESCE(activity_type, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern, pattern])
            sql += " ORDER BY effective_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                snippet = f"[{row['activity_type']}] {row['title']}"
                if row["description"]:
                    snippet += f" - {row['description']}"
                results.append(
                    SearchResult(
                        object_type="activity",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["effective_at"]),
                        title=row["title"],
                        snippet=snippet[:220],
                        source_document_id=row["source_document_id"],
                    )
                )

        if "metric_observation" in selected:
            sql = """
                SELECT id, user_id, source_document_id, effective_at, metric_type, value, unit, notes
                FROM metric_observations
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
                sql += " AND (lower(metric_type) LIKE ? OR lower(COALESCE(notes, '')) LIKE ?)"
                pattern = f"%{normalized_query}%"
                params.extend([pattern, pattern])
            sql += " ORDER BY effective_at DESC LIMIT ?"
            params.append(limit)
            rows = self.conn.execute(sql, tuple(params)).fetchall()
            for row in rows:
                snippet = f"{row['metric_type']}: {row['value']}"
                if row["unit"]:
                    snippet += f" {row['unit']}"
                if row["notes"]:
                    snippet += f" ({row['notes']})"
                results.append(
                    SearchResult(
                        object_type="metric_observation",
                        object_id=row["id"],
                        user_id=row["user_id"],
                        effective_at=datetime.fromisoformat(row["effective_at"]),
                        title=row["metric_type"],
                        snippet=snippet[:220],
                        source_document_id=row["source_document_id"],
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

    def get_activities_for_week(
        self, user_id: str, week_start: date, week_end: date
    ) -> list[Activity]:
        rows = self.conn.execute(
            """
            SELECT * FROM activities
            WHERE user_id = ? AND date(effective_at) BETWEEN ? AND ?
            ORDER BY effective_at ASC
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        return [self._row_to_activity(row) for row in rows]

    def get_metrics_for_week(
        self, user_id: str, week_start: date, week_end: date
    ) -> list[MetricObservation]:
        rows = self.conn.execute(
            """
            SELECT * FROM metric_observations
            WHERE user_id = ? AND date(effective_at) BETWEEN ? AND ?
            ORDER BY effective_at ASC
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        return [self._row_to_metric_observation(row) for row in rows]

    def get_insights_for_week(
        self, user_id: str, week_start: date, week_end: date
    ) -> list[Insight]:
        """Return insights created or updated during the given week."""
        rows = self.conn.execute(
            """
            SELECT * FROM insights
            WHERE user_id = ? AND date(created_at) BETWEEN ? AND ?
            ORDER BY created_at ASC
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        return [self._row_to_insight(row) for row in rows]

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
        engagement_notes: list[str],
        insight_mentions: list[str] | None = None,
        activity_summary: list[str] | None = None,
        metric_highlights: list[str] | None = None,
        sparse_data_flags: list[str] | None = None,
        notable_entries: list[str] | None = None,
        llm_narrative: str | None = None,
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
                recommended_next_actions_json, engagement_notes_json,
                insight_mentions_json, activity_summary_json,
                metric_highlights_json, sparse_data_flags_json,
                notable_entries_json, llm_narrative,
                source_ids_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                _to_json(engagement_notes),
                _to_json(insight_mentions or []),
                _to_json(activity_summary or []),
                _to_json(metric_highlights or []),
                _to_json(sparse_data_flags or []),
                _to_json(notable_entries or []),
                llm_narrative,
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
            engagement_notes=json.loads(row["engagement_notes_json"] or "[]"),
            insight_mentions=json.loads(row["insight_mentions_json"] or "[]"),
            activity_summary=json.loads(row["activity_summary_json"] or "[]"),
            metric_highlights=json.loads(row["metric_highlights_json"] or "[]"),
            sparse_data_flags=json.loads(row["sparse_data_flags_json"] or "[]"),
            notable_entries=json.loads(row["notable_entries_json"] or "[]"),
            llm_narrative=row["llm_narrative"],
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












    def _row_to_audit_log(self, row: sqlite3.Row) -> AuditLogEntry:
        return AuditLogEntry(
            id=row["id"],
            user_id=row["user_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            action=row["action"],
            before=json.loads(row["before_json"]),
            after=json.loads(row["after_json"]),
            changed_fields=json.loads(row["changed_fields_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    def _row_to_prompt_cycle(self, row: sqlite3.Row) -> PromptCycle:
        return PromptCycle(
            id=row["id"],
            user_id=row["user_id"],
            cycle_date=date.fromisoformat(row["cycle_date"]),
            scheduled_for=datetime.fromisoformat(row["scheduled_for"]),
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            status=row["status"],
            response_source_document_id=row["response_source_document_id"],
            response_at=datetime.fromisoformat(row["response_at"]) if row["response_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_engagement_event(self, row: sqlite3.Row) -> EngagementEvent:
        return EngagementEvent(
            id=row["id"],
            user_id=row["user_id"],
            prompt_cycle_id=row["prompt_cycle_id"],
            event_type=row["event_type"],
            event_at=datetime.fromisoformat(row["event_at"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_activity(self, row: sqlite3.Row) -> Activity:
        return Activity(
            id=row["id"],
            user_id=row["user_id"],
            source_document_id=row["source_document_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            effective_at=datetime.fromisoformat(row["effective_at"]),
            activity_type=row["activity_type"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            title=row["title"],
            description=row["description"],
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]),
            provenance=row["provenance"],
        )

    def _row_to_metric_observation(self, row: sqlite3.Row) -> MetricObservation:
        return MetricObservation(
            id=row["id"],
            user_id=row["user_id"],
            source_document_id=row["source_document_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            effective_at=datetime.fromisoformat(row["effective_at"]),
            metric_type=row["metric_type"],
            value=row["value"],
            unit=row["unit"],
            value_type=row["value_type"],
            notes=row["notes"],
            provenance=row["provenance"],
        )

    def _row_to_protocol(self, row: sqlite3.Row) -> Protocol:
        return Protocol(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            name=row["name"],
            category=row["category"],
            description=row["description"],
            steps=json.loads(row["steps_json"]),
            target_metrics=json.loads(row["target_metrics_json"]),
            status=row["status"],
            provenance=row["provenance"],
        )

    def _row_to_protocol_execution(self, row: sqlite3.Row) -> ProtocolExecution:
        return ProtocolExecution(
            id=row["id"],
            user_id=row["user_id"],
            protocol_id=row["protocol_id"],
            source_document_id=row["source_document_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            executed_at=datetime.fromisoformat(row["executed_at"]),
            completion_status=row["completion_status"],
            notes=row["notes"],
            provenance=row["provenance"],
        )

    def _row_to_insight(self, row: sqlite3.Row) -> Insight:
        return Insight(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            title=row["title"],
            summary=row["summary"],
            confidence=row["confidence"],
            status=row["status"],
            evidence_ids=json.loads(row["evidence_ids_json"]),
            counterevidence_ids=json.loads(row["counterevidence_ids_json"]),
            time_window_start=date.fromisoformat(row["time_window_start"]) if row["time_window_start"] else None,
            time_window_end=date.fromisoformat(row["time_window_end"]) if row["time_window_end"] else None,
            detector_key=row["detector_key"],
            provenance=row["provenance"],
        )

    def _row_to_heuristic(self, row: sqlite3.Row) -> Heuristic:
        return Heuristic(
            id=row["id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            rule=row["rule"],
            source_type=row["source_type"],
            confidence=row["confidence"],
            active=bool(row["active"]),
            evidence_ids=json.loads(row["evidence_ids_json"]),
            counterevidence_ids=json.loads(row["counterevidence_ids_json"]),
            validation_notes=row["validation_notes"],
            insight_id=row["insight_id"],
            promotion_snapshot=json.loads(row["promotion_snapshot"]) if row["promotion_snapshot"] else None,
            provenance=row["provenance"],
        )

    # Questionnaire Template methods
    def create_questionnaire_template(self, template: QuestionnaireTemplateCreate) -> QuestionnaireTemplate:
        now = datetime.now(timezone.utc)
        template_id = _new_id("qt")
        
        self.conn.execute(
            """
            INSERT INTO questionnaire_templates (
                id, user_id, name, description, questions_json, target_objects_json,
                created_at, updated_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                template.user_id,
                template.name,
                template.description,
                json.dumps([q.model_dump() for q in template.questions]),
                json.dumps(template.target_objects),
                now.isoformat(),
                now.isoformat(),
                1,
            ),
        )
        self.conn.commit()
        
        row = self.conn.execute(
            "SELECT * FROM questionnaire_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return self._row_to_questionnaire_template(row)

    def list_questionnaire_templates(self, user_id: str, active_only: bool = True) -> list[QuestionnaireTemplate]:
        if active_only:
            rows = self.conn.execute(
                "SELECT * FROM questionnaire_templates WHERE user_id = ? AND active = 1 ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM questionnaire_templates WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [self._row_to_questionnaire_template(row) for row in rows]

    def get_questionnaire_template(self, template_id: str, user_id: str) -> QuestionnaireTemplate | None:
        row = self.conn.execute(
            "SELECT * FROM questionnaire_templates WHERE id = ? AND user_id = ?",
            (template_id, user_id),
        ).fetchone()
        return self._row_to_questionnaire_template(row) if row else None

    # Questionnaire Session methods
    def create_questionnaire_session(self, session: QuestionnaireSessionCreate) -> QuestionnaireSession:
        now = datetime.now(timezone.utc)
        session_id = _new_id("qs")
        
        self.conn.execute(
            """
            INSERT INTO questionnaire_sessions (
                id, user_id, template_id, conversation_id, status,
                current_question_index, answers_json, raw_responses_json, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                session.user_id,
                session.template_id,
                session.conversation_id,
                "in_progress",
                0,
                "{}",
                "{}",
                now.isoformat(),
            ),
        )
        self.conn.commit()
        
        row = self.conn.execute(
            "SELECT * FROM questionnaire_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_questionnaire_session(row)

    def get_questionnaire_session(self, session_id: str, user_id: str) -> QuestionnaireSession | None:
        row = self.conn.execute(
            "SELECT * FROM questionnaire_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        return self._row_to_questionnaire_session(row) if row else None

    def update_questionnaire_session(
        self, 
        session_id: str, 
        user_id: str,
        current_question_index: int | None = None,
        answers: dict | None = None,
        raw_responses: dict | None = None,
        status: str | None = None
    ) -> QuestionnaireSession | None:
        # First get current session
        session = self.get_questionnaire_session(session_id, user_id)
        if not session:
            return None
            
        # Update fields that were provided
        now = datetime.now(timezone.utc)
        updates = []
        params = []
        
        if current_question_index is not None:
            updates.append("current_question_index = ?")
            params.append(current_question_index)
        
        if answers is not None:
            updates.append("answers_json = ?")
            params.append(json.dumps(answers))
            
        if raw_responses is not None:
            updates.append("raw_responses_json = ?") 
            params.append(json.dumps(raw_responses))
            
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status == "completed":
                updates.append("completed_at = ?")
                params.append(now.isoformat())
        
        if not updates:
            return session
            
        query = f"UPDATE questionnaire_sessions SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        params.extend([session_id, user_id])
        
        self.conn.execute(query, params)
        self.conn.commit()
        
        return self.get_questionnaire_session(session_id, user_id)

    def get_active_questionnaire_session(self, user_id: str, conversation_id: str | None = None) -> QuestionnaireSession | None:
        """Get the current in-progress questionnaire session for a user/conversation."""
        if conversation_id:
            row = self.conn.execute(
                """
                SELECT * FROM questionnaire_sessions 
                WHERE user_id = ? AND conversation_id = ? AND status = 'in_progress'
                ORDER BY started_at DESC LIMIT 1
                """,
                (user_id, conversation_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT * FROM questionnaire_sessions 
                WHERE user_id = ? AND status = 'in_progress'
                ORDER BY started_at DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return self._row_to_questionnaire_session(row) if row else None

    def _row_to_questionnaire_template(self, row: sqlite3.Row) -> QuestionnaireTemplate:
        from ..schemas import QuestionDef  # Import here to avoid circular imports
        
        questions_data = json.loads(row["questions_json"])
        questions = [QuestionDef(**q) for q in questions_data]
        
        return QuestionnaireTemplate(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row["description"],
            questions=questions,
            target_objects=json.loads(row["target_objects_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            active=bool(row["active"]),
        )

    def _row_to_questionnaire_session(self, row: sqlite3.Row) -> QuestionnaireSession:
        return QuestionnaireSession(
            id=row["id"],
            user_id=row["user_id"],
            template_id=row["template_id"],
            conversation_id=row["conversation_id"],
            status=row["status"],
            current_question_index=row["current_question_index"],
            answers=json.loads(row["answers_json"]),
            raw_responses=json.loads(row["raw_responses_json"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )














