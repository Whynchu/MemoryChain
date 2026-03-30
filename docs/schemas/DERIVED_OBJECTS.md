# Derived Objects

This document covers the core V1 objects that are produced by extraction, aggregation, or inference.

## 1. `WeeklyReview`

Purpose:

- generate a structured synthesis of a bounded period

Category:

- `derived`

Fields:

- `id`
- `user_id`
- `created_at`
- `week_start`
- `week_end`
- `summary`
- `wins`: array of strings
- `slips`: array of strings
- `open_loops`: array of strings
- `recommended_next_actions`: array of strings
- `source_ids`: array of evidence object ids
- `confidence`: optional

Rules:

- must cite evidence
- should avoid claims that are not supportable by source material

## 2. `Insight`

Purpose:

- capture an evidence-backed interpretation or pattern

Category:

- `derived`

Fields:

- `id`
- `user_id`
- `created_at`
- `title`
- `summary`
- `confidence`
- `status`: `candidate`, `active`, `rejected`, `archived`
- `evidence_ids`
- `counterevidence_ids`: optional
- `time_window_start`: optional
- `time_window_end`: optional

Rules:

- insights are suggestive, not authoritative
- insights must be reviewable and rejectable
- insights should not make diagnostic or identity-hardening claims

## 3. `Heuristic`

Purpose:

- capture a validated execution rule

Category:

- `derived`

Fields:

- `id`
- `user_id`
- `created_at`
- `updated_at`
- `rule`
- `source_type`: `validated_pattern`, `user_defined`, `correction_history`
- `confidence`
- `active`
- `evidence_ids`
- `counterevidence_ids`: optional
- `validation_notes`: optional

Rules:

- must have stronger evidence than `Insight`
- should describe an action, constraint, or preference
- should not be generated from one isolated emotional event

Examples:

- good: "When sleep is below 6 hours, avoid scheduling difficult creative work late at night."
- bad: "User is self-sabotaging because they fear success."

## 4. Future Derived Objects

These are likely useful but should not be required before V1 stabilizes:

- `CorrectionRecord`
- `FailureFlag`
- `GoalLink`
- `TaskLink`
- `ThemeCluster`
- `PreferenceProfile`

Reason to delay:

- these objects depend on clear ingestion and evidence rules
- adding them too early increases ambiguity in the rest of the model
