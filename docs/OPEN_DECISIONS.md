# MemoryChain — Design Decisions

> This document captures every major design decision — both resolved and open.
> Decisions locked during V0.2.0 implementation are marked with ✅ LOCKED.
> Open questions that still need resolution are marked with ❓ OPEN.
>
> **Last updated:** After Opus architectural review (post-V0.2.0).

---

## 1. Technology Stack

### 1.1 Database Engine ✅ LOCKED → SQLite

**Decision:** SQLite with file-based storage (`memorychain.db`).

**Rationale:** Single-user MVP, zero-config, no server dependency. FTS5 will
be added for full-text search (Phase 0). Migration to PostgreSQL deferred to
V1.1+ if multi-user is needed.

**Remaining concern:** Add FTS5 virtual tables before data volume grows. Current
`LIKE '%query%'` search won't scale past a few hundred entries.

---

### 1.2 Backend Language & Framework ✅ LOCKED → Python + FastAPI

**Decision:** Python 3.11+ with FastAPI, Pydantic for schemas, uvicorn for serving.

**Rationale:** Best LLM library ecosystem (OpenAI SDK), Pydantic models map
directly to the 12 V1 object types, fast prototyping with async support.

**Implementation status:** Fully operational with 16 passing tests.

---

### 1.3 LLM Provider & Model Strategy

The system needs LLM capabilities for:
1. **Extraction** — parsing raw text into structured objects (DailyCheckin, Activity, etc.)
2. **Summarization** — generating WeeklyReview summaries
3. **Pattern detection** — identifying candidate Insights
4. **Chat/retrieval** — conversational access to personal history

| Option | Strengths | Weaknesses |
|--------|-----------|------------|
| **OpenAI (GPT-4o / GPT-4o-mini)** | Best structured output support, function calling, widely documented | Cost per call, data leaves your machine, rate limits |
| **Anthropic (Claude)** | Strong reasoning, long context windows, good at nuanced text | Slightly less structured output tooling, cost |
| **Local models (Ollama + Llama/Mistral)** | Free, private, no data leaves machine | Weaker extraction accuracy, requires GPU, slower |
| **Hybrid (local for extraction, cloud for analysis)** | Privacy for routine ops, quality for complex tasks | Two integration paths to maintain |

**Suggested default:** Start with OpenAI GPT-4o-mini for extraction (cheap,
good at structured output) and GPT-4o for summarization/analysis. Add local
model support as a V2 privacy option.

**Questions to answer:**
- How important is data privacy? (This is personal health/emotion data.)
- Budget tolerance for API costs? (~$0.01-0.05 per daily log ingestion with GPT-4o-mini)
- Do you have a local GPU available for running models?
- Should the system work offline?

---

### 1.4 Frontend

| Option | Strengths | Weaknesses |
|--------|-----------|------------|
| **React (Next.js or Vite)** | Component model fits structured data UI, huge ecosystem | Heavy for simple use case |
| **CLI-first (no frontend)** | Fastest to build, focuses effort on core logic | Poor UX for daily journaling |
| **Mobile (React Native / Flutter)** | Best for daily check-ins on the go | Much more complex, slower dev cycle |
| **Simple web (HTMX + templates)** | Lightweight, server-rendered, fast to build | Less interactive, harder to build rich views |

**Suggested default:** Defer frontend. Build the backend + API first, use CLI
or a simple script for ingestion during V1. Add a web UI once the API is stable.

**Questions to answer:**
- Where do you actually want to enter daily logs? (Phone? Desktop? Terminal?)
- Is a web UI a V1 requirement or can it wait?
- Any frontend framework experience?

---

## 2. API Contract

No endpoints are currently defined. The following decisions shape the entire
integration surface.

### 2.1 API Style

| Option | When to use |
|--------|-------------|
| **REST** | Simple CRUD-heavy apps, easy to understand, broad tooling |
| **GraphQL** | Complex relational queries (e.g., "get journal entries with linked goals and evidence"), flexible frontends |
| **tRPC** | TypeScript full-stack, type-safe end-to-end |

**Suggested default:** REST for V1. The object model is CRUD-friendly. GraphQL
adds complexity that isn't needed until the frontend requires flexible queries.

### 2.2 Core Endpoint Map (Draft)

If REST, the V1 surface would look roughly like:

