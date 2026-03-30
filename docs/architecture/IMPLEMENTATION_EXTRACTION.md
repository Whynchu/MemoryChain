# MemoryChain Implementation Extraction

Purpose: convert the product design document into implementable system ideas while preserving the core thesis.

Source documents:
- `docs/goals/design doc/MemoryChain_Design.docx`
- `core/WHYNNFIGHT OS.odt`
- `users/Sam/logs/MUAY THAI/III_DAILY_LOGS.txt`
- `users/Sam/logs/MUAY THAI/WHYNN_MASTER_PROTOCOL_DIRECTIVE.txt`

This document is a handoff artifact for future context compaction. It intentionally strips out RPG framing and keeps only reusable product and schema ideas.

## 1. Product Thesis To Preserve

MemoryChain is not a notes app with chat. It is a structured personal memory system that:

- captures life data as typed objects
- preserves raw source truth
- derives cautious, inspectable insights from evidence
- turns validated patterns into execution guidance

Core rule:

- analysis can suggest
- execution rules must be validated before they influence behavior

## 2. Design Doc Sections Converted To Buildable Ideas

### Executive Summary

Buildable interpretation:

- The system needs ingestion, storage, retrieval, analysis, and coaching surfaces.
- The system must treat memory as structured data, not only documents.
- The system must support longitudinal behavior analysis, not just retrieval.

Immediate product implication:

- V1 must prioritize data model and event ingestion over advanced coaching.

### Five Jobs Of MemoryChain

Translated into subsystems:

- Capture -> ingestion pipeline and source storage
- Remember -> structured object store plus retrieval
- Interpret -> analysis jobs over historical data
- Coach -> prompt generation and action recommendations
- Evolve -> controlled model updates with evidence and user override

### Operational Alignment Layer

This is the most important section in the design doc.

Buildable interpretation:

- Separate observations from interpretations.
- Separate interpretations from operational rules.
- Never generate execution constraints from a single emotional or narrative entry.

Required object distinction:

- `SourceDocument`
- `Observation`
- `Insight`
- `Heuristic`

Promotion rule:

- `Insight` can become `Heuristic` only after repeated evidence, cross-context support, or direct user confirmation.

### Data Layer

The design doc is directionally right but too broad for V1.

V1 should not start with every listed object type. It should start with a narrow canonical set:

- `SourceDocument`
- `JournalEntry`
- `DailyCheckin`
- `Activity`
- `MetricObservation`
- `Protocol`
- `ProtocolExecution`
- `Goal`
- `Task`
- `WeeklyReview`
- `Insight`
- `Heuristic`

Implementation note:

- A single day of logging may produce many objects.
- Do not model the entire day as only one journal blob.

### Memory Layer

Buildable interpretation:

- `working_memory`: recent unresolved tasks, active goals, recent observations, current constraints
- `episodic_memory`: timestamped entries and events
- `semantic_self_memory`: slowly updated stable preferences, recurring triggers, validated tendencies

Implementation note:

- V1 only needs lightweight versions of these categories.
- They can be materialized as filtered views over the same core data before they become separate systems.

### Analysis Layer

Good long-term target, but too large for V1.

V1 analysis should be limited to:

- recent theme extraction across journal entries
- unresolved commitment detection
- goal-to-task-to-entry linking
- basic completion drift detection
- weekly summary generation with source references

Defer to V2+:

- contradiction detection
- relapse forecasting
- identity-belief conflict
- longitudinal language evolution
- advanced trigger clustering

### Agent Layer

The doc describes multiple agents, but V1 should likely implement roles before true independent agents.

Recommended V1 shape:

- one orchestration layer
- role-specific prompt templates
- deterministic extraction and validation steps around model calls

Proposed V1 roles:

- capture/extraction
- linking/curation
- weekly review synthesis
- safety/integrity checks

Defer multi-agent runtime complexity until the data contracts are stable.

### Repository Structure

The target monorepo structure in the design doc is reasonable, but this repo is not there yet.

Practical first build order:

1. `docs/architecture/`
2. `docs/schemas/`
3. `packages/schemas/`
4. `packages/memory-engine/`
5. `packages/analysis-engine/`
6. `apps/api/`
7. `apps/web/`

### Alignment Engine

This should not be treated as a vibe layer. It is a stateful rule system.

V1 alignment scope:

- store explicit user corrections
- store repeated failure patterns
- generate soft recommendations, not hard execution locks

Canonical V1 objects:

- `CorrectionRecord`
- `FailureFlag`
- `Heuristic`

### UI Design

The five-screen model is useful and should stay.

V1 screens can map to concrete queries:

- Today -> active tasks, recent check-in, open loops, recent notes
- Journal -> capture and browse source entries
- Goals -> active goals, linked tasks, linked evidence
- Insights -> low-volume evidence-backed findings only
- Weekly Review -> generated weekly synthesis with references

### Roadmap

The design doc is correct to keep V1 focused, but the written V1 is still slightly too broad.

Recommended V1 scope lock:

