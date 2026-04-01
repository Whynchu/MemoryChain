# MemoryChain — Roadmap to MVP

Current state: **V0.2.0 — working FastAPI backend with basic chat extraction,
continuity tracking, audit/rollback, and 16 passing tests.**

This document defines the work remaining to reach a usable MVP. Phases are
ordered by dependency — each unlocks the next. The ordering is informed by
hands-on analysis of the real WHYNN daily logs in `users/Sam/logs/`.

---

## Phase 0: Foundation Fixes (This Week)

**Why first?** The existing code has structural gaps that will compound if
carried forward. Fix them while the codebase is small.

### 0.1 Add Missing V1 Object Tables

The design docs define 12 canonical V1 objects. The database only has 7.
These four are missing and are required before extraction can target them:

| Object | Table | Why It's Needed |
|--------|-------|-----------------|
| `Activity` | `activities` | Training sessions, meals, breathwork — the most common content in WHYNN logs |
| `MetricObservation` | `metric_observations` | Strike counts, CO₂ holds, heart rate, body weight — the data the insight engine needs |
| `Protocol` | `protocols` | Repeatable routines (AM stack, breathwork protocol, fight study) |
| `ProtocolExecution` | `protocol_executions` | Evidence a protocol was followed — ties to adherence tracking |

Also add empty tables for `insights` and `heuristics` — they already have
Pydantic Literal types defined but no storage.

**What to build:**
- Add 6 new tables to `storage/db.py` (matching the schema docs field specs)
- Add Pydantic models for Activity, MetricObservation, Protocol, ProtocolExecution, Insight, Heuristic
- Add basic CRUD in repository + simple list/create endpoints
- Add foreign keys: activity → source_document, metric → source_document, etc.

### 0.2 Add `provenance` Column to All Tables

The schema rules require every object to answer "who created this?"

```
provenance TEXT NOT NULL DEFAULT 'user'
-- values: 'user', 'import', 'system_extracted', 'system_inferred', 'system_aggregated'
```

Add this column to: source_documents, journal_entries, daily_checkins,
activities, metric_observations, goals, tasks, protocol_executions,
weekly_reviews, insights, heuristics.

**Why now:** The insight engine needs to distinguish "user said mood was 4"
from "system guessed mood was 4." Without provenance, you can't build
trustworthy derived objects.

### 0.3 Fix Transaction Safety

Currently `update_goal` and `update_task` do two separate commits — one for
the update, one for the audit log. If the process crashes between them, you
get an unaudited change.

**Fix:** Remove per-statement `conn.commit()` calls in multi-step operations.
Wrap related writes in a single transaction. Commit once at the end.

Pattern:
```python
def update_goal(self, ...):
    # ... do UPDATE ...
    # ... do INSERT audit_log ...
    self.conn.commit()  # single commit at the end
```

Apply to: `update_goal`, `update_task`, `create_prompt_cycle`,
`_transition_prompt_cycle`, and the ingestion service.

### 0.4 Stop Creating Journal Entries for Every Chat Message

`handle_chat` currently creates a `JournalEntry` for every message, including
"ok", "thanks", and one-word replies. This pollutes the journal and will
poison the insight engine with noise.

**Fix:** Only create a JournalEntry when the message has substantive content.
Simple heuristic for now: length > 40 characters, or contains a recognized
extraction pattern (sleep, mood, todo:, goal:). Chat messages still get stored
as `conversation_messages` — that table already exists.

### 0.5 Add FTS5 for Search

Current search does `LIKE '%query%'` full table scans. This won't scale past
a few hundred entries.

**Fix:** Add FTS5 virtual tables for searchable text:
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    object_type, object_id, user_id, content, effective_at,
    content='', contentless_delete=1
);
```

Populate on insert. Query with `MATCH` instead of `LIKE`.

### 0.6 Unify Extraction Into a Shared Service

Currently chat and ingest have divergent extraction logic. Chat does inline
regex. Ingest does passthrough. When LLM extraction arrives, both need it.

**Fix:** Create `services/extraction.py` with a single `extract_objects()`
function. Both the chat handler and the ingest handler call it. This is the
function that will later gain LLM capabilities.

```python
def extract_objects(
    raw_text: str,
    source_document_id: str,
    user_id: str,
    effective_at: datetime,
    provider: str = "regex",  # later: "llm"
) -> ExtractionResult:
    ...
