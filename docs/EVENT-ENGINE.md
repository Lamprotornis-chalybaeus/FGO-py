# CN event campaign engine (development)

The default objective is `CLEAR_MAIN_STORY`. Mission farming is performed only
when a freshly observed requirement blocks the next main node. Clean/recovered
outcomes are quality measurements, not prerequisites for advancing the event.

## Components

- `EventCampaignRunner` coordinates the existing `EventRunner`, Mission lookup,
  empirical candidate ranking and the shared `BattleCycle`.
- `EventQuestEntry` and `EventQuestIndex` retain event/area/title/AP, availability,
  viewport, position, neighbours and target-icon fingerprints.
- `EventQuestLocator` restores a LIST viewport and confirms three fresh
  title/AP/available observations before one selection. MAP uses an adapter
  contract with bounded panning and fresh identity proof; a real MAP adapter has
  not yet been validated in this event.
- `MissionEvidenceDB` computes deltas only for full conditions reliably present
  in both snapshots of one uniquely identified won battle. Missing cards are
  not negative samples; already capped counters cannot prove a negative.
- `MissionExperimentEngine` saves an immutable before snapshot and prior entry
  IDs before selection. Reconciliation requires a new, uniquely won entry and
  a fresh full blocking-card after snapshot; duplicate reconciliation does not
  increment samples again.
- `EventFarmTask` describes fixed runs or a specified Mission completion target.
- `EventCurrency` is an identity/value/source interface. Currency OCR and
  currency-target farming are not yet validated.
- `EventProfile` records observed structures and unsupported structures locally.

Indices are advisory. A cached location never authorizes a touch. Title OCR may
still substitute Chinese characters at high confidence. Operator-reviewed full
title patches can correct such substitutions only when a fresh pixel match,
two-scale line read, area and AP agree. Patches remain beside the private index;
their spelling corrections are not activity names hardcoded into the engine.
An entry not re-observed during a completed bounded area scan is excluded from
current candidates, while its historical identity/effects remain intact. A
fresh re-observation restores eligibility. This is not an enemy-effect negative
sample or a claim that the card can never return.

## Mission learning

Read the full blocking condition and before progress. Rank available candidates
by measured positive effect, related target fingerprint, NEW state and AP. A
title or target icon ranks a candidate; it does not prove an enemy attribute.
Run one battle and independently read after progress. Store all reliably
observed deltas, then repeat only while the blocking Mission remains incomplete.
Do not immediately repeat a negative candidate.

Snapshot coverage currently means readable cards along the bounded top/target
lookup route. It does **not** mean all 100 Missions were read. The pre-selection
baseline and prior entry IDs are saved durably before the quest input so a
diagnostic stop need not lose the experiment's provenance.

Two-scale OCR retains the original confidence threshold. Wrapped exclusions
must be complete. Joining the two actual line crops for OCR can recover a short
tail without adding condition text; both reads must agree and preserve all
words, counts and balanced exclusion parentheses.

## Resources and privacy

Public resource defaults remain apples off, quartz off and temporary automatic
formation off. The user's explicit local policy may permit apples and isolated
event formation. `QuartzGuard` remains mandatory; quartz is never an AP fallback.
Natural AP is used first. Existing item/resource selectors must independently
prove any restoration input.
Nested Mission experiments check the campaign's parent time/entry budget before
starting another selection, in addition to their own finite attempt bounds.

Private images, title patches, traces, indices, configurations, experiment
evidence and profiles stay local and are not CI artifacts. The removed drop
recognizer is not restored. The activity layer does not change skill/card AI.

## Current validation limits

The first scoped LIST index and Mission experiment have live evidence: one
AP5 win increased the blocking counter from 0/4 to 2/4. Settlement also exposed
a Master-level-up overlay and an item presentation after the reward summary;
both require their own positive producers and single bounded advancement.
One AP40 experiment reached a real seven-turn victory after a 60-second
post-card timeout during a noble animation. Its outcome is recovered; full
elapsed time is unavailable. CN event battles can now opt into wait-only
post-card activity diagnostics: actual noble selection plus two material fresh
central-frame changes renews the 60-second stall timer, with an immutable
180-second episode cap and the existing whole-battle deadline. Minor animation
background jitter, identical captures and normal-card-only turns do not renew
the stall timer. This is not a new battle state or permission for another input;
live validation of this new wait policy remains pending.
Activity completion has not been proved. LIST scrolling/index selection and
passive fixed-uniform formation notices have real observations; three-card
indexing does not imply every future event layout is supported. Continuous
repeat farming integration and recovery of every interrupted experiment remain
development items. No merge into `cn-dev` is authorized by this task.

The prior clean single/continuous acceptance requirements in older event notes
are superseded as campaign blockers by the current main-story-first task.
Historical failures and recovered outcomes remain historical evidence.


### Mission completion and post-settlement boundaries

Three actual experiments established a blocking Mission counter of 4/4:
AP5 +2, then two AP40 +1 samples. The AP40 outcomes were recovered after
long noble-animation timeouts; the newly bounded animation wait has not yet
passed a live battle. No further experimental farming is required for that gate.

Condition identity ignores ornamental quotation marks only; words, numbers
and exclusion parentheses remain mandatory. Exact completed-card claims also
require a readable pre-claim counter and three stable full-condition frames.
An obtained-item receipt can cover several background Mission headers. The
receipt does not guess a task number: closing requires the unique durable
pending claim consistent with the visible headers and counter. A weak obtained
label is re-read from its actual crop at two scales with the unchanged threshold.

Post-battle map transitions now separate bounded loading progress from generic
UNKNOWN. Proven fixed loading labels or a real dark loading frame can extend
the stall budget, with a fixed parent-capped hard deadline. Static darkness does
not repeatedly renew it. A transient terminal detector miss is revalidated
read-only before outcome recovery; no result, turn count or time is fabricated.
Fixed-until-complete farming remains bound to its measured quest, with no silent
substitution if that quest is no longer freshly available.
