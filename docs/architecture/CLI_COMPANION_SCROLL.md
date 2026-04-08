# MemoryChain CLI Companion Scroll

## Purpose

Define the target behavior for MemoryChain as a CLI-first operational companion.

This document is not a generic product wishlist. It is a working spec for how
the system should think, speak, remember, infer, and guide.

The immediate priority is not mobile polish or a richer dashboard. The
immediate priority is making the CLI feel like a highly intelligent, persistent
companion that can:

- hold continuity across days and weeks
- protect metric accuracy
- notice patterns and discrepancies
- guide the user toward declared and behaviorally validated priorities

## Core Thesis

MemoryChain should not behave like a chatbot attached to a tracker.

It should behave like a persistent operational companion with four core traits:

- continuity: it remembers what matters without needing to be re-briefed
- initiative: it opens the most relevant thread for the moment
- precision: facts remain factual and traceable
- alignment: it helps the user close the gap between stated intent and lived behavior

The CLI is the first true product surface for this. Web and mobile can follow
once the companion loop is real.

## Companion Contract

MemoryChain must do all of the following:

- preserve raw source truth
- distinguish facts from interpretations
- infer when useful, but never let inference corrupt factual records
- use recent and long-term context to decide what matters now
- help the user name recurring patterns and integrate them into self-understanding
- help the user commit to realistic plans when there is a history of drift

MemoryChain must not do any of the following:

- store inferred mood as if it were explicitly reported mood
- blur metrics, guesses, and validated patterns into one layer
- make strong psychological claims without evidence
- optimize only for what the user said once if behavior repeatedly proves otherwise
- act as a passive archive when enough context exists to guide action

## Truth Layers

This is the most important architectural rule in the system.

### Layer 1: Observed Truth

Explicitly reported or directly extractable facts.

Examples:

- sleep hours
- body weight
- mood score the user actually stated
- task completion
- workout duration
- exact journal text

Requirements:

- immutable source linkage
- high trust
- used for retrieval, metrics, summaries, and analysis

### Layer 2: Inferred Signals

Short-horizon interpretations derived from language, timing, context, and
recent behavior.

Examples:

- user seems flat, rushed, avoidant, agitated, foggy, or motivated
- user may be resisting a known task
- morning tone suggests low energy before any numeric check-in is completed

Requirements:

- confidence-based
- explicitly marked as inferred
- never written into factual metric fields
- may be ephemeral or stored separately with evidence and expiry

### Layer 3: Pattern Claims

Repeated evidence-backed interpretations about behavior.

Examples:

- low sleep is followed by lower mood
- late training reduces next-day adherence
- verbal declarations spike before avoidance periods

Requirements:

- evidence-backed
- traceable to observed truth
- user-reviewable
- promotable to operational use only after validation

### Layer 4: Guidance Rules

Validated patterns or explicit user preferences that can shape planning and
interventions.

Examples:

- if sleep < 6h, reduce plan intensity
- ask for one realistic commitment when avoidance pattern appears
- do not schedule complex work before the user's typical activation window

Requirements:

- sourced from validated patterns or explicit user preference
- clearly reversible
- never hidden from the user

## The Desired CLI Experience

The CLI should feel like entering an ongoing relationship, not issuing commands.

The user should be able to type:

```text
hey
```

and receive a response that opens the most relevant thread for that moment.

That response should not default to generic friendliness. It should decide what
is most useful based on:

- time of day
- last check-in status
- recent adherence
- unresolved commitments
- active goals
- current drift signals
- recent emotional or behavioral context

### Example Opening Behaviors

Morning with no check-in:

- greet briefly
- ask the highest-value question first
- prefer picture-painting questions over a rigid form when possible

Morning after poor recent adherence:

- open with a grounding question or one specific accountability thread
- avoid dumping a full checklist immediately

After clear low-energy language:

- lightly reflect the tone if it may unlock honesty
- otherwise proceed with the most useful check-in thread and gather stronger evidence

After repeated goal drift:

- surface the discrepancy directly
- ask for a real commitment, not another abstract intention

## Orchestration Model

The companion should decide what to do next before it decides what to say.

### Primary Modes

1. intake
2. clarify
3. reflect
4. guide
5. commit
6. review

### Mode Definitions

`intake`

- collect current state
- prioritize missing high-value information

`clarify`

- resolve ambiguity in observations or inferred signals
- ask the smallest useful follow-up

`reflect`

- name a likely pattern, tension, or state
- surface it carefully when it may help the user respond honestly

`guide`

