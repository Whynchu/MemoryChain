# Continuity Signals Plan (Prompted Response + Non-Response)

## Why This Matters

MemoryChain currently captures what the user writes. This plan adds explicit modeling for what the user does not write after a system prompt.

Core principle:

- presence is data
- absence is also data
- absence should be treated as continuity/habit signal first, not emotional diagnosis

## Objective

Add backend-native continuity tracking so daily attendance behavior is queryable and analyzable alongside journal/task/check-in data.

## Event Model (Source of Truth)

The backend owns this state. LLMs interpret it; they do not define it.

Suggested event states per check-in cycle:

1. `prompt_scheduled`
2. `prompt_sent`
3. `prompt_viewed_no_response`
4. `prompt_responded`
5. `missed_checkin`
6. `streak_resumed`

Optional additional events:

- `app_open_no_entry`
- `partial_entry`

## Proposed Data Objects

### `PromptCycle`

One row per user/day prompt attempt.

Fields:

- `id`
- `user_id`
- `cycle_date`
- `scheduled_for`
- `sent_at`
- `expires_at`
- `status` (`pending`, `responded`, `viewed_no_response`, `missed`)
- `response_source_document_id` (nullable)
- `response_at` (nullable)
- `created_at`
- `updated_at`

### `EngagementEvent`

Append-only event log for continuity analytics.

Fields:

- `id`
- `user_id`
- `prompt_cycle_id` (nullable for generic app-open events)
- `event_type`
- `event_at`
- `metadata_json`

## Minimal API Surface (Backend First)

- `POST /api/v1/prompt-cycles/schedule` (internal/system use)
- `POST /api/v1/prompt-cycles/{id}/send` (internal/system use)
- `POST /api/v1/prompt-cycles/{id}/viewed`
- `POST /api/v1/prompt-cycles/{id}/responded` (links source document/message)
- `POST /api/v1/prompt-cycles/{id}/missed`
- `GET /api/v1/prompt-cycles?user_id=...&from=...&to=...`
- `GET /api/v1/engagement/summary?user_id=...&window=7d|30d`

## Derived Metrics (Phase 1)

- adherence rate (7d, 30d)
- response delay median
- longest silence gap
- open-without-entry frequency
- streak length and streak-resume count

## Interpretation Guardrails

Interpretation layer must remain probabilistic and non-diagnostic.

Recommended language:

- "No entry recorded after scheduled check-in"
- "2-day continuity gap detected"
- "Responses are less frequent after late prompts"

Avoid deterministic emotional conclusions by default.

## Implementation Phases

### Phase A: Event Capture

- add DB tables (`prompt_cycles`, `engagement_events`)
- add repository CRUD and transition methods
- add status transition validation (`pending -> responded|viewed_no_response|missed`)
- add API endpoints and tests

### Phase B: Metrics and Retrieval

- add engagement summary query methods
- expose `GET /engagement/summary`
- include continuity metrics in guided prompts context

### Phase C: Weekly Review Integration

- include adherence + gap metrics in deterministic weekly facts
- include continuity notes in weekly summary output

### Phase D: Prompt Timing Optimization (Later)

- evaluate response rate by time window
- store preferred check-in windows per user
- suggest schedule shifts based on measured response patterns

## Risks and Controls

Risks:

- overinterpreting non-response
- noisy events from client instrumentation gaps
- conflating "app open" with intentional journaling behavior

Controls:

- keep event layer factual and append-only
- store explicit transition reasons in metadata
- separate facts from interpretations in APIs/services

## Immediate Backend Tasks

1. Define schemas for `PromptCycle` and `EngagementEvent` in `schemas.py`.
2. Add DB table initialization in `storage/db.py`.
3. Add repository methods for transitions and list/summary queries.
4. Add routers and endpoint tests for cycle lifecycle.
5. Add one guided prompt bundle for continuity (e.g., "attendance this week").
