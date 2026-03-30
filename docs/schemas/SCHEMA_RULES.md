# Schema Rules

This document defines the cross-cutting rules that all V1 schemas must follow.

## 1. Object Categories

All V1 objects belong to one of three categories:

- `source`: raw captured material
- `authored`: user-entered or user-confirmed structured data
- `derived`: system-generated structures, links, or interpretations

V1 rule:

- every `derived` object must be traceable to one or more `source` or `authored` objects

## 2. Source Truth Rule

Raw input is never overwritten.

Implications:

- `SourceDocument.raw_text` is immutable after capture except for explicit correction workflows
- normalized or extracted data must live in separate objects
- interpretation must never replace source content

## 3. Evidence Rule

Every non-trivial derived object must carry evidence references.

Applies to:

- `Insight`
- `Heuristic`
- `WeeklyReview`
- future pattern or contradiction objects

Minimum evidence contract:

- `evidence_ids`
- optional `counterevidence_ids`
- optional `confidence`

## 4. Separation Rule

MemoryChain must distinguish between:

- observations
- interpretations
- operational guidance

In schema terms:

- `MetricObservation` and `Activity` are observations
- `Insight` is interpretation
- `Heuristic` is operational guidance

No object may mix these roles casually.

## 5. Authored Versus Derived Rule

V1 should strongly prefer explicit provenance.

Every object should answer:

- who created this
- when was it created
- was it entered directly or inferred

Suggested common fields:

- `id`
- `user_id`
- `created_at`
- `updated_at`
- `provenance`

Suggested `provenance` values:

- `user`
- `import`
- `system_extracted`
- `system_inferred`
- `system_aggregated`

## 6. Time Rule

MemoryChain needs more than one time field.

Recommended conventions:

- `created_at`: when the record was stored
- `effective_at`: when the event or content actually happened
- `updated_at`: when the record last changed

For ranged events:

- `started_at`
- `ended_at`

Why this matters:

- users often log after the fact
- imports may preserve historical timestamps
- weekly reviews aggregate by `effective_at`, not necessarily `created_at`

## 7. Optionality Rule

V1 schemas should be permissive where user logging is naturally incomplete.

Good examples of optional fields:

- body weight
- sleep quality
- duration
- tags
- end time

Bad examples of optional fields:

- object `id`
- object `created_at`
- provenance
- source linkage for derived data

## 8. Enum Discipline

Use enums only where the product truly benefits from consistency.

Strong enum candidates:

- `source_type`
- `entry_type`
- `activity_type`
- `goal_status`
- `task_status`
- `insight_status`
- `heuristic_source_type`

Avoid premature enums for:

- moods
- tags
- freeform themes

Those should start as open text or numeric scales in V1.

## 9. Validation Threshold Rule

Derived objects do not all have the same trust level.

V1 trust ladder:

- extraction: structure pulled from text into typed objects
- aggregation: summaries or linked rollups over known records
- insight: evidence-backed pattern suggestion
- heuristic: validated operational rule

Promotion rule:

- no `Heuristic` from a single source document
- no `Heuristic` from a purely emotional interpretation
- `Heuristic` requires repeated evidence, user confirmation, or correction history

## 10. Correction Rule

The user must be able to correct system output without rewriting source history.

Implications:

- user correction should create a separate record, not silently mutate inference history
- future heuristics should be able to cite correction history

This likely implies future objects such as:

- `CorrectionRecord`
- `LinkOverride`
- `InferenceRejection`

These are not required in the first schema pass but should be anticipated.