```

**Definition of done for Phase 0:**
- [ ] 6 new tables exist, with Pydantic models and basic CRUD
- [ ] All tables have `provenance` column
- [ ] Multi-step writes use single-commit transactions
- [ ] Chat only creates JournalEntry for substantive messages
- [ ] FTS5 search index exists and is used by the search endpoint
- [ ] Shared `extraction.py` service exists, used by both chat and ingest
- [ ] All existing tests still pass + new tests for the additions

---

## Phase 1: Real Data First, Then Extraction (Weeks 1–3)

**Why this order?** The previous plan designed extraction in the abstract, then
tested on real data later. That's backwards. The WHYNN logs are the ground
truth. Understand them first, then build extraction that actually works.

### 1.1 Characterize the WHYNN Logs (Already Done)

Analysis of `III_DAILY_LOGS.txt` (2,468 lines, ~26 entries, Apr 7 – May 2, 2025):

**Structure:** Section-based with clear headers:
- `SYSTEM METRICS:` → sleep, weight, mood, energy, emotional state
- `BREATHWORK & PHYSICAL METRICS:` → CO₂ holds, lung capacity, breath cadence
- `TRAINING EXECUTION:` → session type, duration, rounds, strike counts, heart rate
- `NUTRITION & HYDRATION:` → hydration oz, meals, macros, supplement stacks
- `BUFFS TRIGGERED:` → domain-specific achievement markers (RPG framing)
- `XP AWARDS:` → gamified progress tracking
- `SYSTEM NOTES:` → freeform reflections, emotional processing, dream logs

**Key challenges:**
- Fields often `[Not recorded]` — must handle gracefully
- Inconsistent field names (`CO₂ Hold` vs `Max CO₂ Hold`, `Total Hydration` vs `Hydration Total`)
- Freeform emotional/dream content resists schema mapping
- RPG framing (buffs, XP, levels) is domain-specific vocabulary
- Some entries are combat-focused, others emotional-recovery, others ritual-only
- No canonical intra-day timestamps; approximate times only
- Unit variance (km/miles, oz/L, bpm/beats per minute)

### 1.2 Build Section-Based Log Parser

The WHYNN logs are not freeform prose — they're sectioned documents. Build a
deterministic parser that splits entries by date header, then splits sections
by header keyword.

```python
def parse_whynn_entry(raw_text: str) -> dict:
    """Split a single day's log into named sections."""
    # Returns: {"system_metrics": "...", "training": "...", "nutrition": "...", ...}
```

This is deterministic, testable, and doesn't need an LLM.

**Testing:** Write 5+ test cases from real entries (comprehensive entry, sparse
entry, emotional-only entry, combat-heavy entry, missing-fields entry).

### 1.3 Build Deterministic Field Extractors Per Section

For each section type, write regex/pattern extractors for structured fields:

```python
# From SYSTEM METRICS section:
extract_sleep_hours("Total Sleep: ~7 hours") → 7.0
extract_mood("Mood: 8/10") → 8
extract_body_weight("Morning Body Weight: 138.1 lbs") → (138.1, "lbs")

# From TRAINING section:
extract_strikes("Total Strikes: 488") → 488
extract_rounds("Rounds: 6") → 6
extract_duration("57 min total") → 57

