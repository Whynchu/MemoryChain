# MemoryChain — Prioritized Next Steps

Current state: **V0.2.0 with working backend, basic extraction, continuity tracking, and audit system.**

This document prioritizes the remaining work to reach a usable MVP and beyond.

---

## Phase 1: LLM-Powered Extraction (Weeks 1-2)

**Why first?** This is the gating item for everything. Without intelligent extraction from freeform text, the system can't actually capture real daily logs. It's currently all-or-nothing deterministic parsing.

### 1.1 Implement Structured LLM Extraction

**Current state:** Ingestion service has hardcoded parsing logic. It doesn't use the LLM.

**What to build:**
- Update `services/llm.py` to implement structured extraction prompts
- For each source document, call the LLM to extract:
  - `JournalEntry` (text, tags, sentiment hints)
  - `DailyCheckin` (sleep, mood, energy, metrics)
  - `Activity` list (what did they do, for how long)
  - `MetricObservation` list (quantified measurements)
  - `Task` list (goals mentioned as `todo:` or implied)

**Implementation approach:**
- Use OpenAI function calling or structured outputs (GPT-4o-mini supports both)
- Pydantic models as extraction targets
- Fallback to local model if OPENAI_API_KEY not set
- Log extraction confidence and let lower-confidence results be flagged for review

**Testing:**
- Write extraction tests for sample daily logs
- Test against 1-2 WHYNN logs to validate quality
- Measure: extraction accuracy, token cost, latency

**Definition of done:**
- `POST /api/v1/ingest` successfully extracts structured objects from messy journal text
- LLM-based extraction is toggled via env var `MEMORYCHAIN_LLM_PROVIDER`
- Tests pass with real sample data

### 1.2 Ingest Real WHYNN Logs

**What to do:**
- Write a bulk import tool: read WHYNN txt files from `users/Sam/logs/MUAY THAI/`
- Parse the historical logs
- Ingest them as SourceDocuments + extract structured objects
- Verify nothing breaks

**Outcome:**
- System can handle multi-month historical logs
- Discover parsing edge cases and fix them
- See what real extracted data looks like

---

## Phase 2: Insight & Heuristic Promotion Engine (Weeks 3-4)

**Why next?** This is the intellectual core. Without promotion logic, the system just stores logs but doesn't *learn*.

### 2.1 Implement Insight Generation

**Current state:** Schemas exist, objects exist in DB, no promotion logic.

**What to build:**

**Thresholds (locked decisions):**
- Minimum evidence: **≥ 3 observations within 14 days**
- Time window: Consider only data from past 60 days
- Confidence scale: 0.0–1.0 (0.3–0.6 = moderate, 0.6–0.8 = strong)

**Algorithm (deterministic first pass):**
1. Scan recent journal entries for repeated keywords (e.g., "sleep", "anxiety", "energy")
2. Scan daily checkins for correlated metrics (e.g., low sleep → low energy)
3. For each detected pattern, create candidate `Insight` with:
   - Title: "Pattern: Low sleep correlates with low mood"
   - Summary: "On days with <6h sleep, mood averaged 1.2 points lower"
   - Evidence IDs: list of supporting observations
   - Confidence: calculated from consistency ratio
   - Status: `candidate` (awaiting user review)

**Implementation:**
- New service: `services/insights.py` with `detect_candidate_insights()` function
- New endpoint: `POST /api/v1/insights/detect` (for manual trigger) or auto-run on weekly review
- Store Insight objects in new table: `insights`
- Tests: "Given 5 low-sleep days with low mood, should create Insight with confidence ≥0.6"

**Definition of done:**
- Insight detection runs on weekly review generation
- At least 3 test cases pass (mood correlation, sleep correlation, activity pattern)
- Low-confidence insights (< 0.3) are not surfaced

### 2.2 Implement Heuristic Promotion

**Thresholds (locked decisions):**
- Minimum evidence for Heuristic: **≥ 5 supporting observations**
- Time span: Pattern across **≥ 3 weeks**
- Counterevidence ratio: Supporting outnumber counter by **≥ 3:1**
- **User confirmation required** (never auto-promoted)

**Algorithm:**
1. User explicitly promotes an Insight to Heuristic (UI button or API call)
2. System validates: do the promotion thresholds hold?
3. If valid, create `Heuristic` with confidence inherited from Insight
4. If invalid, return 409 Conflict with explanation of gaps

**Implementation:**
- New endpoint: `POST /api/v1/insights/{id}/promote`
- Validation logic in `services/insights.py`
- New table: `heuristics`
- Tests: "Given Insight with 3 observations, should reject promotion (too few)"

**Definition of done:**
- Heuristic promotion validates minimum thresholds
- User can only promote Insights with sufficient evidence
- Promotion decision is logged in audit trail

### 2.3 Implement Heuristic Application (Optional V2+)

**Defer to V2.** Once heuristics exist, the system could use them for:
- Warnings ("You're planning a late creative session with <6h sleep — past pattern: lower productivity")
- Guidance suggestions ("Based on your pattern, recovery day after high-stress week works")

For now, just store them. The act of *validating* patterns is the value.

---

## Phase 3: Real Data Testing (Week 5)

**Why?** The system works on toy data. Real logs are messier. This phase finds and fixes edge cases.

### 3.1 Ingest Full WHYNN History

**What to do:**
- Use bulk import tool from Phase 1.2
- Ingest all available WHYNN logs (3+ months)
- Run insight detection across historical data
- Manually review generated Insights for quality

