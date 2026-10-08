# FGO-py CN Enhanced development snapshot — 2026-10-07

Upstream: [hgjazhgj/FGO-py](https://github.com/hgjazhgj/FGO-py), baseline
`7b0cb32ff8ee8207715f4ea1084c1a86b5412d1f`, version 21.1.1. License: AGPLv3.
CN development line: `cn-dev`; archive integration:
`integration/archive-2026-10-07`.

## Included

- CN GUI and local portable GUI distribution.
- Bounded navigation and shared terminal normalization.
- Daily indexed scanning, complete coverage proof and fast title/AP-verified locating.
- User-managed support templates and bounded support selection.
- Battle-cycle state machine, repeated farming and meaningful progress tracking.
- Item/drop recognition remains removed.

## Acceptance

Core gate runtime `5604635e2f41689ab438be1447b7b8551c34f95d`: clean1 PASS, continuous5 PASS; continuous10 cancelled
by the user, not run. The final candidate `c5a19a53ff13e39e5c71e9ae2d7dcaf419b95ca7` adds a narrowly scoped
bond-result detector follow-up accepted by static regression, existing-result
recovery and fresh daily/integration smokes. The core tracker/AI code remains
identical to the six core-gate battles. Six accepted core-gate wins, zero defeats/Fused/FlowTimeout/
duplicate outer turns, zero restoration or revival. Three daily refreshes,
five indexed positions, A→B→C reuse and three normalization contexts passed.
Daily integration and archive-integration single-battle smokes passed.
626 offline cases (623 passed, three existing integration skips), compileall,
whitespace and AI AST checks passed. The portable self-check operates no device.

Battle P0: **mitigated / awaiting longer-term observation**; not permanently
fixed. Daily evidence covers the current observed list and verified contexts,
not every possible future menu or campaign UI.

## Retained work

`feat/cn-event-progress` at `4d9ff5a943e1550a82cbe2330933154ae03df9b8` is WIP_KEEP and remains separate.
Earlier daily/battle and local development branches are retained for history;
no history is rewritten and no upstream ref is pushed. The snapshot tag and
prerelease identify the final archive commit on cn-dev.

Only sanitized source/tests/docs and a fresh portable payload are published.
Private logs, screenshots, templates, configuration, evidence databases,
indices, backups and environments are excluded.

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
