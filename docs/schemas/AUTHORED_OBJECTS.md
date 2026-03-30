# Authored Objects

This document covers the core V1 objects that are directly entered, imported, or user-confirmed.

## 1. `SourceDocument`

Purpose:

- preserve the original captured payload

Category:

- `source`

Fields:

- `id`: unique identifier
- `user_id`: owner of the document
- `source_type`: `text`, `voice_transcript`, `import`, `manual_log`
- `created_at`: record creation timestamp
- `effective_at`: when the content was authored or occurred
- `title`: optional short label
- `raw_text`: original textual payload
- `metadata`: source-specific structured metadata

Notes:

- this is the root evidence object
- later extraction should point back here

## 2. `JournalEntry`

Purpose:

- store reflective or narrative content as a first-class object

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `source_document_id`
- `created_at`
- `effective_at`
- `entry_type`: `journal`, `reflection`, `note`
- `title`: optional
- `text`
- `tags`: optional string array

Notes:

- some `SourceDocument` records may produce one `JournalEntry`
- others may produce none if the source is purely structured

## 3. `DailyCheckin`

Purpose:

- capture a daily self-report snapshot

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `source_document_id`
- `date`
- `created_at`
- `effective_at`
- `sleep_hours`: optional number
- `sleep_quality`: optional 1-10 scale
- `mood`: optional 1-10 scale
- `energy`: optional 1-10 scale
- `body_weight`: optional number
- `body_weight_unit`: optional enum or string
- `immediate_thoughts`: optional text
- `pain_notes`: optional text
- `hydration_start`: optional number
- `hydration_unit`: optional string

Notes:

- this is not a whole-day summary
- it is one structured snapshot

## 4. `Activity`

Purpose:

- store completed activities or sessions

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `source_document_id`
- `created_at`
- `effective_at`
- `activity_type`: `workout`, `mobility`, `breathwork`, `meal`, `recovery`, `study`, `social`, `work`
- `started_at`: optional
- `ended_at`: optional
- `title`
- `description`: optional
- `notes`: optional

Notes:

- one day may contain many activities
- an activity may later be linked to metrics and protocols

## 5. `MetricObservation`

Purpose:

- capture a single measurable or structured observation

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `source_document_id`
- `created_at`
- `effective_at`
- `metric_type`
- `value`
- `unit`: optional
- `value_type`: `number`, `string`, `boolean`
- `notes`: optional

Examples:

- sleep hours
- body weight
- heart rate
- hydration total
- pain score

Notes:

- keep `metric_type` open in V1
- do not hardcode every imaginable metric yet

## 6. `Protocol`

Purpose:

- define a named repeatable routine

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `created_at`
- `updated_at`
- `name`
- `category`
- `description`: optional
- `steps`: optional ordered list
- `target_metrics`: optional array
- `status`: `active`, `archived`, `draft`

Notes:

- protocols are templates
- they are not evidence that something happened

## 7. `ProtocolExecution`

Purpose:

- record that a protocol was attempted or completed

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `protocol_id`
- `source_document_id`
- `created_at`
- `executed_at`
- `completion_status`: `completed`, `partial`, `skipped`
- `notes`: optional

Notes:

- this gives repeated routines first-class history

## 8. `Goal`

Purpose:

- represent a medium- or long-horizon objective

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `created_at`
- `updated_at`
- `title`
- `description`: optional
- `status`: `active`, `paused`, `completed`, `dropped`
- `priority`: `low`, `medium`, `high`
- `target_date`: optional

## 9. `Task`

Purpose:

- represent a concrete action item

Category:

- `authored`

Fields:

- `id`
- `user_id`
- `goal_id`: optional
- `created_at`
- `updated_at`
- `title`
- `description`: optional
- `status`: `todo`, `in_progress`, `done`, `canceled`
- `priority`: `low`, `medium`, `high`
- `due_at`: optional
- `completed_at`: optional

Notes:

- tasks may exist without goals
- goal linkage should be encouraged, not required
