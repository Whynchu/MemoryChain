# MemoryChain — Roadmap to MVP

**Current state: V0.6.0-dev — Phases 0–2 complete. 58 checkins, 64 tests. Phase 3 next.**

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

<details>
<summary><strong>Phase 2: Insight Detection Engine ✅</strong> (commit <code>bcda479</code>)</summary>

- Pearson correlation-based sleep→mood detector (`services/insight_detection.py`)
- `POST /detect` endpoint — runs all detectors, deduplicates by `detector_key`, respects rejection blocking
- `PUT /{id}/status` endpoint — enforces state machine (candidate→active→promoted, etc.)
- `POST /{id}/promote` endpoint — validates evidence count, time span, counter-evidence ratio; stores `promotion_snapshot`
- Schema: `detector_key` on insights, `promotion_snapshot` on heuristics, `"promoted"` status
- Idempotent DB migrations for new columns
- 17 new tests (64 total) covering math, detection, dedup, rejection blocking, state machine, promotion thresholds
</details>

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
