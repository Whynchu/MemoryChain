# MemoryChain

MemoryChain is a personal memory and execution system focused on turning daily logs into structured, queryable objects.

Current state: early V1 backend. The API is usable and tested, but still intentionally lightweight.

## What It Can Do Right Now

- Capture chat messages and persist conversation history.
- Extract structured memory objects from chat text:
  - `JournalEntry`
  - optional `DailyCheckin` (sleep/mood/energy)
  - `Task` from `todo:`
  - `Goal` from `goal:`
- Store and list core authored objects:
  - goals
  - tasks
  - journal entries
  - check-ins
- Generate deterministic weekly reviews.
- Search across memory objects with filters:
  - keyword (`q`)
  - type (`source_document`, `journal_entry`, `daily_checkin`, `task`, `goal`)
  - date range (`from`, `to`)
  - journal tag (`tag`)
- Return guided prompt bundles for UI consumption:
  - open tasks
  - recent check-ins
  - recent journal
  - active goals

## What It Is Not Yet

- No frontend app yet (backend-first phase).
- No semantic/vector search yet (keyword search only).
- No advanced insight/heuristic lifecycle implementation yet.
- No multi-user auth system (static API key only).

## Repo Layout

- `apps/api` - FastAPI backend (current build focus)
- `docs/` - architecture notes, schema docs, open decisions
- `users/` and `core/` - source material and legacy references

## Quick Start (API)

1. Install Python 3.11+.
2. From repo root:

```bash
cd apps/api
python -m pip install -e .
python -m pip install pytest
```

3. Run the API:

```bash
python -m uvicorn memorychain_api.main:app --reload
```

4. API auth header (default):

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

Chat & memory capture:
- `POST /api/v1/chat`
- `GET /api/v1/conversations/{conversation_id}/messages`

Ingestion:
- `POST /api/v1/ingest`

Core objects:
- `GET /api/v1/goals`
- `POST /api/v1/goals`
- `GET /api/v1/tasks`
- `POST /api/v1/tasks`
- `GET /api/v1/journal-entries`
- `GET /api/v1/checkins`

Weekly review:
- `POST /api/v1/weekly-reviews/generate`
- `GET /api/v1/weekly-reviews`

Search & retrieval:
- `GET /api/v1/search`
- `GET /api/v1/prompts`

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

Search tasks by keyword:

```bash
curl "http://127.0.0.1:8000/api/v1/search?user_id=sam&type=task&q=outline" \
  -H "X-API-Key: dev-key"
```

Guided prompt bundles:

```bash
curl "http://127.0.0.1:8000/api/v1/prompts?user_id=sam" \
  -H "X-API-Key: dev-key"
```

## Testing

From repo root:

```bash
python -m pytest apps/api/tests/test_api.py -q
```

Current baseline in this workspace: all tests pass.

## Near-Term Build Plan

- Expand guided prompts into richer retrieval workflows.
- Add stronger filtering/sorting and pagination in search.
- Improve weekly review quality and evidence traceability.
- Start minimal web UI once API contracts stabilize.
