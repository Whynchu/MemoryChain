# MemoryChain — Roadmap to MVP

Current state: **V0.3.0 — Phase 0 complete, Phase 1A (conversational questionnaires
+ hybrid extraction) complete. 19 passing tests.**

This document defines the work remaining to reach a usable MVP. Phases are
ordered by dependency — each unlocks the next.

---

## Phase 0: Foundation Fixes ✅ COMPLETE

All items delivered in commit `f114cb3`:
- 6 new tables (activities, metric_observations, protocols, protocol_executions, insights, heuristics)
- Provenance column on all tables
- Transaction safety for multi-step writes
- Substantive-message filtering for journal entries
- FTS5 search index
- Shared extraction service (`services/extraction.py`)
- 16 passing tests

---

## Phase 1A: Conversational Questionnaires + Hybrid Extraction ✅ COMPLETE

**Context:** After analyzing the WHYNN logs, the approach pivoted from bulk log
import to building a conversational input pipeline first — the system should be
usable for *new* daily data before worrying about historical import.

### What was built:

1. **Questionnaire system** — Template-driven conversational data collection
   - Schema: `questionnaire_templates` + `questionnaire_sessions` tables
   - Pydantic models: `QuestionDef`, `QuestionnaireTemplate`, `QuestionnaireSession`
   - Full CRUD repository methods
   - REST endpoints: `POST/GET /api/v1/questionnaires/templates`

2. **Natural language answer parser** (`services/answer_parser.py`)
   - Handles: numeric ("7 hours", "~140"), scale ("8/10"), boolean, choice, text
   - Word-to-number conversion, approximate value handling

3. **Chat-questionnaire integration** (`services/questionnaire.py`)
   - `/morning`, `/checkin`, `/training` commands start questionnaire sessions
   - Active sessions intercept chat flow — answers are parsed, not extracted
   - On completion: creates DailyCheckin, Activity, or MetricObservation records

4. **LLM extraction upgrade** (`services/extraction.py`)
   - Three modes: `regex` (default), `llm` (OpenAI), `hybrid` (LLM + regex fallback)
   - Chat now uses `hybrid` mode
   - GPT-4o-mini for structured extraction, regex fallback when no API key

5. **Provenance plumbing** — All Create schemas now carry provenance through to
   the database. LLM-extracted and questionnaire-sourced data is tagged
   `system_extracted` for data lineage tracking.

### 19 tests passing (16 original + 3 new)

---

## Phase 1B: Real Data Import + Extraction Iteration

**Why still needed:** The questionnaire system handles *new* data. Historical
WHYNN logs (~26 daily entries) still need import to seed the insight engine.

### 1.1 Characterize the WHYNN Logs ✅ (Done in prior session)

### 1.2 Build Section-Based Log Parser

Split entries by date header, then by section keyword
(`SYSTEM METRICS:`, `TRAINING EXECUTION:`, etc.). Deterministic, no LLM needed.

### 1.3 Build Deterministic Field Extractors Per Section

Regex extractors for structured fields: sleep hours, mood, body weight,
strike counts, rounds, duration, hydration, CO₂ holds, etc.

### 1.4 Build Bulk Import Tool

```python
# scripts/import_whynn_logs.py
# Parse → Extract → Create SourceDocument + DailyCheckin + Activities + Metrics
```

### 1.5 Iterate Extraction on Real Failures

Spot-check 20+ entries. Score accuracy. Fix failure modes. Re-import. Repeat
until ≥ 80% accuracy on structured fields.

**Definition of done for Phase 1B:**
- [ ] Bulk import processes all WHYNN log entries
- [ ] Each entry produces: SourceDocument + DailyCheckin + Activities + MetricObservations + JournalEntry
- [ ] Spot-check accuracy ≥ 80% on structured fields
- [ ] Import tool reports extraction stats

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