- propose the most useful next move for the day
- use heuristics, constraints, and active goals

`commit`

- convert vague intention into an explicit plan or promise
- track whether follow-through actually occurs

`review`

- summarize evidence across a broader window
- revisit pattern claims and alignment drift

### Orchestration Inputs

The mode selector should consider:

- current time window
- whether today's check-in is complete
- recent message tone
- recent task adherence
- active goals and top priorities
- open loops
- recent insights and heuristics
- continuity gaps
- recent commitments without follow-through

### Orchestration Output

At any moment the companion should choose:

- current mode
- highest-priority thread
- whether to infer explicitly or implicitly
- whether to ask, reflect, summarize, or guide

## Inference Rules

Inferences are allowed because they make the system feel observant, but they
must remain operationally disciplined.

### Good Uses Of Inference

- to ask a better next question
- to unlock a more honest response
- to identify likely friction early
- to personalize tone and pacing

### Bad Uses Of Inference

- turning tone into stored metrics
- using weak guesses in quantitative summaries
- escalating soft reads into identity claims

### Inference Output Types

Suggested internal signals:

- `tone_read`
- `activation_level`
- `avoidance_signal`
- `stress_signal`
- `commitment_risk`

Each signal should include:

- `signal_type`
- `confidence`
- `evidence`
- `created_at`
- `expires_at`
- `source_message_id`

## Discrepancy And Alignment Engine

One of the system's core jobs is detecting when declared intention and lived
behavior diverge.

This should be treated as first-class product behavior, not a side note.

### What Counts As A Discrepancy

- repeated verbal commitments without execution
- repeated stated goals with no linked task movement
- recurrent regret around the same behavior without changed action
- repeated behavior that contradicts a declared priority

### Desired System Behavior

When discrepancy is detected, the system should:

- name it clearly
- avoid moralizing
- help the user define the pattern in their own language
- ask for a concrete commitment sized to the user's actual behavior

### Example

Not:

- "You should work harder on your goal."

Instead:

- "You've declared this goal several times without follow-through. Do you want
  to shrink the commitment, change the plan, or admit it is not a real priority
  right now?"

### Proposed Derived Objects

`CommitmentRecord`

- an explicit verbal or written commitment made by the user
- includes source, intended time horizon, and eventual outcome

`AlignmentTension`

- a detected mismatch between declared desire and observed behavior
- includes evidence on both sides

`FrictionHypothesis`

- a ranked, revisable guess about why a pattern keeps recurring
- examples: fatigue, ambiguity, avoidance, schedule mismatch, overcommitment

These should remain separate from `DailyCheckin`, `Task`, and `Goal`.

## Desire Alignment Model

The companion should not blindly optimize for the latest stated goal.

It should estimate deeper priorities from repeated evidence.

### Signals Of Deep Desire

- explicitly repeated goals over time
- behaviors the user repeatedly returns to after lapses
- emotionally charged regret about neglected domains
- activities done voluntarily and consistently without prompting
- areas where the user tolerates discomfort because they matter

### Priority Ranking

Priority should be estimated from a blend of:

- stated importance
- repeated follow-through
- repeated re-commitment
- emotional salience
- time investment

If behavior and language conflict, MemoryChain should surface the mismatch and
help the user decide what is actually true.

## Why Analysis

The system should aim to understand the likely "why" behind recurring patterns,
but it must do so as hypothesis formation, not diagnosis.

### Good "Why" Questions

- what condition tends to precede this behavior?
- what friction repeatedly blocks follow-through?
- what environment or timing pattern predicts success?
- what belief, fear, or workload pattern appears alongside the drift?

### Output Shape

The system should rank hypotheses and ask the best clarifying question, not
pretend certainty.

Example:

- "This tends to happen after low-sleep days and overloaded task lists. Does it
  feel more like fatigue or avoidance?"

## Daily Guidance Loop

MemoryChain should be an operational guidance bot, not just a reflection tool.

### Ideal Loop

1. open the relevant thread
2. capture current state
3. identify constraints and signals
4. reconcile against active goals and real behavior
5. propose a realistic plan
6. secure explicit commitment
7. measure follow-through later

### Guidance Principles

- guidance should be grounded in observed truth first
- heuristics may shape intensity, sequence, and reminders
- plans should be sized to demonstrated capacity
- when drift is high, prefer realism over ambition

### Proposed Output

`GuidancePlan`

- date
- context snapshot
- top priorities
- recommended actions
- risk flags
- linked heuristics
- linked commitments

This can start as generated output without a table, then become a stored object
once the behavior is stable.