# From NUTRITION section:
extract_hydration("Total Hydration: ~140 oz") → (140.0, "oz")
```

Handle `[Not recorded]` → `None`. Handle unit variance. Handle approximate
values (`~140` → `140.0`).

### 1.4 Wire Up LLM Extraction for Freeform Content

The structured fields (sleep, weight, strikes) can be extracted deterministically.
The freeform content (emotional notes, dream logs, system reflections) needs LLM.

Use OpenAI structured outputs to extract:
- Tags/themes from freeform text
- Emotional state classification (not diagnosis — classification)
- Task/commitment mentions buried in narrative
- Activity descriptions from ambiguous text

**Implementation:**
- Use `response_format` with a Pydantic model for structured output
- GPT-4o-mini for extraction (cheap, fast, good at structured output)
- Fallback to regex-only if no API key is set
- Log extraction confidence per field

**Key principle:** Deterministic extraction for structured fields. LLM only
for freeform content that resists regex. This keeps costs low and results
predictable.

### 1.5 Build Bulk Import Tool

```python
# scripts/import_whynn_logs.py
# 1. Read III_DAILY_LOGS.txt
# 2. Split into individual day entries by date header
# 3. For each entry:
#    a. Create SourceDocument (provenance='import')
#    b. Run extraction pipeline
#    c. Create DailyCheckin, Activities, MetricObservations, JournalEntry
#    d. Report: what was extracted, what was skipped, what failed
```

Run against the full WHYNN dataset. Manually review 10+ entries for accuracy.
Fix extraction bugs as they surface.

### 1.6 Iterate Extraction on Real Failures

This is the critical step. After bulk import:
- Spot-check 20 random entries. Score extraction accuracy per field.
- Identify the top 5 failure modes (what does the extractor get wrong?)
- Fix them. Re-import. Re-check. Repeat until accuracy ≥ 80%.

This loop will take longer than you expect. Budget 1+ weeks for it.

**Definition of done for Phase 1:**
- [ ] Bulk import successfully processes all WHYNN log entries
- [ ] Each entry produces: SourceDocument + DailyCheckin + 0-N Activities + 0-N MetricObservations + 0-1 JournalEntry
- [ ] Spot-check accuracy ≥ 80% on structured fields (sleep, weight, mood, strikes, hydration)
- [ ] Freeform content captured as JournalEntry with LLM-extracted tags
- [ ] Import tool reports extraction stats (fields found, fields missing, confidence)

---

## Phase 2: One Insight Detector, Done Right (Weeks 4–5)

**Why one, not many?** The previous plan called for a general-purpose insight
engine. That's a research project disguised as an engineering task. Start with
one concrete detector that proves the architecture, then generalize.

### 2.1 Sleep-Mood Correlation Detector

**The simplest meaningful insight:** "When you sleep less than X hours, your
mood averages Y points lower."

This only needs two fields from DailyCheckin: `sleep_hours` and `mood`. Both
are numeric. The correlation is straightforward to compute.

**Algorithm:**
1. Query DailyCheckins for the past 60 days where both `sleep_hours` and `mood` are non-null
2. If fewer than 5 data points, skip (insufficient evidence)
3. Split into two groups: sleep < 6h and sleep ≥ 6h
4. Compare average mood between groups
5. If difference ≥ 1.5 points and each group has ≥ 2 entries → create candidate Insight

**Output:**
```json
{
  "title": "Low sleep correlates with lower mood",
  "summary": "On days with <6h sleep, your mood averaged 4.2/10 vs 7.1/10 on days with ≥6h sleep (based on 12 entries over 30 days).",
  "confidence": 0.72,
  "status": "candidate",
  "evidence_ids": ["dc_abc123", "dc_def456", ...],
  "time_window_start": "2025-04-07",
  "time_window_end": "2025-05-02"
}
```

### 2.2 Build the Insight Creation Flow

- New service: `services/insights.py` with `detect_sleep_mood_insight()`
- Stores result in the `insights` table
- Endpoint: `POST /api/v1/insights/detect` (triggers detection manually)
- Also triggered by weekly review generation
- Returns created insights with evidence links

### 2.3 Build Heuristic Promotion

Once an Insight exists and has been reviewed:
- Endpoint: `POST /api/v1/insights/{id}/promote`
- Validates promotion thresholds:
  - ≥ 5 supporting observations
  - Pattern spans ≥ 3 weeks
  - Counter-evidence ratio ≤ 1:3
  - **Requires explicit user confirmation** (never auto-promoted)
- If valid → creates Heuristic, links back to Insight
- If invalid → returns 409 with explanation of what's missing

### 2.4 Build Insight Rejection

- Endpoint: `PUT /api/v1/insights/{id}/status` (accept, reject, archive)
- When rejected, store rejection reason
- Track rejected patterns to avoid re-generating similar insights
- Audit log records the rejection

### 2.5 Add a Second Detector (If Time Permits)

Only after sleep-mood works end-to-end, consider adding:
- **Training volume vs. energy** (high strike count days → next day energy)
- **Adherence decay** (missed prompt cycles correlate with fewer journal entries)

Each detector is a separate function, not a generalized engine. Generalize
only after you have 3+ working detectors and see the common patterns.

**Definition of done for Phase 2:**
- [ ] Sleep-mood insight detector runs against imported WHYNN data
- [ ] Produces at least 1 meaningful insight from the real dataset
- [ ] User can promote Insight → Heuristic (with threshold validation)
- [ ] User can reject an Insight (with reason, audit trail)
- [ ] Rejected patterns are not re-generated
- [ ] Tests cover: detection, promotion (success + failure), rejection

---

## Phase 3: Weekly Review + LLM Polish (Week 6)

### 3.1 Improve Weekly Review Generation

Current state: deterministic aggregation that reads like a database report.

**Improvements:**
- Include top insights (if any) in the review
- Include Activity summaries (total training sessions, strike counts, etc.)
- Reference specific entries ("On April 12, you noted...")
- Add "areas to investigate" (sparse data days, pattern breaks)

### 3.2 Add LLM Summary Layer

After computing the structured facts, pass them to the LLM:

```python
prompt = f"""Write a brief, supportive weekly summary from these facts.
Only make claims supported by the data. Be specific, not generic.
Facts: {structured_facts}"""
```

Use GPT-4o (not mini) for this — quality matters for user-facing prose.
Store both the structured facts and the LLM summary.

### 3.3 Extend Audit Logging to All Objects

Currently only goals/tasks have audit trails. Extend to:
- Journal entries, checkins, activities, metric observations
- Insights (status changes: candidate → active → rejected)
- Heuristics (enable/disable/deactivate)

**Definition of done for Phase 3:**
- [ ] Weekly reviews include activity summaries and insight mentions
- [ ] LLM produces human-readable narrative (not a data dump)
- [ ] All object types have audit trail on modification
- [ ] Reviews generated from WHYNN data are manually reviewed for quality

---

## Phase 4: Make It Usable (Weeks 7–8)

### 4.1 Build CLI Tool

The fastest path to daily use. Use Click + rich/tabulate for terminal output.

```bash
# Daily interaction
memorychain log "Slept 7h, mood 7/10. Did 6 rounds of bagwork, 480 strikes."
memorychain today              # show today's checkin, open tasks, active goals
memorychain search "sleep"     # keyword search across all objects

