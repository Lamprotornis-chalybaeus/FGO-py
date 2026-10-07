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
