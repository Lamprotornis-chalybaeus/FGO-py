# CN event progression candidate

Development branch: `feat/cn-event-progress`, based on daily acceptance merge
`34d4e24a803bb6e2979cf2ab79c6fa18dbe3b483`. This event feature is not merged
into `cn-dev`. Battle P0 remains **mitigated / awaiting longer-term observation**;
that status does not certify event mechanics or a permanent fix.

## Implemented and bounded

- Explicit event resource policy with a hard QuartzGuard. Quartz AP restoration,
  quartz revival and resource confirmation ambiguity stop without confirmation.
- Current CN story skip controls and Yes/No confirmation require positive OCR.
  Consecutive dialogue episodes need three stable fresh observations. A completed
  skip is counted only after a positive departure, not after its input.
- Event battle preparation, AI and settlement reuse the shared BattleCycle;
  approved card/skill strategy is unchanged. Bond, Bond level-up, Master EXP,
  rewards and optional friend handling retain their existing detectors.
- Restricted-party errors override background formation/start evidence. Empty
  observed starting slots prevent start. Temporary automatic formation is a
  separate permission, disabled by default. It requires a positively isolated
  special-party offer or a restricted event settings page; normal parties are
  never automatically replaced by this path.
- The observed automatic-party review page is distinct from quest start. Its
  unique decision requires three stable proofs and one input, followed by a
  bounded wait for the confirmation header and start control. No click retries.
- Old fading maps cannot count nodes. A completed story/battle and three fresh
  positive map/HUD captures are required. Restart observes the actual UI;
  private ledger entries never supply blind click coordinates.

## Evidence and remaining gates

The zero-AP event-map smoke passed. Subsequent development encountered omitted
story controls, a different skip confirmation, consecutive story segments,
special-party prompts, insufficient starting members, and a distinct temporary
party review page. These are retained historical diagnostics, not successful
main-node gates. Each repair has synthetic regressions; private raw frames and
trace files are not published or included in CI artifacts.

The current offline suite passes 688 cases, with the original three explicitly
local integration skips. Full event battle, three-node and ten-node acceptance
must be reported from actual local runs. A general Mission-to-Free-Quest mapping,
real AP-item selector validation remain incomplete. Completed non-choice Mission claims have initial live evidence,
but their broader repeated coverage remains incomplete.
An unsupported mission condition stops with local evidence rather than inventing
a quest. The operator report contains exact revisions, corrected node counts,
resources and current live outcome.

Capture connection resets and an exhausted stream now stop with a specific
event capture error and unconfirmed outcome statistics. They never authorize
automatic capture-service restarts or another game input. One development run
was interrupted while an independent probe used a different ADB server version;
it cannot be accepted as a clean event battle gate. Subsequent local probes use
the exact worker ADB executable. This diagnostic interference is distinct from
a proven battle detector or AI failure.

The first event victory reached BOND, then stopped because decoration in the
Master EXP heading contaminated OCR. The existing result header/footer and two
independent fixed body labels now prove Master EXP without lowering thresholds.
Recovery of an already won result sequence has a separate settlement-resume
counter; it cannot count another battle entry. That interrupted/recovered first
node is diagnostic evidence, not a clean full-node gate.

The completion receipt is identified independently from Mission conditions.
Awarded quartz is not quartz consumption; only its proved dismissal control
may be pressed. The observed world map alternates its counter with currencies
and bounces the next-area marker. Navigation requires three fresh stable
marker/area proofs and a single area touch. Numbered 話/话 cards are supported.
The prologue was recovered to the world map with one actual entry and one win;
it remains diagnostic evidence, not an uninterrupted clean acceptance gate.

Transient UNKNOWN frames during decorated-card confirmation reset the positive
count and permit only bounded rereading. A missing title never authorizes a
selection. The actual story-only start confirmation uses 是否开始任务/任务开始
and has its own joint producer, including a two-scale cancel check.


## Observed reward and Mission UI follow-up

The first story-only episode was completed through recovery, including two
already awarded CE cards, their information pages, instructional pages and one
completed Mission reward. The Mission counter changed from 0/100 to 1/100;
receiving an apple is not consuming an apple. These interrupted diagnostic runs
are not the uninterrupted story, battle, three-node or ten-node gates.

Each automatic receipt, item-information close, tutorial advance and numbered
completed Mission claim has independent structural proof, three fresh stable
observations and one input. Embedded tutorial screenshots never authorize
claims. The observed post-claim unlock tutorial has a separate producer from
main-quest Mission requirements. Partial Mission-list anchors permit only
bounded rereading: locked background rows cannot become a foreground blocker,
and partial evidence cannot authorize a claim or return input.

Raw images, original OCR logs, CE features and local ledgers remain private.
Mission-to-Free-Quest mapping and real AP-item selection still require evidence.


A real ledger destination lock interrupted one development selection. Only the
atomic file replacement now has five bounded PermissionError attempts (under a
second total); persistent failure retains the previous ledger and pending file.
Game inputs are never replayed by this retry. Input intent is persisted before
the single physical touch, preventing a failed pre-input log write from touching
the device. Short observed dialogue in the lower text panel is recognized with
independent skip/auto proof; upper captions cannot substitute for dialogue.


Observed post-story temporary-servant receipt, passive join explanation and
servant information tabs now have distinct positive structural proofs. No
servant identity is used to choose an action. Information pages permit only
closing; inventory/lock/mark/enhancement controls are untouched. A Mission
receipt may lead to the observed unlock tutorial; its close still requires a
three-frame real counter increment under the same bounded parent deadline.
The second story-only episode returned to a positive map through recovery with
no new battle entry and unchanged AP. It is not a clean story gate.