- capture journal entries
- capture structured daily check-ins
- create goals and tasks
- link entries to goals and tasks
- generate a weekly review
- support simple chat/retrieval over personal history
- store everything in inspectable structured format

Explicit V1 exclusions:

- identity modeling
- advanced graph exploration
- adaptive intervention timing
- relapse prediction
- heavy semantic self model updates

## 3. Reusable Ideas From Legacy Documents

The old system is useful only where it implies stable behavioral structure.

Keep these ideas:

- latest dated entry should resolve current state when conflicts exist
- repeated routines should be first-class objects
- daily logs contain multiple typed observations, not one undifferentiated blob
- weekly or periodic audits are useful object types
- derived state should always point back to source evidence

Discard these ideas:

- XP
- levels
- buffs/debuffs
- aura/class/state mythology
- inflated identity labels

Be careful with these ideas:

- psychological framing
- stable trait claims
- anything that looks diagnostic

## 4. Proposed V1 Data Model

### `SourceDocument`

The original raw item exactly as captured.

Suggested fields:

- `id`
- `user_id`
- `source_type` (`text`, `voice_transcript`, `import`, `manual_log`)
- `created_at`
- `effective_at`
- `title`
- `raw_text`
- `metadata`

### `JournalEntry`

A reflective or narrative entry extracted from a source document.

Suggested fields:

- `id`
- `source_document_id`
- `created_at`
- `entry_type` (`journal`, `reflection`, `note`)
- `text`
- `tags`

### `DailyCheckin`

A structured snapshot of daily self-report state.

Suggested fields:

- `id`
- `source_document_id`
- `date`
- `sleep_hours`
- `sleep_quality`
- `mood`
- `energy`
- `body_weight`
- `immediate_thoughts`
- `pain_notes`
- `hydration_start`

### `Activity`

A completed event or session.

Suggested fields:

- `id`
- `source_document_id`
- `activity_type` (`workout`, `mobility`, `breathwork`, `meal`, `recovery`, `study`)
- `started_at`
- `ended_at`
- `title`
- `notes`

### `MetricObservation`

A specific quantitative or qualitative measurement.

Suggested fields:

- `id`
- `source_document_id`
- `metric_type`
- `value`
- `unit`
- `observed_at`
- `confidence`
- `notes`

### `Protocol`

A named repeatable routine.

Suggested fields:

- `id`
- `name`
- `category`
- `description`
- `steps`
- `target_metrics`
- `status`

### `ProtocolExecution`

Evidence that a protocol was run.

Suggested fields:

- `id`
- `protocol_id`
- `source_document_id`
- `executed_at`
- `completion_status`
- `notes`

### `Goal`

Suggested fields:

- `id`
- `title`
- `description`
- `status`
- `priority`
- `target_date`

### `Task`

Suggested fields:

- `id`
- `goal_id`
- `title`
- `status`
- `due_at`
- `priority`
- `completed_at`

### `WeeklyReview`

Suggested fields:

- `id`
- `week_start`
- `week_end`
- `summary`
- `wins`
- `slips`
- `open_loops`
- `recommended_next_actions`
- `source_ids`

### `Insight`

An evidence-backed but non-authoritative pattern claim.

Suggested fields:

- `id`
- `title`
- `summary`
- `confidence`
- `evidence_ids`
- `counterevidence_ids`
- `status`

### `Heuristic`

An operational rule derived from repeated evidence or explicit user preference.

Suggested fields:

- `id`
- `rule`
- `source_type` (`validated_pattern`, `user_defined`, `correction_history`)
- `confidence`
- `evidence_ids`
- `active`

## 5. Recommended Ingestion Flow

V1 pipeline:

1. Store raw input as `SourceDocument`.
2. Extract typed structures from the source.
3. Create zero or more child objects:
   - `JournalEntry`
   - `DailyCheckin`
   - `Activity`
   - `MetricObservation`
   - `ProtocolExecution`
4. Link extracted objects to relevant `Goal` and `Task` records.
5. Generate low-risk summaries and unresolved commitment flags.
6. Periodically generate `WeeklyReview`.
7. Promote repeated validated patterns into `Insight`.
8. Promote only validated and confirmed patterns into `Heuristic`.

Non-negotiable:

- raw source is never overwritten
- derived objects are traceable
- heuristics require stronger validation than insights

## 6. Key Open Questions

These questions should be answered before significant implementation begins:

- What are the exact canonical schemas for V1?
- Which objects are user-authored versus system-derived?
- What validation threshold promotes an `Insight` to a `Heuristic`?
- How much extraction is deterministic versus LLM-based?
- What is the minimum useful weekly review output?
- How should current state be resolved when recent entries conflict?

## 7. Recommended Immediate Next Steps

1. Create schema docs for the V1 object set in `docs/schemas/`.
2. Decide canonical field names and required versus optional fields.
3. Define ingestion examples using real legacy logs rewritten into neutral schema form.
4. Define validation rules for `Insight` and `Heuristic`.
5. Only after schemas stabilize, choose backend and storage implementation details.
