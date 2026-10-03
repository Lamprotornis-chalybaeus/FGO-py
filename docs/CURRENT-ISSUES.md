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
