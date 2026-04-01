# MemoryChain

**A personal memory and execution backend that turns daily logs and interactions into structured, queryable behavioral data.**

MemoryChain separates *observations* (what happened) from *interpretations* (patterns) from *operational rules* (what to do about it). This prevents casual journal entries from accidentally becoming execution constraints.

**Current state:** V0.2.0 — Backend is functional and tested. Ready for LLM extraction and insight engine.

---

## What It Can Do Right Now ✅

**Core Ingestion:**
- Capture chat messages and persist conversation memory
- Extract structured objects from chat text (deterministic parsing):
  - `JournalEntry` — reflective content
  - `DailyCheckin` — sleep, mood, energy, metrics
  - `Task` — from `todo:` prefix or chat context
  - `Goal` — explicit goals or implied
- Store as immutable `SourceDocument` with content hash (dedup)

**Data Management:**
- Create, list, fetch, and update core objects (goals, tasks, journal entries, check-ins)
- Pagination support (`limit`/`offset`)
- Full audit logging for goal/task updates with rollback capability
- Tag-based search and date range filtering

**Analysis & Synthesis:**
- Generate weekly reviews with continuity-aware engagement metrics
  - Adherence rates (7d/30d), missed cycles, streak gaps
- Guided prompt bundles (what to review, what's open, what's recent)
- Keyword + type + date range search across all objects

**Continuity Tracking:**
- Prompt cycle lifecycle (`pending` → `viewed_no_response` → `responded` or `missed`)
- Engagement events and event log (append-only)
- Engagement summary metrics (7d / 30d windows)
- Track presence and absence as separate signals

---

## What It Is Not Yet ⚠️

- **Missing V1 objects** — Activity, MetricObservation, Protocol, ProtocolExecution, Insight, and Heuristic have no tables/CRUD yet
- **No `provenance` column** — Schema rules require it on all objects; not yet implemented
- **LLM extraction not yet wired** — Config exists, but deterministic parsing is still the default
- **No insight/heuristic engine** — Schemas exist, promotion logic doesn't
- **No frontend** — API-first; use curl, Postman, or CLI
- **No semantic search** — Keyword search only (no FTS5 or embeddings)
- **No multi-user** — Single-user with static API key
- **Transaction gaps** — Some multi-step writes use separate commits (audit + entity)

---

## Next Steps 🚀

**See [NEXT_STEPS.md](./NEXT_STEPS.md) for the full prioritized roadmap.**

**Immediate priorities:**
1. **Phase 0: Foundation fixes** — Add missing tables, provenance, fix transactions, FTS5, unify extraction service
2. **Phase 1: Real data extraction** — Build WHYNN log parser, field extractors, LLM for freeform, bulk import
3. **Phase 2: Insight engine** — Sleep-mood detector, promotion/rejection flow
4. **Phase 3: Weekly review + audit** — LLM polish, full audit coverage
5. **Phase 4: CLI + daily workflow** — Make it actually usable

**Estimated to MVP:** ~8–10 weeks

## Repo Layout

- `apps/api` — FastAPI backend (Python 3.11+)
  - `routers/` — API endpoints (chat, ingest, goals, tasks, journal, etc.)
  - `services/` — Business logic (ingestion, chat, LLM, reviews)
  - `storage/` — Database layer (SQLite, repository pattern)
  - `schemas.py` — Pydantic models for all objects
- `docs/` — Architecture, schemas, design decisions
  - `NEXT_STEPS.md` — Prioritized roadmap to MVP
  - `OPEN_DECISIONS.md` — Decision framework (locked and unlocked choices)
  - `architecture/` — System design and continuity tracking plan
  - `schemas/` — Object definitions and validation rules
- `users/` — User data and logs (WHYNN historical logs in `users/Sam/logs/`)
- `core/` — Legacy reference materials

## Quick Start (API)

1. **Install dependencies:**

```bash
cd apps/api
python -m pip install -e .
python -m pip install pytest
```

2. **Set environment variables (optional):**

```bash
export MEMORYCHAIN_API_KEY=your-secret-key
export MEMORYCHAIN_DB_PATH=./memorychain.db
export MEMORYCHAIN_LLM_PROVIDER=openai  # or 'local'
export OPENAI_API_KEY=sk-...  # if using OpenAI
```

3. **Run the API:**

```bash
python -m uvicorn memorychain_api.main:app --reload
```

4. **API is live at** `http://localhost:8000`
   - Docs: `http://localhost:8000/docs`
   - Default auth header: `X-API-Key: dev-key`

