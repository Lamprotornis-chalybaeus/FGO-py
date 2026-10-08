# Intermittent stop during repeated farming

Priority: **P0**. Current status: **mitigated / awaiting longer-term observation**. Not proven permanently fixed.

The open/unverified statements below are retained historical development snapshots; the dated successful-gate and final-review acceptance section at the end is authoritative.

## Observed

- Repeated farming can stop after one or more successful battles.
- GUI may show `Script Stopped` / `Fused`.
- Occurrence is intermittent.
- A saved transition frame has shown the continuous-battle confirmation while later processing attempted to acquire battle state.

## Known good within previous tested cases

- A battle can complete.
- Daily-quest and Free Quest navigation can work.
- AP parsing and completed-battle progress accounting can work.
- These are case-specific observations, not universal reliability guarantees.

## Suspected area

Post-battle transition → battle continue → friend selection → formation transition → next battle state acquisition.

## Historical uncertainty (superseded by the latest gate)

Do not blame OCR, item recognition, network behavior or device input without evidence. Item recognition is removed from the current version. Existing evidence does not identify the exact failure point, and the issue remains open.

## Historical state-machine branch validation (2026-10-03; superseded)

`fix/battle-cycle-state-machine` is based on `add17a8a58f0315e91b695b25693c42431a61424` and is not merged into `cn-dev`. The refactor addresses the confirmed initial/repeat asymmetry, count-before-start behavior, busy waits, guardian input and GUI lifecycle races. These structural repairs do not prove every historical Fused cause.

The single-stage live trial stopped before any AI turn: an initial normalization refusal, then a support-departure timeout (CN first-row header input; fixed with a verified card-body input and failing/passing regression), then `FORMATION -> TURN_BEGIN` timeout at 90.20 seconds. A subsequent read-only probe positively detected TURN_BEGIN with the existing attack template (score 0.0028; threshold remains 0.05). The missing evidence during the timeout prevents attributing that case to OCR, device capture, background rendering or server delay.

A quest had actually been entered even though the worker's `startedBattles` remained zero because it never confirmed TURN_BEGIN within its deadline. No terminal result was confirmed. Five- and ten-battle stages were not run. **P0 remains open; not mitigated yet.** No threshold increase, extra sleeps, blind retry or catch-and-continue was introduced. Next live validation must account for the already-entered unfinished battle, obtain explicit continuation approval, and retain the bounded test budget.

See [BATTLE-CYCLE.md](BATTLE-CYCLE.md) for state/counter semantics and guards. Private traces/screenshots remain local.

## Next reproduction should capture locally

- Timestamp and current page classifier.
- Screenshot/state hash, with any raw screenshot retained locally only.
- `isBattleContinue`, `isChooseFriend`, `isBattleFormation`, `isTurnBegin`.
- Last device input and elapsed time per transition.

Do not attach private screenshots, game/account data, configuration, support templates, credentials or raw logs to a public issue. Publish only a sanitized description and minimal state trace after review.

# CN event progression / restricted formation support

Priority: P1. Event-specific formation requirements and a general Mission solver remain incomplete. Distinguish supported generic navigation from unsupported event mechanics; do not report an unsupported path as verified.

# CN navigation normalization coverage

Priority: P1. New page identities can appear. Extend coverage using verified page titles and return controls, while preserving refusal of battle, purchase, AP recovery, story and reward-choice modals. Complete daily scanning remains comparatively slow.

## 2026-10-04 daily directory entry search repair

The real CN Gate directory showed three costume quests before the Daily entry. The former upward-only search stopped at the top although the entry was below the visible cards. Search now reverses downward once after two observed scrollbar endpoints confirm the top; a stationary mid-list drag does not authorize reversal. Exact unique entry text and foreground guards remain required; duplicate entries, modals, an unverified boundary, the bottom without a match, or the finite search budget stop without selecting a quest.

Eight new offline regressions preserve these guards. The complete suite passes 464 cases (461 executed, three existing local-integration skips), including the unchanged battle AI strategy AST check. A local zero-AP navigation test started from the confirmed failing Gate-top layout, normalized to Terminal, reopened Gate, found Daily below the pinned cards and verified the daily header and three visible card titles. It did not start a quest or rerun the complete daily-list scan. Private screenshots and raw logs remain local. The battle-cycle implementation and its approved gate record are unchanged.
# Historical 2026-10-04 formation-start diagnostic follow-up (superseded)

P0 remains open. STARTING without a producer has been removed. Full-cycle physical input tracing and a narrowly scoped local formation-start capture diagnostic are implemented. Every remaining state has a tested producer; the .05 attack threshold is unchanged.

Fresh read-only observation found QUEST_READY, not the previous unfinished battle, so no replacement legacy entry was made. Strict report-only AP OCR refused a reading; visual observation was used only in the private report harness, without changing game AP policy. The independent body-touch diagnostic was explicitly authorized and reached formation with an 80ms tap. A later trial still missed support departure, so duration alone does not establish causality. A fixed-body readiness guard now precedes the one selection input.

