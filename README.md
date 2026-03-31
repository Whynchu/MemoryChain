# MemoryChain

MemoryChain is a personal memory and execution backend that turns daily logs and interactions into structured, queryable behavioral data.

Current state: V1 backend is active and tested.

## What It Can Do Right Now

- Capture chat and persist conversation memory.
- Extract structured objects from chat text:
  - `JournalEntry`
  - optional `DailyCheckin` (sleep/mood/energy)
  - `Task` from `todo:`
  - `Goal` from `goal:`
- Create, list, fetch, and update core objects:
  - goals (`limit`/`offset` pagination on list)
  - tasks (`limit`/`offset` pagination on list)
  - journal entries (list)
  - check-ins (list)
- Generate weekly reviews with continuity-aware metrics.
  - includes `engagement_notes` (adherence, missed cycles, streak gaps)
- Search memory with filters:
  - keyword (`q`)
  - type (`source_document`, `journal_entry`, `daily_checkin`, `task`, `goal`)
  - date range (`from`, `to`)
  - journal tag (`tag`)
- Return guided prompt bundles:
  - open tasks
  - recent check-ins
  - recent journal
  - active goals
  - attendance this week (engagement metadata)
- Track continuity events (presence + non-response):
  - prompt cycle lifecycle (`scheduled`, `sent`, `viewed_no_response`, `responded`, `missed`)
  - engagement summary metrics (`7d` / `30d` windows)
- Track correction history and rollback changes for authored objects:
  - append-only audit log entries for goal/task updates
  - rollback endpoint that restores the selected audit entry's prior state

## What It Is Not Yet

- No frontend app yet (backend-first phase).
- No semantic/vector search (keyword search only).
- No full insight/heuristic lifecycle engine yet.
- No multi-user auth system (static API key only).

## Repo Layout

- `apps/api` - FastAPI backend (main build target)
- `docs/` - architecture notes, schemas, decisions
  - continuity plan: `docs/architecture/CONTINUITY_SIGNALS_PLAN.md`
- `users/` and `core/` - source material / legacy references

## Quick Start (API)

1. Install Python 3.11+.
2. From repo root:

```bash
cd apps/api
python -m pip install -e .
python -m pip install pytest
```

3. Run API:

```bash
python -m uvicorn memorychain_api.main:app --reload
```

4. Default auth header:

- Header: `X-API-Key`
- Value: `dev-key`

## Environment Variables

- `MEMORYCHAIN_API_KEY` (default `dev-key`)
- `MEMORYCHAIN_DB_PATH` (default `memorychain.db`)
- `MEMORYCHAIN_LLM_PROVIDER` (`local` or `openai`, default `local`)
- `MEMORYCHAIN_LLM_MODEL` (default `gpt-4o-mini`)
- `OPENAI_API_KEY` (required if provider is `openai`)

## Current API Surface

Health:
- `GET /health`

Chat:
- `POST /api/v1/chat`
- `GET /api/v1/conversations/{conversation_id}/messages`

Ingestion:
- `POST /api/v1/ingest`

Goals:
- `POST /api/v1/goals`
- `GET /api/v1/goals?user_id=...&limit=...&offset=...`
- `GET /api/v1/goals/{goal_id}?user_id=...`
- `PUT /api/v1/goals/{goal_id}`

Tasks:
- `POST /api/v1/tasks`
- `GET /api/v1/tasks?user_id=...&limit=...&offset=...`
- `GET /api/v1/tasks/{task_id}?user_id=...`
- `PUT /api/v1/tasks/{task_id}`

Journal / Check-ins:
- `GET /api/v1/journal-entries`
- `GET /api/v1/checkins`

Weekly Reviews:
- `POST /api/v1/weekly-reviews/generate`
- `GET /api/v1/weekly-reviews`

Search & Prompts:
- `GET /api/v1/search`
- `GET /api/v1/prompts`

Continuity / Engagement:
- `POST /api/v1/prompt-cycles/schedule`
- `POST /api/v1/prompt-cycles/{id}/send`
- `POST /api/v1/prompt-cycles/{id}/viewed`
- `POST /api/v1/prompt-cycles/{id}/responded`
- `POST /api/v1/prompt-cycles/{id}/missed`
- `GET /api/v1/prompt-cycles`
- `GET /api/v1/engagement/summary`

Audit / Rollback:
- `GET /api/v1/audit-log?user_id=...&limit=...&offset=...`
- `POST /api/v1/audit-log/{audit_log_id}/rollback?user_id=...`

## Example Calls

Chat capture:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{
    "user_id": "sam",
    "message": "Sleep 6.5h mood 4/10. todo: send the outline. goal: finish v1 spec"
  }'
```

Search tasks:

```bash
curl "http://127.0.0.1:8000/api/v1/search?user_id=sam&type=task&q=outline" \
  -H "X-API-Key: dev-key"
```

Engagement summary:

```bash
curl "http://127.0.0.1:8000/api/v1/engagement/summary?user_id=sam&window=7d" \
  -H "X-API-Key: dev-key"
```

## Testing

From repo root:

```bash
python -m pytest apps/api/tests/test_api.py -q
```

Current baseline in this workspace: `16 passed, 1 warning`.

## Near-Term Backend Plan

- Expand engagement summaries (time-window quality + trend deltas).
- Continue hardening weekly review evidence/citation structure.
- Add rollback guardrails (policy checks + dry-run preview mode).
