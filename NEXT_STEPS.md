# MemoryChain — Roadmap to MVP

**Current state: V0.5.0-dev — Phases 0–1 complete. 58 checkins, 47 tests. Phase 2 next.**

This document defines the work remaining to reach a usable MVP. Phases are
ordered by dependency — each unlocks the next.

---

## Completed Work

<details>
<summary><strong>Phase 0: Foundation Fixes ✅</strong> (commit <code>f114cb3</code>)</summary>

- 6 new tables (activities, metric_observations, protocols, protocol_executions, insights, heuristics)
- Provenance column on all tables
- Transaction safety for multi-step writes
- Substantive-message filtering for journal entries
- FTS5 search index
- Shared extraction service (`services/extraction.py`)
</details>

<details>
<summary><strong>Phase 1A: Conversational Questionnaires + Hybrid Extraction ✅</strong> (commit <code>66764f4</code>)</summary>

- Questionnaire system — template-driven Q&A via `/morning`, `/checkin`, `/training`
- Natural language answer parser (numeric, scale, boolean, choice, text)
- Hybrid LLM extraction (GPT-4o-mini + regex fallback)
- Provenance plumbing through all Create schemas
</details>

<details>
<summary><strong>Phase 1B: Real Data Import ✅</strong> (commit <code>ea23197</code>)</summary>

- WHYNN log parser + field extractors (two format variants)
- Bulk import script (`scripts/import_whynn_logs.py`)
- 26/26 entries → 21 checkins, 15 activities, 56 metrics, 14 journal entries
- All provenance = `import`, structured fields spot-checked accurate
</details>

**Data baseline:** 58 daily checkins in the database, all with both `sleep_hours`
and `mood` populated. This is the dataset Phase 2 detectors run against.

---

## Phase 2: Insight Detection Engine

**Goal:** Prove the observation → interpretation → rule pipeline works end-to-end
with one real detector, then make the lifecycle (promote, reject, re-detect)
bulletproof before adding more detectors.

### 2.1 Schema Evolution

Before writing detection logic, add the infrastructure that makes insights
manageable:

**Add `detector_key` column to `insights` table:**

```sql
ALTER TABLE insights ADD COLUMN detector_key TEXT;
-- e.g., "sleep_mood_v1", "training_energy_v1"
```

This is how we fingerprint insights for dedup and rejection tracking. Without
it, the system can't know "I already generated (or the user rejected) this
type of insight" — it would blindly re-create rejected patterns.

**Add `promotion_snapshot` column to `heuristics` table:**

```sql
ALTER TABLE heuristics ADD COLUMN promotion_snapshot TEXT;
-- JSON blob: thresholds applied, values at promotion time
```

When a heuristic is promoted, record *why it qualified* — the thresholds used,
the evidence counts, the correlation values. The audit trail should say "promoted
because r=0.72, n=14, span=28 days" not just "promoted."

### 2.2 Sleep-Mood Correlation Detector

**Why this one first:** It needs exactly two numeric fields (`sleep_hours`,
`mood`) that we have 100% coverage on. The correlation is meaningful and
personally actionable.

**Algorithm — statistically grounded, not bucket-hacking:**

1. Query checkins where both `sleep_hours` and `mood` are non-null
2. If fewer than 7 data points → skip (insufficient for correlation)
3. Compute **Pearson correlation coefficient** (r) between sleep_hours and mood
4. If |r| < 0.3 → no meaningful correlation → skip
5. Compute **descriptive group stats** for the human-readable summary:
   - Split at median sleep hours (data-driven, not a magic 6h cutoff)
   - Report mean mood for each group
6. Map r → `confidence`:
   - |r| 0.3–0.5 → confidence 0.4–0.6 (moderate)
   - |r| 0.5–0.7 → confidence 0.6–0.8 (strong)
   - |r| > 0.7 → confidence 0.8–0.95 (very strong)