Real formation-start evidence showed bright tips/loading and introduction frames, without a start confirmation. Captures changed normally; no long identical-frame interval required a stale-source intervention. The proven loading indicator now gates a 60-second stall / 180-second hard wait. The original historical timeout has no retained UNKNOWN capture and cannot be conclusively attributed to this page.

One diagnostic battle reached victory, but the omitted Bond result detector caused a bounded timeout. A regression first reproduced that failure. Fixed CN Bond/Master EXP labels and footer now positively identify each result page; settlement advances once per page and waits for its departure. Recovery of the existing result sequence succeeded without another entry. This diagnostic battle is not counted as the clean gate.

The subsequent clean single gate passed: started/completed/wins/defeats=1/1/1/0, with all result pages, optional friend request, CONTINUE and final QUEST_READY confirmed. The five-stage trial then completed one battle and stopped on the second support departure: CN continuous entry reused the party and bypassed FORMATION, so its FORMATION-only wait was wrong. Fresh TURN_BEGIN confirmed the second actual entry. A failing regression now covers this observed route; only a confirmed CN CONTINUE action admits direct TURN_BEGIN. Repeated live validation has not passed; ten-stage was not run and P0 remains open. No private screenshots, raw traces or logs are published.

Recovery of the already entered second battle exposed another timing error: the no-progress clock included legitimate skill/card execution. The clock now starts after completed turn inputs; its 60-second limit and the whole-battle hard deadline remain unchanged. The earlier clean-single pass predates these follow-up fixes; the final revision still needs uninterrupted clean/repeated gates before mitigation.

## 2026-10-04 successful repeated gate and final-review acceptance

P0: **mitigated / awaiting longer-term observation**. Mitigated does not mean proven permanently fixed.

The earlier completed live gate at `b5bff1e493d841ceb325eca36d660996260268cb` passed clean1, continuous5 and continuous10 on the same runtime revision: wins=16, defeats=0, Fused=0, FlowTimeout=0, consistent started/completed counters and an empty queue at each final boundary. Three initial entries used FORMATION; thirteen CN repeats went directly from FRIEND through loading to TURN_BEGIN. All sixteen used the first-support policy, not templates. A repeated FORMATION route and template/direct combination have offline coverage, not a claim of live coverage.

Earlier development failures remain historical evidence: support timeout; formation/start timeout; result-page timeout; continuous-route timeout; and bond-level-up timeout. The original start timeout lacks an interval screenshot and cannot be attributed conclusively. Recovery of an already entered battle/result is not a clean gate. No historical failure is erased by the successful run.

Final-review hardening adds two fresh outer UNKNOWN observations before turn rearm (LOADING may rearm immediately) and three stable captures of a distinct CN BOND_LEVEL_UP instance before advancing it once. A small local foreground-mask difference is ignored as raster jitter. Persistent or indistinguishable overlays fail closed. No OCR/ATTACK threshold or AI card/skill strategy is relaxed. Capture sequence proves another reader acquisition, not that JAVACAP can never return stale pixels. Instance features stay in memory and are not logged or published.

Offline validation: 456 cases, 453 executed successfully and the original three integration skips; original 436 cases retained. Compileall, diff whitespace check and baseline AI strategy AST preservation pass. Raw frames, private templates, traces and local integration data are excluded from Git and CI artifacts.

**Latest candidate code HEAD `f28705f9aefac3bf318f5525ef4c07e81b0f116b` completed and passed the fresh post-hardening gate: clean1 PASS, continuous5 PASS, continuous10 PASS.** Latest sixteen battles: wins=16, defeats=0, Fused=0, FlowTimeout=0, duplicate turn=0; started/completed statistics agree and each queue ends empty. Template zero-AP smoke PASS: a real existing private template was confirmed in three fresh frames, followed by one 80ms touch reaching FORMATION, then a safe return without starting a quest. AP change was zero. Three initial entries used FORMATION and thirteen CN repeats took the direct route. This latest gate supersedes the earlier pending acceptance requirement. Repeated bond-level-up instances and the template/direct-route combination remain offline-only coverage. The operator's local report retains the exact revision and per-battle transitions; private images, templates and raw traces are not published.

The battle-cycle state machine was merged into `cn-dev` by fast-forward to `5e6b212c6b28f801f9836f80b5bebb4f68a47fea`. The fix branch is retained; master remains unchanged. This follow-up changes Markdown only. Zero apples, quartz, AP recovery and revival are required. A failed stage stops later stages. Longer-term stability remains under observation.


## 2026-10-07 archive acceptance (current; earlier snapshots are historical)

