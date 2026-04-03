# MemoryChain — Roadmap to MVP

**Current state: V0.8.0-dev — Phases 0–4 complete. 58 checkins, 106 tests. MVP reached.**

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

<details>
<summary><strong>Phase 3: Weekly Review + Audit Expansion ✅</strong> (commit <code>e7f1250</code>)</summary>

- Enriched weekly reviews: insight_mentions, activity_summary, metric_highlights, sparse_data_flags, notable_entries
- Optional LLM narrative layer (GPT-4o) with evidence-grounded prompting; graceful fallback to deterministic summary
- Average sleep included in summary text alongside mood
- Audit trail expanded: insight creation, heuristic creation, insight status changes
- New repo methods: get_activities_for_week, get_metrics_for_week, get_insights_for_week
- DB migrations for 6 new weekly_reviews columns (idempotent)
- 18 new tests (82 total) covering helpers, LLM mock, enriched reviews, audit expansion
</details>

---

## Phase 4: Make It Usable

<details>
<summary><strong>Phase 4: CLI Tool + Daily Workflow ✅</strong> (commit <code>867b5b4</code>)</summary>

- CLI package (`apps/cli/`) using Click + Rich with 12 commands
- `memorychain log` — freeform text → extraction → storage with confirmation flow
- `memorychain today` — daily summary (checkin, open tasks, active goals)
- `memorychain search` — keyword search across all objects
- `memorychain review` — show/generate weekly reviews
- `memorychain insights` — list with optional `--detect` flag
- `memorychain promote` / `accept` / `reject` — insight lifecycle management
- `memorychain goals` / `tasks` / `heuristics` — list views with rich tables
- `memorychain status` — API health check
- httpx-based API client matching real endpoint contracts
- Rich display: panels, tables, status badges, extraction summaries
- Env-var config: `MEMORYCHAIN_API_URL`, `MEMORYCHAIN_API_KEY`, `MEMORYCHAIN_USER_ID`
- 24 CLI tests via Click CliRunner with mocked httpx (106 total)
</details>

### Daily Workflow

1. **Morning:** `memorychain today` — yesterday's summary, open tasks, active goals
2. **During day:** `memorychain log "..."` — quick entries as things happen
3. **Evening:** `memorychain log "..."` — full daily log with metrics
4. **Weekly:** `memorychain review --generate` — synthesis + insights
5. **Ad hoc:** `memorychain search`, `memorychain insights --detect`, `memorychain promote`

### Definition of Done — Phase 4

- [x] CLI handles daily log → extraction → storage flow
- [x] Extraction confirmation works in freeform mode
- [x] `memorychain today` shows a useful daily summary
- [x] `memorychain review` generates weekly review
- [x] Insight commands work (list, promote, reject)
- [ ] Usable daily for 1+ week without blockers (validation in progress)

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
- CLI is usable daily for 1+ week (validation in progress)
- All tests pass (target ≥ 50 tests covering detection + lifecycle flows) ✅ **106 tests passing**

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