```
# Ingestion
POST   /api/v1/ingest                    → accepts raw text, returns SourceDocument + extracted objects

# Source Documents
GET    /api/v1/sources                   → list (paginated, filterable by date range)
GET    /api/v1/sources/{id}              → detail

# Authored Objects (one set per type)
GET    /api/v1/journal-entries            → list
POST   /api/v1/journal-entries            → create
GET    /api/v1/journal-entries/{id}       → detail

GET    /api/v1/checkins                   → list
POST   /api/v1/checkins                   → create
GET    /api/v1/checkins/{id}              → detail

GET    /api/v1/activities                 → list/filter
POST   /api/v1/activities                 → create
GET    /api/v1/activities/{id}            → detail

GET    /api/v1/metrics                    → list/filter
GET    /api/v1/metrics/{id}              → detail

GET    /api/v1/protocols                  → list
POST   /api/v1/protocols                  → create
PUT    /api/v1/protocols/{id}             → update
GET    /api/v1/protocols/{id}/executions  → list executions

GET    /api/v1/goals                      → list
POST   /api/v1/goals                      → create
PUT    /api/v1/goals/{id}                 → update
GET    /api/v1/goals/{id}/tasks           → list linked tasks

GET    /api/v1/tasks                      → list
POST   /api/v1/tasks                      → create
PUT    /api/v1/tasks/{id}                 → update

# Derived Objects
GET    /api/v1/weekly-reviews             → list
GET    /api/v1/weekly-reviews/{id}        → detail (with evidence links)
POST   /api/v1/weekly-reviews/generate    → trigger generation for a date range

GET    /api/v1/insights                   → list
GET    /api/v1/insights/{id}              → detail (with evidence)
PUT    /api/v1/insights/{id}/status       → accept / reject / archive

GET    /api/v1/heuristics                 → list
GET    /api/v1/heuristics/{id}            → detail (with evidence)
PUT    /api/v1/heuristics/{id}/active     → enable / disable

# Search & Retrieval
GET    /api/v1/search?q=...&type=...&from=...&to=...  → full-text search across objects
POST   /api/v1/chat                       → conversational retrieval over personal history
```

**Questions to answer:**
- Does this endpoint surface feel right, or is anything missing?
- Should ingestion be a single `POST /ingest` that does everything, or should
  extraction be a separate step the caller controls?
- Do you need batch ingestion (import multiple days at once)?

### 2.3 Authentication & Authorization

| Option | Complexity | When to use |
|--------|-----------|-------------|
| **None (single-user, local)** | Trivial | MVP, local deployment only |
| **API key (static token)** | Low | Single user, hosted deployment |
| **JWT + user accounts** | Medium | Multi-user, web-accessible |
| **OAuth (GitHub/Google)** | Higher | Public-facing app |

**Suggested default:** API key for V1. Single static token in an env var.
Upgrade to JWT if/when multi-user becomes real.

---

## 3. Promotion Algorithm (Insight & Heuristic Lifecycle)

This is the intellectual core of MemoryChain. The schema defines Insight and
Heuristic objects, but the rules for *creating and promoting them* are not
specified. Every choice here directly affects user trust.

### 3.1 Insight Generation

**When should the system create an Insight?**

| Approach | Description | Risk |
|----------|-------------|------|
| **Time-windowed pattern scan** | After each WeeklyReview, scan recent data for repeated patterns (e.g., "low sleep → low mood appeared 4 of 7 days") | May find spurious correlations |
| **Threshold-based** | Only create Insight when a metric correlation exceeds N occurrences in M days | Conservative but clear |
| **LLM-detected** | Ask the LLM to identify patterns in a batch of entries | Hard to validate, risk of hallucination |
| **Hybrid** | Deterministic correlation check first, then LLM to phrase the Insight naturally | Best of both; more complex |

**Questions to answer:**
- Minimum evidence count: How many observations before a pattern becomes an Insight?
  - Suggested: **≥ 3 occurrences within 14 days**
- Should Insights be auto-created, or should the system propose candidates for user review?
- Can an Insight be created from qualitative data (journal text), or only from structured metrics?

### 3.2 Heuristic Promotion

**When does an Insight become a Heuristic (operational rule)?**

The schema says Heuristics require "stronger evidence" and "user confirmation."
We need to define exactly what that means.