## Memory Context Requirements

The companion needs richer context than the current chat layer provides.

Minimum context snapshot should include:

- local time and phase of day
- today's check-in completeness
- last 3-7 days of sleep, mood, and energy trends
- open tasks and stale commitments
- active goals ranked by recent relevance
- recent insights and active heuristics
- continuity/adherence state
- most relevant inferred signals
- current alignment tensions

This context should be assembled deterministically before any LLM phrasing step.

## Accuracy Rules

Accuracy is a hard requirement, especially for metrics.

### Non-Negotiables

- no inferred numeric values in metric fields
- no silent correction of user-entered metrics
- no summary claim without observable evidence
- every derived claim should point back to supporting observations

### Retrieval Rules

When answering questions about history, the system should prefer:

- dates
- counts
- exact values
- explicit uncertainty when data is sparse

### Correction Rules

If the user corrects a fact:

- the corrected value becomes the current authored truth
- downstream derived objects should be marked stale or recalculable
- the correction trail should remain auditable

## Interface Principles For The CLI

The CLI should feel persistent and alive, but not noisy.

### Desired Traits

- opens relevant threads quickly
- asks one strong question at a time
- avoids generic filler
- references continuity naturally
- makes initiative feel earned by evidence

### Not Desired

- dumping dashboards in response to casual openings
- interrogating the user with rigid forms unless needed
- vague encouragement without operational value

## Implementation Path From The Current Repo

The current repo already has useful primitives:

- chat routing
- extraction
- questionnaires
- prompt cycles and engagement tracking
- insights and heuristics
- weekly reviews
- audit logs

The missing layer is orchestration plus stricter distinction between facts,
inferences, tensions, and guidance.

### Phase 1: Companion Orchestrator

Add a deterministic orchestration layer ahead of reply generation.

Target additions:

- `services/context_snapshot.py`
- `services/companion_orchestrator.py`
- richer `ChatResponse` metadata for chosen mode and active thread

Responsibilities:

- build full context snapshot
- choose mode
- choose highest-priority thread
- decide whether to ask, reflect, or guide

### Phase 2: Inferred Signal Layer

Add a provisional interpretation layer.

Target additions:

- `InferredSignal` schema or equivalent internal model
- tone and activation inference service
- expiry and confidence rules

Important rule:

- inferred signals never write into factual metric tables

### Phase 3: Commitment And Tension Tracking

Add explicit tracking for declared plans and behavioral mismatch.

Target additions:

- `CommitmentRecord`
- `AlignmentTension`
- discrepancy detection service

Responsibilities:

- detect repeated declarations without follow-through
- detect goal drift
- surface tension in review and guidance flows

### Phase 4: Why Engine

Add lightweight friction analysis.

Target additions:

- `FrictionHypothesis`
- ranked cause analysis using observed patterns
- clarification prompts that reduce uncertainty

Important rule:

- hypotheses are revisable and evidence-linked

### Phase 5: Daily Guidance Plans

Generate evidence-backed plans from current state and validated heuristics.

Target additions:

- `GuidancePlan` generator
- commitment follow-up loop
- review integration showing plan adherence

### Phase 6: Web Shell

Only after the CLI companion loop feels real:

- build a thin web shell around the same orchestration layer
- keep logic in backend services, not the UI

## Definition Of Success

MemoryChain will feel like the intended companion when the following are true:

- the user can type `hey` and get a context-aware opening, not a generic reply
- the system protects factual accuracy while still making useful inferences
- the system notices recurring drift and names it clearly
- the system helps the user define their own patterns and vocabulary
- the system proposes realistic plans shaped by evidence and validated priorities
- continuity is obvious across days and weeks without needing manual recap

## Immediate Next Build Tasks

1. Define a deterministic `ContextSnapshot` assembled from existing repo data.
2. Add a `CompanionOrchestrator` that selects mode and active thread before reply generation.
3. Expand chat replies from simple `log/query/chat` into companion actions:
   `intake`, `clarify`, `reflect`, `guide`, `commit`, `review`.
4. Create an inference model that stores provisional signals separately from observed truth.
5. Introduce commitment and discrepancy tracking as first-class derived objects.
6. Use prompt-cycle and adherence data as real orchestration inputs, not just review data.
7. Make the morning `hey` path a flagship interaction and test it heavily.

## Final Rule

MemoryChain should help the user log life, but that is not the real goal.

The real goal is to help the user understand and shape themselves through
persistent, evidence-backed dialogue without sacrificing factual trust.
