# Intermittent stop during repeated farming

Priority: **P0**. Status: open; no confirmed complete fix.

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

## Not proven

Do not blame OCR, item recognition, network behavior or device input without evidence. Item recognition is removed from the current version. Existing evidence does not identify the exact failure point, and the issue remains open.

## State-machine branch validation (2026-10-03)

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
# 2026-10-04 formation-start diagnostic follow-up

P0 remains open. STARTING without a producer has been removed. Full-cycle physical input tracing and a narrowly scoped local formation-start capture diagnostic are implemented. Every remaining state has a tested producer; the .05 attack threshold is unchanged.

Fresh read-only observation found QUEST_READY, not the previous unfinished battle, so no replacement legacy entry was made. Strict report-only AP OCR refused a reading; visual observation was used only in the private report harness, without changing game AP policy. The independent body-touch diagnostic was explicitly authorized and reached formation with an 80ms tap. A later trial still missed support departure, so duration alone does not establish causality. A fixed-body readiness guard now precedes the one selection input.

Real formation-start evidence showed bright tips/loading and introduction frames, without a start confirmation. Captures changed normally; no long identical-frame interval required a stale-source intervention. The proven loading indicator now gates a 60-second stall / 180-second hard wait. The original historical timeout has no retained UNKNOWN capture and cannot be conclusively attributed to this page.

One diagnostic battle reached victory, but the omitted Bond result detector caused a bounded timeout. A regression first reproduced that failure. Fixed CN Bond/Master EXP labels and footer now positively identify each result page; settlement advances once per page and waits for its departure. Recovery of the existing result sequence succeeded without another entry. This diagnostic battle is not counted as the clean gate.

The subsequent clean single gate passed: started/completed/wins/defeats=1/1/1/0, with all result pages, optional friend request, CONTINUE and final QUEST_READY confirmed. Five/ten-stage validation is tracked separately and does not yet establish P0 mitigation. No private screenshots, raw traces or logs are published.