# Review and insights
memorychain review             # generate/show this week's review
memorychain insights           # list candidate insights
memorychain promote <id>       # promote insight to heuristic

# Management
memorychain goals              # list active goals
memorychain tasks              # list open tasks
memorychain import <file>      # bulk import from log file
```

### 4.2 Design the Daily Workflow

The CLI isn't just commands — it's a workflow. Define what daily use looks like:

1. **Morning:** `memorychain today` — see yesterday's summary, open tasks, active goals
2. **During day:** `memorychain log "..."` — quick entries as things happen
3. **Evening:** `memorychain log "..."` — full daily log with metrics
4. **Weekly:** `memorychain review` — see the week's synthesis + insights
5. **Ad hoc:** `memorychain search`, `memorychain insights`, `memorychain promote`

### 4.3 Web UI (Stretch Goal)

Only if the CLI workflow proves insufficient. If you build it:
- Use Streamlit for rapid prototyping (not React — too heavy for MVP)
- Five views: Today, Journal, Goals, Insights, Weekly Review
- Consume the existing API

**Definition of done for Phase 4:**
- [ ] CLI tool handles daily log → extraction → storage flow
- [ ] `memorychain today` shows a useful daily summary
- [ ] `memorychain review` generates and displays weekly review
- [ ] Insight commands work (list, promote, reject)
- [ ] You can actually use it daily for 1+ week without hitting blockers

---

## Deferred (V1.1+)

These are real needs, but not MVP-blocking:

- **Multi-user auth** — JWT, user accounts, data isolation
- **Semantic search** — Embeddings + vector similarity
- **Advanced analysis** — Contradiction detection, relapse forecasting, longitudinal language evolution
- **Notification system** — Alerts for insights, unresolved tasks, missed streaks
- **Data export** — Bulk export, migration tools
- **Mobile interface** — React Native or PWA for on-the-go logging
- **Generalized insight engine** — Abstract pattern detection across arbitrary metric pairs
- **Heuristic application** — System uses heuristics to generate warnings/guidance

---

## Success Criteria (By End of Phase 4)

- System ingests real WHYNN daily logs with ≥ 80% field accuracy
- At least 1 meaningful insight is detected from historical data
- User can promote insights to heuristics (with evidence validation)
- Weekly reviews are human-readable and reference specific entries
- All mutations are auditable with rollback capability
- You can use it daily via CLI for 1+ week
- All tests pass (aim for ≥ 30 tests covering new objects + flows)

---

## Estimated Timeline

| Phase | Focus | Weeks |
|-------|-------|-------|
| 0: Foundation Fixes | Missing tables, provenance, transactions, FTS5, extraction service | 0.5–1 |
| 1: Real Data + Extraction | WHYNN parser, field extractors, LLM for freeform, bulk import, iteration | 2–3 |
| 2: Insight Engine | Sleep-mood detector, promotion flow, rejection flow | 1.5–2 |
| 3: Weekly Review + Audit | LLM polish, activity summaries, full audit coverage | 1 |
| 4: CLI + Daily Workflow | Click CLI, daily workflow design, usability testing | 1–2 |
| **Total** | | **~8–10 weeks** |

The range accounts for the extraction iteration loop (Phase 1.6) — the
hardest part is getting extraction right on messy real data, and that takes
as long as it takes.

---

## Open Questions

- **LLM cost budget:** GPT-4o-mini extraction ≈ $0.01–0.03 per entry. GPT-4o
  for weekly review summaries ≈ $0.05–0.10 per review. Comfortable with ~$5-10/month?
- **Real-time vs. batch insight detection:** Run on every ingestion (expensive,
  immediate) or daily/weekly batch (cheaper, delayed)? Recommend weekly batch
  (tied to review generation).
- **RPG framing (buffs, XP, levels):** Treat as domain metadata? Store in
  Activity.metadata? Or build explicit XP tracking? Recommend: metadata for
  now, explicit tracking if it proves valuable.
- **ODT file import:** Several WHYNN logs are .odt format. Do we need an ODT
  parser, or can you export them as .txt?