5. **Run tests:**

```bash
pytest tests/test_api.py -v
```

---

## Usage Example

**Chat ingestion:**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-1",
    "message": "Had great sleep last night. 8 hours, felt refreshed. Planning a workout later.",
    "conversation_id": "conv-123"
  }'
```

This extracts and stores:
- `SourceDocument` (raw message)
- `JournalEntry` (the reflection)
- `DailyCheckin` (sleep: 8h)
- `Activity` (workout planned)

**Search:**

```bash
curl "http://localhost:8000/api/v1/search?q=workout&type=journal_entry" \
  -H "X-API-Key: dev-key"
```

**Weekly review:**

```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-1",
    "from": "2026-03-24",
    "to": "2026-03-31"
  }'
```

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `MEMORYCHAIN_API_KEY` | `dev-key` | Static key for auth; upgrade to JWT if multi-user |
| `MEMORYCHAIN_DB_PATH` | `memorychain.db` | SQLite database file |
| `MEMORYCHAIN_LLM_PROVIDER` | `local` | `local` or `openai` |
| `MEMORYCHAIN_LLM_MODEL` | `gpt-4o-mini` | OpenAI model (if provider is openai) |
| `OPENAI_API_KEY` | *(required if provider is openai)* | Your OpenAI API key |

---

## Current API Surface

### Health
- `GET /health` — System status

### Chat (Conversation Memory)
- `POST /api/v1/chat` — Send message, extract objects, store in memory
- `GET /api/v1/conversations/{conversation_id}/messages` — Retrieve conversation

### Ingestion
- `POST /api/v1/ingest` — Ingest raw SourceDocument + optionally structured objects

### Core Objects
- `POST /api/v1/goals` — Create goal
- `GET /api/v1/goals?limit=10&offset=0` — List with pagination
- `GET /api/v1/goals/{goal_id}` — Fetch detail
- `PUT /api/v1/goals/{goal_id}` — Update

- `POST /api/v1/tasks` — Create task
- `GET /api/v1/tasks?limit=10&offset=0` — List
- `GET /api/v1/tasks/{task_id}` — Fetch detail
- `PUT /api/v1/tasks/{task_id}` — Update (includes status changes)

- `GET /api/v1/journal` — List entries
- `GET /api/v1/checkins` — List daily checkins

### Analysis
- `POST /api/v1/reviews/generate` — Generate weekly review for date range
- `GET /api/v1/prompts/guided` — Get guided prompt bundle (what to focus on)

### Search & Retrieval
- `GET /api/v1/search?q=...&type=...&from=...&to=...&tag=...` — Search across all objects

### Continuity Tracking
- `POST /api/v1/prompt-cycles/{id}/viewed` — Mark prompt as viewed
- `POST /api/v1/prompt-cycles/{id}/responded` — Record response
- `POST /api/v1/prompt-cycles/{id}/missed` — Record missed checkin
- `GET /api/v1/engagement/summary?window=7d|30d` — Adherence metrics

### Audit & Corrections
- `GET /api/v1/audit-log?object_id=...&object_type=...` — View change history
- `POST /api/v1/audit-log/{entry_id}/rollback` — Restore to previous state

---

## Testing

All 16 tests pass:

```
tests/test_api.py::test_health_open PASSED
tests/test_api.py::test_auth_required PASSED
tests/test_api.py::test_chat_creates_memory_objects PASSED
tests/test_api.py::test_search_filters_by_type_and_keyword PASSED
tests/test_api.py::test_search_tag_and_date_filters PASSED
tests/test_api.py::test_guided_prompts_returns_bundles PASSED
tests/test_api.py::test_update_goal PASSED
tests/test_api.py::test_update_task_status_sets_and_clears_completed_at PASSED
tests/test_api.py::test_prompt_cycle_lifecycle PASSED
tests/test_api.py::test_prompt_cycle_invalid_transition_returns_conflict PASSED
tests/test_api.py::test_engagement_summary_metrics PASSED
tests/test_api.py::test_weekly_review_includes_engagement_signals PASSED
tests/test_api.py::test_audit_log_records_goal_and_task_updates PASSED
tests/test_api.py::test_audit_log_rollback_restores_goal_state PASSED
tests/test_api.py::test_goal_detail_and_pagination PASSED
tests/test_api.py::test_task_detail_and_pagination PASSED
```

Run: `pytest tests/test_api.py -v`