7. Check for existing insight with same `detector_key` + `user_id`:
   - If active/candidate exists → update if data changed significantly, else skip
   - If rejected exists → do not re-create (respect user's judgment)
8. Create candidate Insight with evidence_ids pointing to the checkin IDs used

**Why Pearson instead of bucket comparison:**
- Uses all data points instead of discarding information via arbitrary grouping
- Produces a real correlation coefficient that maps to `confidence` naturally
- Still generates plain-language summaries ("on low-sleep days, mood averaged X
  vs Y") but the *detection* is principled
- ~5 extra lines of code (stdlib `statistics` module)

**Output:**
```json
{
  "detector_key": "sleep_mood_v1",
  "title": "Sleep duration correlates with mood",
  "summary": "Your sleep and mood are moderately correlated (r=0.58). On days with <6.5h sleep, mood averaged 4.8/10 vs 7.2/10 on days with ≥6.5h (n=58, 30-day window).",
  "confidence": 0.65,
  "status": "candidate",
  "evidence_ids": ["dc_xxx", ...],
  "time_window_start": "2025-04-07",
  "time_window_end": "2025-05-02"
}
```

### 2.3 Detection Service & Endpoint

**New file: `services/insight_detection.py`**

```
detect_sleep_mood(repo, user_id, lookback_days=60) → Insight | None
run_all_detectors(repo, user_id) → list[Insight]
```

Pattern: each detector is a standalone function. `run_all_detectors` calls them
all and returns newly created insights. Adding a detector = writing one function
and registering it in the list.

**Endpoint: `POST /api/v1/insights/detect`**
- Triggers `run_all_detectors` for the given user
- Returns list of newly created candidate insights
- Idempotent: re-running won't duplicate insights (detector_key dedup)

### 2.4 Heuristic Promotion

**Endpoint: `POST /api/v1/insights/{id}/promote`**

Validates before promoting:
- Insight status must be `active` (user has reviewed and accepted it)
- ≥ 5 supporting observations in evidence_ids
- Pattern spans ≥ 3 weeks (time_window_end − time_window_start)
- Counter-evidence ratio ≤ 1:3

If valid:
- Creates Heuristic linked to the Insight via `insight_id`
- Stores `promotion_snapshot` with the exact thresholds and values at
  promotion time
- Updates Insight status to `promoted`

If invalid:
- Returns 409 with structured explanation of which thresholds weren't met

**Promotion is always user-initiated.** The system surfaces candidates; the
user decides what becomes a rule.

### 2.5 Insight Lifecycle (Accept / Reject / Archive)

**Endpoint: `PUT /api/v1/insights/{id}/status`**

Status transitions:
```
candidate → active     (user reviewed, accepts the pattern)
candidate → rejected   (user disagrees — store reason)
candidate → archived   (not useful right now, revisit later)
active    → promoted   (via promote endpoint only)
active    → rejected   (user changed their mind)
active    → archived
rejected  → archived   (cleanup)
```

On rejection:
- Store `rejection_reason` (free text from user)
- The `detector_key` + `rejected` status combination prevents re-generation
- Audit log records the status change with timestamp and reason

### 2.6 Second Detector (Stretch)

Only after sleep-mood works end-to-end:
- **Training volume → next-day energy** — strike count / session count correlated
  with next day's energy rating
- **Adherence decay** — missed prompt cycles correlate with fewer journal entries

Each detector follows the same function signature. Generalize into a framework
only after 3+ detectors reveal common patterns.

### Definition of Done — Phase 2

- [ ] `detector_key` and `promotion_snapshot` columns added (migration-safe)
- [ ] Sleep-mood detector runs against real data, produces ≥1 meaningful insight
- [ ] Detection is idempotent (re-running doesn't duplicate)
- [ ] Rejected detector_keys are not re-generated
- [ ] Promote endpoint validates thresholds, stores snapshot
- [ ] Status transitions enforce valid state machine
- [ ] Tests: detection, dedup, promotion (pass + fail), rejection, re-detect blocking

---

## Phase 3: Weekly Review + Audit Expansion

### 3.1 Weekly Review Improvements

Current state: deterministic aggregation. Upgrade to include:
- Top insights (if any) surfaced during the review period
- Activity summaries (session counts, strike totals, training types)
- Specific entry references ("On April 12, you noted…")
- Sparse-data flags ("No check-in on Tuesday — was that intentional?")

### 3.2 LLM Summary Layer

After computing structured facts, pass to LLM for human-readable narrative:
- Use GPT-4o (not mini) — quality matters for user-facing prose
- Store both structured facts and LLM summary
- Prompt enforces evidence grounding: "Only make claims supported by the data"

### 3.3 Audit Trail Expansion

Extend audit logging beyond goals/tasks to cover:
- Journal entries, checkins, activities, metric observations
- Insight status changes (candidate → active → rejected → promoted)
- Heuristic lifecycle (activate, deactivate, update)

### Definition of Done — Phase 3

- [ ] Weekly reviews include insight mentions and activity summaries
- [ ] LLM narrative is human-readable, not a data dump
- [ ] All object types have audit trail on modification
- [ ] Reviews from real WHYNN data manually reviewed for quality

---

## Phase 4: Make It Usable

### 4.1 CLI Tool

Click + rich/tabulate for terminal output:

```bash
memorychain log "Slept 7h, mood 7/10. Did 6 rounds of bagwork."
memorychain today              # today's checkin, open tasks, active goals
memorychain search "sleep"     # keyword search across all objects
memorychain review             # generate/show this week's review
memorychain insights           # list candidates
memorychain promote <id>       # promote insight → heuristic
memorychain goals              # list active goals
memorychain tasks              # list open tasks
memorychain import <file>      # bulk import from log file
```

### 4.2 Extraction Confirmation Flow

*Deferred from Phase 1A.* When chat extraction detects structured data, confirm
with the user before storing. This is a UX concern that belongs here, not in the
extraction layer — it needs the CLI or UI to present confirmations naturally.

Approach:
- After extraction, present a summary: "I found: Sleep 7h, Mood 7/10, Activity: bagwork. Store this?"
- User confirms or corrects
- Corrected values override extracted values (provenance: `user`)
- Only relevant for freeform chat input, not questionnaire mode (which is already interactive)

### 4.3 Daily Workflow Design

1. **Morning:** `memorychain today` — yesterday's summary, open tasks, active goals
2. **During day:** `memorychain log "..."` — quick entries as things happen
3. **Evening:** `memorychain log "..."` — full daily log with metrics
4. **Weekly:** `memorychain review` — synthesis + insights
5. **Ad hoc:** `memorychain search`, `memorychain insights`, `memorychain promote`

### 4.4 Web UI (Stretch)

Only if CLI proves insufficient. Streamlit for rapid prototyping:
- Five views: Today, Journal, Goals, Insights, Weekly Review
- Consumes existing API

### Definition of Done — Phase 4

- [ ] CLI handles daily log → extraction → storage flow
- [ ] Extraction confirmation works in freeform mode
- [ ] `memorychain today` shows a useful daily summary
- [ ] `memorychain review` generates weekly review
- [ ] Insight commands work (list, promote, reject)
- [ ] Usable daily for 1+ week without blockers

---

## Deferred (V1.1+)

- **Multi-user auth** — JWT, user accounts, data isolation
- **Semantic search** — Embeddings + vector similarity
- **Advanced analysis** — Contradiction detection, relapse forecasting, longitudinal language evolution
- **Notification system** — Alerts for insights, unresolved tasks, missed streaks
- **Data export** — Bulk export, migration tools
- **Mobile interface** — React Native or PWA for on-the-go logging
- **Generalized insight engine** — Abstract pattern detection across arbitrary metric pairs
- **Heuristic application** — System uses heuristics to generate warnings/guidance
- **RPG framing** — Buff/XP tracking stored in Activity.metadata for now; explicit tracking if it proves valuable

---

## Success Criteria (By End of Phase 4)

- At least 1 statistically grounded insight detected from real data
- User can promote insights to heuristics with evidence validation
- Rejected patterns are never re-generated
- Weekly reviews are human-readable and reference specific entries
- All mutations are auditable
- CLI is usable daily for 1+ week
- All tests pass (target ≥ 50 tests covering detection + lifecycle flows)

---

## Resolved Decisions

These were open questions in earlier iterations. Documenting the resolution
to prevent backtracking:

| Question | Resolution |
|----------|-----------|
| LLM cost budget | GPT-4o-mini for extraction (~$0.01/entry), GPT-4o for summaries (~$0.10/review). Acceptable. |
| Real-time vs. batch detection | Manual trigger for now (`POST /detect`). Weekly batch (tied to review) later. |
| RPG framing (buffs, XP) | Store as metadata in Activity. Defer explicit tracking. |
| ODT file import | Export to .txt manually. No ODT parser needed. |
| Insight generation approach | Deterministic statistics (Pearson correlation), not LLM-detected. LLM used only for phrasing. |
| Sleep threshold | Data-driven (median split), not hardcoded 6 hours. |
| Confirmation flow timing | Deferred to Phase 4 (needs CLI/UI to be useful). |
| Confidence scale | 0.0–1.0 numeric, derived from correlation coefficient. User-facing labels mapped in UI layer. |