| Criterion | Proposed Threshold |
|-----------|-------------------|
| **Minimum evidence count** | ≥ 5 supporting observations |
| **Minimum time span** | Pattern observed across ≥ 3 weeks |
| **Counterevidence ratio** | Supporting evidence outnumbers counter by ≥ 3:1 |
| **User confirmation** | Explicit user approval required (never auto-promoted) |

**Questions to answer:**
- Should Heuristic promotion ever be automatic, or always require user confirmation?
- What happens to a Heuristic when new counterevidence appears? Auto-deactivate? Flag for review?
- Can users create Heuristics directly (bypassing the evidence chain)?
  - The schema allows `source_type: user_defined` — so yes, but should there be guardrails?

### 3.3 Confidence Scoring

Both Insight and Heuristic have a `confidence` field but no definition of what
the values mean.

**Proposed scale:**

| Value | Meaning |
|-------|---------|
| 0.0–0.3 | Weak — few observations, short time window |
| 0.3–0.6 | Moderate — repeated pattern, some variance |
| 0.6–0.8 | Strong — consistent pattern across weeks |
| 0.8–1.0 | Very strong — highly consistent, user-confirmed |

**Questions to answer:**
- Is 0.0–1.0 the right scale, or would categorical labels (low/medium/high) be simpler?
- Should confidence auto-adjust as new evidence arrives?
- Should low-confidence Insights be hidden from the user or shown with a warning?

---

## 4. Correction & Override Workflow

The schema rules mention correction records but don't define the flow. This is
critical for user trust — if the system says something wrong, how does the user
fix it?

### 4.1 What Can Be Corrected?

| Object Type | Correction Scenario |
|-------------|-------------------|
| **SourceDocument** | Typo in raw text; wrong date attributed | 
| **Extracted objects** (JournalEntry, DailyCheckin, etc.) | System extracted wrong values (e.g., parsed sleep as 8 when user meant 6) |
| **Insight** | User disagrees with the pattern ("that's not real") |
| **Heuristic** | User wants to deactivate or modify a rule |
| **WeeklyReview** | User disagrees with summary |

### 4.2 Correction Approaches

| Approach | How it works | Trade-off |
|----------|-------------|-----------|
| **Edit-in-place + audit log** | Update the object, store old value in a `corrections` table | Simple UX, but original state is hidden |
| **Immutable + supersede** | Mark old object as `corrected`, create new version with `supersedes_id` | Full history, but more complex data model |
| **Rejection record** | For derived objects: create an `InferenceRejection` record, mark original as `rejected` | Clean for Insights; doesn't work for field-level fixes |
| **Hybrid** | Edit-in-place for authored objects (with audit), rejection records for derived objects | Matches the authored/derived split naturally |

**Suggested default:** Hybrid approach. Authored objects get edit-in-place with
an audit trail. Derived objects (Insight, Heuristic, WeeklyReview) get explicit
rejection/archive status changes with an optional reason.

**Questions to answer:**
- If a user rejects an Insight, should the system avoid regenerating similar Insights?
  (This implies storing rejection patterns.)
- If a user corrects extracted data (e.g., sleep hours), should downstream
  derived objects (WeeklyReview mentioning sleep) be flagged as potentially stale?
- How much correction history should be visible to the user?

---

## 5. Evidence Citation Format

The schema requires `evidence_ids` on Insights, Heuristics, and WeeklyReviews.
But what exactly do these IDs point to, and how granular should they be?

### 5.1 Citation Granularity

| Level | Example | Pros | Cons |
|-------|---------|------|------|
| **Object-level** | `evidence_ids: ["journal-entry-abc", "checkin-def"]` | Simple, easy to implement | Can't point to specific sentences |
| **Object + excerpt** | `evidence: [{id: "journal-abc", excerpt: "I slept terribly"}]` | User sees exactly what was used | More storage, excerpts can be misleading out of context |
| **Object + offset** | `evidence: [{id: "source-abc", start: 142, end: 203}]` | Precise, can highlight in UI | Fragile if source text is corrected |

**Suggested default:** Object + type for V1. Store evidence as typed
references, e.g. `{type: "journal_entry", id: "abc"}`. This keeps citations
simple while avoiding extra lookups and ambiguity in mixed evidence lists. Add
excerpt support in V2 if needed.

