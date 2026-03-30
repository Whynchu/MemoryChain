# Ingestion Examples

These examples show how one raw source can produce multiple structured objects.

## Example 1. Simple Journal Entry

Raw source:

> "I slept badly, kept putting off working on the song, and felt more clear after a walk."

Possible output:

- `SourceDocument`
- `JournalEntry`
- `MetricObservation` for poor sleep only if the system has a concrete parseable value
- no `Heuristic`
- maybe an `Insight` later if similar evidence repeats across entries

## Example 2. Daily Structured Check-In

Raw source:

> "Sleep 6.5h. Mood 4/10. Energy 3/10. 20 minute walk at lunch. Wrote nothing on the project."

Possible output:

- `SourceDocument`
- `DailyCheckin`
- `Activity` with `activity_type = walk`
- `MetricObservation` for sleep hours
- `MetricObservation` for mood
- `MetricObservation` for energy

## Example 3. Legacy Daily Log Conversion

A single daily log from the old system should not remain one giant blob after processing.

Possible output:

- `SourceDocument` for the imported text
- `DailyCheckin` for wake, sleep, mood, energy, body state
- one or more `Activity` records for workout, breathwork, mobility, meal, recovery
- multiple `MetricObservation` records for hydration, duration, distance, heart rate, weight
- `ProtocolExecution` if a named routine clearly occurred
- optional `JournalEntry` for reflective notes

## Example 4. Weekly Review

Inputs:

- all authored and source records within a date window

Output:

- one `WeeklyReview` with:
  - a bounded time range
  - evidence references
  - conservative claims
  - open loops tied to real unfinished tasks or repeated commitments

## Example 5. Insight To Heuristic Promotion

Pattern observed:

- several entries and tasks show creative task deferral after low-sleep days

Allowed first step:

- create an `Insight`

Promotion path:

- repeated evidence across multiple dates
- at least one counterexample check
- optional user confirmation

Only then:

- create a `Heuristic`
