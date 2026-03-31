# MemoryChain API (Chat-first V1 bootstrap)

## Run

```bash
cd apps/api
pip install -e .
uvicorn memorychain_api.main:app --reload
```

Default auth:

- Header: `X-API-Key`
- Value: `dev-key`

Env vars:

- `MEMORYCHAIN_API_KEY`
- `MEMORYCHAIN_DB_PATH` (default: `memorychain.db`)
- `MEMORYCHAIN_LLM_PROVIDER` (`local` or `openai`, default `local`)
- `MEMORYCHAIN_LLM_MODEL` (default `gpt-4o-mini`)
- `OPENAI_API_KEY` (required when provider is `openai`)

## Primary Endpoint

- `POST /api/v1/chat`

This endpoint:

- stores every user message as `SourceDocument`
- appends user/assistant messages to persistent conversation memory
- extracts structured objects from message text (`JournalEntry`, optional `DailyCheckin`, `Task`, `Goal`)
- generates assistant response with memory context

Example:

```json
{
  "user_id": "sam",
  "message": "Sleep 6.5h mood 4/10. todo: submit the draft. goal: run 4 training sessions this week"
}
```