**Questions to answer:**
- Is it enough to say "this Insight was derived from these 4 journal entries"?
- Or does the user need to see "specifically, this sentence from this entry"?
- Should evidence include the type of object (to avoid extra lookups)?
  e.g., `evidence: [{type: "journal_entry", id: "abc"}, {type: "checkin", id: "def"}]`

---

## 6. Search & Retrieval

V1 scope includes "simple chat/retrieval over personal history." This needs
a concrete design.

### 6.1 Search Capabilities

| Capability | Implementation | V1? |
|------------|---------------|-----|
| **Full-text search** | Postgres `tsvector` / SQLite FTS5 over raw_text + title fields | Yes |
| **Date range filter** | SQL `WHERE effective_at BETWEEN ? AND ?` | Yes |
| **Object type filter** | SQL `WHERE object_type IN (...)` | Yes |
| **Tag filter** | Array contains on `tags` field | Yes |
| **Semantic search** | Embeddings + vector similarity (pgvector / ChromaDB) | Defer to V2 |
| **Conversational retrieval** | RAG pipeline: search → context → LLM response | V1 stretch goal |

**Questions to answer:**
- Is keyword search sufficient for V1, or is semantic search ("entries where I felt anxious") a requirement?
- Should search return objects or a natural language summary?
- How should search results be ranked? (Recency? Relevance? Both?)

### 6.2 Chat Interface

The V1 scope mentions "simple chat/retrieval." What does that look like?

| Option | Description |
|--------|-------------|
| **Query-only** | User asks a question, system searches and returns matching objects |
| **RAG chat** | User asks a question, system retrieves relevant objects, passes to LLM, returns natural language answer |
| **Guided prompts** | Pre-built queries: "How did I sleep this week?", "What are my open tasks?" |

**Suggested default:** Start with guided prompts + query-only. Add RAG chat
as a stretch goal once the data layer is solid.

---

## 7. WeeklyReview Generation

The schema defines what a WeeklyReview contains but not how to generate one.

### 7.1 Generation Strategy

| Approach | Description | Quality | Cost |
|----------|-------------|---------|------|
| **Pure deterministic** | SQL aggregation: count activities, average metrics, list open tasks | Predictable, free | Reads like a database report |
| **Deterministic + LLM polish** | Aggregate data first, then ask LLM to write a human summary | Good balance | One LLM call per week |
| **Pure LLM** | Pass all week's entries to LLM, ask for structured review | Most natural | Expensive, risk of hallucination, hard to verify |

**Suggested default:** Deterministic + LLM polish. Compute the facts (metrics,
activity counts, goal progress) in code, then pass the structured facts to the
LLM with a prompt like: "Write a supportive weekly summary from these facts.
Only make claims supported by the data provided."

**Questions to answer:**
- Should WeeklyReviews be auto-generated every Monday, or on-demand?
- Can the user edit a generated review?
- Should the review include comparison to previous weeks?

---

## 8. Ingestion Edge Cases

The ingestion pipeline is the entry point for all data. These edge cases need
explicit decisions.

### 8.1 Partial Extraction

**What happens if the LLM can only extract some objects from a source?**

| Option | Behavior |
|--------|----------|
| **Store what you can** | Create SourceDocument + whatever objects extracted successfully; log warnings for failures |
| **All or nothing** | If extraction fails for any object, store only SourceDocument; flag for manual review |
| **Confidence-gated** | Only create extracted objects above a confidence threshold |

**Suggested default:** Store what you can. Always create the SourceDocument.
Create extracted objects that pass validation. Log extraction failures for
review.

### 8.2 Duplicate Detection

**What if the user submits the same log twice?**

| Option | Behavior |
|--------|----------|
| **Allow duplicates** | Every submission creates new objects; user cleans up manually |
| **Content hash dedup** | Hash raw_text + effective_at; reject exact duplicates |
| **Fuzzy dedup** | Detect near-duplicates and prompt user |

**Suggested default:** Content hash dedup. If `hash(raw_text + effective_at)`
matches an existing SourceDocument, reject with a clear message.

### 8.3 Legacy Import

The `users/Sam/logs` directory contains existing WHYNN-format daily logs.

**Questions to answer:**
- Should V1 include a bulk import tool for these legacy logs?
- What format are they in? (Need to inspect and build a parser.)
- Should imported data be treated as `provenance: import` or `provenance: user`?