**Checks:**
- No crashes or data corruption
- Extraction accuracy ≥ 80% (spot-check 20 random entries)
- Generated Insights are sensible (not spurious correlations)
- Query performance acceptable (list goals, search entries, generate review should be <500ms)

**Outcome:**
- Discover parsing edge cases and fix them
- Tune insight detection thresholds if needed
- See real engagement patterns (adherence, streaks, gaps)

### 3.2 Iterate on Weekly Review Quality

**Current state:** Reviews include engagement metrics; content is basic aggregation.

**Improvements:**
- Add LLM polish: "Write a supportive summary from these facts"
- Include top 3 insights (if any) in review
- Surface "areas to investigate" (missing data, pattern breaks)
- Add user-facing narrative, not just metrics

**Testing:**
- Generate reviews for 4 weeks of WHYNN data
- Manually review for quality, accuracy, tone
- Adjust LLM prompt if needed

---

## Phase 4: Correction & Override Workflow (Week 6)

**Why?** User trust depends on being able to fix mistakes. Currently only goals/tasks have audit trails.

### 4.1 Extend Audit Logging to All Objects

**Current state:** Goals and tasks have audit logs. Everything else doesn't.

**What to build:**
- Add audit logging to: journal entries, checkins, insights, heuristics
- Extend rollback endpoint to support all object types
- UI for "view this object's history and corrections"

**Definition of done:**
- User can correct any extracted object and see full change history
- Rollback is possible for all objects

### 4.2 Implement Rejection Workflow for Derived Objects

**Current state:** Insights and Heuristics can be marked `rejected`, but rejection doesn't prevent re-creation.

**What to build:**
- When user rejects an Insight, log the rejection reason
- Prevent re-creation of similar Insights (check counterevidence)
- Expose rejection history for debugging

---

## Phase 5: Frontend / CLI (Weeks 7-8)

**Why?** Right now you can only interact via API or direct DB. Need a human-usable interface.

### 5.1 Build CLI Tool

**Quick path (if you prefer terminal workflows):**
- Simple CLI: `memorychain chat "I woke up at 6am, slept 7 hours, felt great"`
- CLI: `memorychain today` — show today's summary (tasks, recent entries, insights)
- CLI: `memorychain review --week 2024-04-01` — show weekly review
- CLI: `memorychain search "sleep problems"` — search and display results

**Implementation:** Click + tabulate, output to terminal

### 5.2 Build Web Frontend (Alternative)

**More involved (if you want a web UI):**
- React + TypeScript
- Five-screen model from original design:
  1. **Today** — current state, recent entries, open tasks
  2. **Journal** — search, tag filtering, detail view
  3. **Goals** — list, create, track progress
  4. **Insights** — view candidates, promote to heuristics
  5. **Weekly Review** — historical reviews, trend charts

**Implementation:** Vite + React, consume API built in Phase 1-4

**Recommendation:** Start with CLI. Simpler, faster, good enough for personal use. Upgrade to web UI if needed.

---

## Deferred (V1.1+)

These are important but not blocking MVP:

- **Multi-user auth** — Still single-user, static API key
- **Semantic search** — Keyword search works; embeddings can wait
- **Advanced analysis** — Identity modeling, relapse prediction, contradiction detection
- **Notifications** — Alerting users to insights, unresolved tasks
- **Data export** — Bulk export, migrations

---

## Success Criteria (By End of Phase 5)

- ✅ System can ingest real messy daily logs (WHYNN data)
- ✅ Extraction accuracy ≥ 80% (LLM-powered)
- ✅ Insight detection works (≥ 3 meaningful patterns discovered from 3mo data)
- ✅ Heuristic promotion validated (user can lock patterns into rules)
- ✅ Weekly reviews are human-readable and insightful
- ✅ All corrections are auditable with rollback available
- ✅ You can use it daily (via CLI or web UI)
- ✅ Tests remain green (aim for ≥ 90% coverage)

---

## Estimated Timeline

| Phase | Effort | Week |
|-------|--------|------|
| 1: LLM Extraction | High | 1–2 |
| 2: Insight/Heuristic | High | 3–4 |
| 3: Real Data Testing | Medium | 5 |
| 4: Correction Workflow | Low | 6 |
| 5: Frontend/CLI | Medium | 7–8 |
| **Total** | | **8 weeks** |

---

## Immediate Actions (This Week)

1. **Set OpenAI API key** in `.env` or environment (if using cloud LLM)
2. **Wire up LLM extraction** in `services/llm.py` — structured extraction prompts
3. **Write bulk import tool** to parse WHYNN logs
4. **Create 5-10 extraction test cases** from real log data
5. **Run against real data** — ingest 1 week of WHYNN logs, see what breaks

---

## Notes

- **Keep scope locked** — Resist adding agents, multi-user, or fancy UI until core logic works.
- **Test with real data early** — The WHYNN logs are your validation source. Use them constantly.
- **Measure what matters** — Extraction accuracy, Insight quality, user trust. Don't optimize for vanity metrics.
- **Ship incrementally** — After Phase 1, you have a working ingestion pipeline. After Phase 2, you have learning logic. Etc.

---

## Questions to Resolve

- **LLM cost budget:** Are you comfortable with $5-10/month for structured extraction? (Rough estimate with GPT-4o-mini on 1-2 entries/day)
- **Real-time vs batch:** Should insights be detected immediately (expensive) or daily batch (cheaper)?
- **Insight confidence thresholds:** The proposed minimums (3 observations, 14 days) might be too strict or too loose once you test on real data. Be ready to tune.