Battle progress candidate `5604635e2f41689ab438be1447b7b8551c34f95d` passed a fresh clean single battle and five
uninterrupted repeated Fuyuki X-C battles. The user explicitly cancelled the
ten-battle stage for this round; it is not reported as tested. Both gates used
the existing party and first-support policy, with no fruit, quartz, AP item or
revival. Final gate counters: started=6, completed=6, wins=6, defeats=0;
Fused=0, FlowTimeout=0, duplicate outer AI turns=0. Each stage returned to a
positively recognized quest list. Queue/counter invariants also pass offline.

P0: **mitigated / awaiting longer-term observation**, not permanently fixed.
Historical support, formation/start, result, continuous-route, bond-overlay and
animation-watchdog failures remain relevant evidence and are retained above.

The old battle watchdog counted from completed turn inputs even through real
animation/loading progress. `BattleProgressTracker` now separates a 60-second
no-progress stall from a 180-second phase hard bound and the unchanged
30-minute battle hard bound. Fresh state changes, positively gated loading
signatures and meaningful sampled battlefield motion renew only the stall
clock. Pixel noise, repeated acquisitions and background motion cannot extend
the phase hard bound. Existing outer turn-episode rearm and AI strategy are
preserved. Failure diagnostics identify the current turn, phase, last positive
state and last physical input; sampled pixels/signatures stay in memory.

A recovered already-entered daily battle won, then exposed a separate 20-second
post-friend sub-wait. Actual quest-list return loading took approximately
24 seconds. The fix allows one dismissal and a bounded 30-second stall / up to
45-second wait, always capped by the existing 60-second settlement parent.
Persistent loading still stops. No input retry was added.

An ensuing daily integration battle won but exposed a clipped CN bond-level-up
label/footer, which the observer classified UNKNOWN until its bounded stall.
The result-only follow-up `c5a19a53ff13e39e5c71e9ae2d7dcaf419b95ca7` adds four fixed-label context proofs at the
unchanged .85 threshold. Local static evidence, synthetic positive/negative
regressions, recovery of that existing result and fresh daily smoke validate
this additional path. The six X-C gates above predate this narrow detector
follow-up; battle AI/tracker/turn-rearm code did not change afterwards.

Offline acceptance: **626 cases, 623 passed and 3 existing local-integration
skips**; compileall, whitespace checks and AI strategy AST preservation pass.
Source integration smoke located one indexed daily quest and completed one
battle/result/return without AP restoration. Candidate portable self-check
passed with frozen GUI subsystem, zero battles and zero device operations.
Private raw evidence is excluded from Git, CI artifacts and release assets.

## 2026-10-08 Master Level Up follow-up / AP recovery pending

Development branch: `fix/cn-master-level-ap-recovery`, based on archived
`cn-dev` `ff57402723d58bf3c002858f6f42ff63794ed906`. This follow-up is not
merged or deployed as an r2 snapshot. The previous snapshot remains immutable.

The newly reproduced settlement timeout was a missing CN `MASTER_LEVEL_UP`
producer, not an apple failure. Four independent fixed OCR labels (battle
result, level-up banner, master level and tap-to-continue footer) are required
at the unchanged .85 confidence floor. The foreground overlay takes priority
over background MASTER_EXP. Settlement advances it once and waits read-only
for departure; no fixed result ordering or repeated dismissal is introduced.

Three fresh daily extreme battles won with no defeat, Fused or FlowTimeout.
The third naturally displayed MASTER_LEVEL_UP; its positive producer, one
80ms result-next input and successful remaining settlement were confirmed
in the local trace. The initial user-supplied overlay had already been
dismissed before this work, so it was not claimed as an existing-result rescue.
The detector code is identical across these three runtime revisions.

AP recovery is a separate **incomplete, fail-closed candidate**. CN resource
identity, bounded protocol, success-only budget decrement, old-config handling
and GUI/core fifth-resource blocking have synthetic regression coverage.
The real confirmation producer is not implemented. An explicit disabled
capability guard stops before any selection or spending until it is supplied
from actual evidence. Mocked recovery success is not real resource acceptance.
Non-CN retains its legacy path. See [AP-RECOVERY.md](AP-RECOVERY.md).

The current extreme quest costs 20 AP during the half-AP campaign. A natural
master-level refill made genuine AP exhaustion unreachable within the user's
revised maximum of eight total entries, including the restored battle. Live
testing stopped after three entries as instructed. Natural AP_EMPTY, one gold
consumption, budget 1->0 and the restored battle remain **NOT RUN**. Merge,
formal portable replacement and the r2 tag/release are withheld. No apples,
quartz, restoration items or revival resources were used by this automation.
Private screenshots/traces remain local; public tests contain synthetic data.
Event WIP, daily indexed navigation, AI strategy and drop removal are unchanged.


Offline validation for this unmerged follow-up: **670 cases, 667 passed and
three existing local-integration skips**. Compileall, whitespace checks and
baseline AI strategy AST preservation pass. Branch CI is checked separately;
these offline results do not complete the missing real AP recovery gate.