---

## 9. Data Privacy & Security

MemoryChain stores deeply personal data: emotions, health metrics, behavioral
patterns, self-assessments. Even for a single-user MVP, basic decisions matter.

### 9.1 Data at Rest

| Option | Description |
|--------|-------------|
| **Unencrypted local DB** | Simplest; relies on OS-level file permissions |
| **Encrypted DB (SQLCipher / Postgres TDE)** | Data encrypted on disk |
| **Application-level encryption** | Encrypt sensitive fields before storage |

**Suggested default:** Unencrypted for local/dev. If deploying to a server,
use Postgres TDE or volume-level encryption.

### 9.2 Data in Transit to LLM

| Option | Description |
|--------|-------------|
| **Send raw text to cloud LLM** | Simplest; relies on provider's privacy policy |
| **Anonymize before sending** | Strip names, dates, locations before LLM calls |
| **Local models only** | No data leaves the machine |

**Questions to answer:**
- Are you comfortable sending personal journal entries to OpenAI/Anthropic?
- Is anonymization worth the complexity?
- Is offline/local-only a hard requirement?

---

## 10. Memory Layer Implementation

The architecture describes three memory layers (working, episodic, semantic self).
How should these be implemented in V1?

### 10.1 Implementation Strategy

| Approach | Description | Complexity |
|----------|-------------|-----------|
| **Database views** | SQL views that filter core tables (e.g., working_memory = active tasks + recent checkins) | Low |
| **Materialized cache** | Periodically compute and cache each memory layer | Medium |
| **Separate tables** | Dedicated storage for each memory type | High, likely premature |

**Suggested default:** Database views for V1. Define each memory layer as a
SQL query over existing tables:

```sql
-- Working memory: recent + active items
CREATE VIEW working_memory AS
  SELECT * FROM tasks WHERE status IN ('todo', 'in_progress')
  UNION ALL
  SELECT * FROM goals WHERE status = 'active'
  UNION ALL
  SELECT * FROM checkins WHERE date >= CURRENT_DATE - INTERVAL '3 days';

-- Episodic memory: all timestamped entries
CREATE VIEW episodic_memory AS
  SELECT * FROM journal_entries ORDER BY effective_at DESC;

-- Semantic self-memory: validated patterns and rules
CREATE VIEW semantic_self_memory AS
  SELECT * FROM heuristics WHERE active = true
  UNION ALL
  SELECT * FROM insights WHERE status = 'active';
```

---

## Decision Summary Checklist

Locked V1 baseline on 2026-03-30:

| # | Decision | Your Pick |
|---|----------|-----------|
| 1.1 | Database engine | PostgreSQL |
| 1.2 | Backend language/framework | Python + FastAPI |
| 1.3 | LLM provider/model | OpenAI cloud-first; GPT-4o-mini for extraction, GPT-4o for summarization/analysis |
| 1.4 | Frontend approach | Backend/API first; CLI or simple script ingestion for V1 |
| 2.1 | API style (REST/GraphQL/tRPC) | REST |
| 2.3 | Auth approach | Static API key |
| 3.1 | Insight generation trigger | Hybrid: deterministic pattern check plus LLM phrasing |
| 3.1 | Minimum evidence for Insight | >= 3 observations within 14 days |
| 3.2 | Heuristic requires user confirmation? | Yes, always |
| 3.3 | Confidence scale | Both numeric 0.0-1.0 and user-facing labels |
| 4.2 | Correction approach | Hybrid: edit authored objects with audit; reject/archive derived objects |
| 5.1 | Evidence citation granularity | Object + type |
| 6.1 | Semantic search in V1? | No; keyword/date/type/tag search only |
| 6.2 | Chat interface approach | Guided prompts + query-only retrieval |
| 7.1 | WeeklyReview generation strategy | Deterministic facts + LLM polish |
| 8.1 | Partial extraction handling | Store what validates; log failures |
| 8.2 | Duplicate detection | Exact content hash dedup |
| 8.3 | Legacy import in V1? | Defer until core ingestion is stable |
| 9.1 | Data at rest encryption | Unencrypted local/dev |
| 9.2 | LLM data privacy approach | Send raw text to cloud LLM |
| 10.1 | Memory layer implementation | Database views |
