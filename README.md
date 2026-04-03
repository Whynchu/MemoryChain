# MemoryChain

**A memory and execution backend that learns your patterns, runs your protocols, and keeps you honest.**

A digital partner that lives alongside you, knows your habits, tracks your metrics, and runs your daily briefings. Not a chatbot. Not a dashboard. A personal system that understands *you* through conversation and structured check-ins, and turns that understanding into queryable behavioral data.

MemoryChain separates *observations* (what happened) from *interpretations* (patterns) from *operational rules* (what to do about it). Casual conversation never accidentally becomes an execution constraint — but real patterns get surfaced and tracked.

**Current state:** v0.7.0-dev — 82 passing tests, 58 daily checkins. Phases 0–3 complete (foundation, questionnaires, hybrid extraction, WHYNN import, insight detection, enriched reviews, audit expansion). Building Phase 4: CLI tool and daily workflow.

---

## The Vision

You talk to MemoryChain like you'd talk to a training partner who remembers everything:

> **You:** "Morning check-in"
> **MC:** "How'd you sleep?"
> **You:** "About 7 hours, woke up once"
> **MC:** "Mood 1-10?"
> **You:** "Solid 7, feeling good"
> **MC:** "Body weight?"
> **You:** "183.5"
> **MC:** ✅ *Morning check-in complete. Sleep 7h, mood 7/10, weight 183.5 lbs. You've logged 5 days straight.*

Or just talk naturally:

> **You:** "Did 30 minutes of mobility work, then 3 rounds of sparring. Felt sharp but my left shoulder is tight."
> **MC:** *Logged: mobility session (30 min), sparring (3 rounds). Noted shoulder tightness. That's the third time this week — want me to flag it?*

Two input modes, one consistent memory layer:
- **Questionnaire mode** — structured Q&A for routine data (morning log, post-training debrief)
- **Freeform mode** — natural conversation with automatic extraction

The system doesn't just store — it *notices*. As data accumulates, patterns emerge: sleep quality drops when you train past 8pm. Recovery scores improve on weeks with 3+ mobility sessions. These become insights, and eventually operational heuristics.

---

## What It Can Do Right Now ✅

**Core Ingestion:**
- Chat-based conversation with persistent memory
- Automatic extraction from natural language:
  - `Activity` — workouts, mobility, breathwork, recovery
  - `MetricObservation` — body weight, heart rate, hydration, CO2 hold
  - `DailyCheckin` — sleep, mood, energy
  - `JournalEntry` — reflective content (noise-filtered)
  - `Task` / `Goal` — from explicit markers or context
- Immutable `SourceDocument` with content hash dedup
- FTS5 full-text search across all object types
- **Questionnaire mode** — structured Q&A via `/morning`, `/checkin`, `/training` commands
- **Hybrid extraction** — LLM (GPT-4o-mini) with regex fallback; works offline
- **Bulk historical import** — deterministic parser for WHYNN log format (`scripts/import_whynn_logs.py`)

**Data Management:**
- Full CRUD for 11 object types: goals, tasks, journal entries, check-ins, activities, metrics, protocols, protocol executions, insights, heuristics
- Provenance tracking on all objects (`user`, `import`, `system_extracted`, `system_inferred`)
- Pagination, audit logging, rollback capability

**Analysis & Continuity:**
- Weekly reviews with engagement metrics (adherence rates, streak gaps)
- Guided prompt bundles (what to review, what's open, what's recent)
- Prompt cycle lifecycle with engagement event tracking
- Search across all objects by keyword, type, date range, tags

---

## What's Next 🚀

**See [NEXT_STEPS.md](./NEXT_STEPS.md) for the full roadmap.**

**Building now — Phase 2: Insight Detection Engine**
1. Schema evolution — `detector_key` on insights (fingerprinting), `promotion_snapshot` on heuristics (audit)
2. Sleep-mood correlation detector — Pearson correlation, data-driven thresholds, not bucket hacking
3. Detection lifecycle — idempotent re-runs, rejected patterns never re-generated
4. Heuristic promotion — threshold validation with stored evidence snapshots
5. Insight state machine — candidate → active → promoted/rejected/archived

**Then:**
- Phase 3: Weekly review upgrades (insight mentions, LLM narrative, full audit trail)
- Phase 4: CLI daily workflow + extraction confirmation flow

---

## Repo Layout

- `apps/api` — FastAPI backend (Python 3.11+)
  - `routers/` — API endpoints (chat, ingest, goals, tasks, activities, metrics, protocols, insights, heuristics, etc.)
  - `services/` — Business logic (extraction, chat, ingestion, LLM, reviews, questionnaire, whynn_parser, whynn_extractor)
  - `storage/` — Database layer (SQLite, repository pattern)
  - `schemas.py` — Pydantic models for all objects
- `scripts/` — Utility scripts (`import_whynn_logs.py` — bulk historical log import)
- `docs/` — Architecture, schemas, design decisions
- `users/` — User data and historical logs
- `core/` — Legacy reference materials

## Quick Start

```bash
cd apps/api
python -m pip install -e .
python -m pip install pytest

# Optional: configure LLM (works without it via regex extraction)
export MEMORYCHAIN_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Run
python -m uvicorn memorychain_api.main:app --reload

# Test
pytest tests/ -v  # 82 tests
```

**API at** `http://localhost:8000` — Docs at `http://localhost:8000/docs` — Auth: `X-API-Key: dev-key`

---

## Usage

**Talk to it:**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-1",
    "message": "Slept 8 hours, mood 8/10. Did 30 minutes of mobility. Body weight 183 lbs.",
    "conversation_id": "conv-123"
  }'
```

This extracts and stores: `DailyCheckin` (sleep 8h, mood 8), `Activity` (mobility 30min), `MetricObservation` (weight 183 lbs), `JournalEntry`, `SourceDocument`.

**Search your memory:**

```bash
curl "http://localhost:8000/api/v1/search?user_id=user-1&query=mobility&type=activity" \
  -H "X-API-Key: dev-key"
```

**Weekly review:**

```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "X-API-Key: dev-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-1", "from": "2026-03-24", "to": "2026-03-31"}'
```

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `MEMORYCHAIN_API_KEY` | `dev-key` | Auth key |
| `MEMORYCHAIN_DB_PATH` | `memorychain.db` | SQLite database |
| `MEMORYCHAIN_LLM_PROVIDER` | `local` | `local` or `openai` |
| `MEMORYCHAIN_LLM_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_API_KEY` | — | Required if using OpenAI |

---

## Testing

47 tests across 2 test files:

```bash
pytest tests/ -v
# tests/test_api.py       — 27 tests (core API, chat, search, prompts, audit, WHYNN parser/extractor)
# tests/test_phase0.py    — 20 tests (activities, metrics, protocols, insights, heuristics, FTS5, extraction)
```
