# CN AP recovery protocol (unmerged development candidate)

The reproduced result-dismissal timeout is a missing `MASTER_LEVEL_UP`
producer. It is not evidence of an apple failure. Master-level overlays now
require the independent battle-result title, level-up banner, master-level
label and tap-to-continue footer, at the existing .85 OCR threshold. An
unconfirmed level-up foreground cannot fall through to background MASTER_EXP.
The generic settlement loop advances once and waits for a different page.

## Current implementation status

**Not production-ready.** `confirmation()` deliberately returns no positive
match because no genuine current confirmation screen has been captured.
`CONFIRMATION_PRODUCER_READY=False` prevents even resource selection on the
live CN path with a positive budget. It must stay false until the missing
producer and actual restoration acceptance are completed. Zero-budget and
forbidden-resource guards remain active. The remainder describes the bounded
protocol and its synthetic tests, not verified live apple consumption.

## Recovery contract

Non-CN retains the legacy implementation. CN validates explicit gold, silver,
bronze or copper; the fifth resource is forbidden in both GUI and core, even
with zero budget. Existing fifth-resource configuration is retained and blocked;
it is never silently converted to gold. The GUI disables this option on CN.

CN recovery requires the positively identified AP resource panel, a unique
resource-name proposal, two independent local OCR reads, positive inventory,
and a stable position in a second fresh capture. Scrolling is bounded and
occurs only inside the verified panel. One selection is permitted. A resource-
specific confirmation must be positively proven on fresh captures before one
confirmation input. A positive post-recovery state is required before decreasing
the budget. Returning to the quest list also requires a numeric AP increase.
Support/formation can deduct quest AP immediately; state departure is therefore
not rejected merely because its AP is lower than before the restoration.

AP numbers are read only with their independent fixed caption. Unavailable
numbers are reported as unknown. Uncertain resource selection/confirmation
leaves the budget unchanged and prevents another automatic attempt by any
runner using the same device in that process. Review the game state manually
before restarting automation. The recovery code never retries spending.

Zero budget performs no restoration input and stops with `Ap Empty`.
No resource optimizer, quartz, revival, APK/data/network modification or
changes to battle AI, Event WIP, daily indexing or drops are included.

## Acceptance

PENDING: actual confirmation producer, natural AP_EMPTY trial, one gold
consumption and the post-restoration battle. A normal resource-selection
panel is not claimed as proof of naturally exhausted AP. User's revised
live budget is at most eight total entries, including the restored battle.
Current half-AP campaign and master-level refills can make that gate
unreachable within the authorized budget; do not merge/archive in that case.

Private raw screenshots and traces remain local. Public tests use synthetic
fixed labels and structural resource-row fixtures.


## 2026-10-08 acceptance boundary

Three daily extreme wins, zero defeats, Fused and FlowTimeout. A natural
MASTER_LEVEL_UP on the third battle was positively detected and advanced
exactly once, with subsequent settlement and stable quest-list return.
The campaign costs 20 AP per entry. A master-level refill prevented natural
AP exhaustion within the revised maximum of eight entries, including the
post-recovery battle; testing stopped after three entries.

The normal AP-plus panel matched the old AP template at its unchanged .05
threshold and independently confirmed the fixed selector labels. This is
**not** a natural AP_EMPTY acceptance. Selecting gold while AP was full showed
an AP-full refusal, not a resource confirmation; it was closed without spending.
Neither sample is used as a fake confirmation fixture.

Pending: real insufficient-AP capture; actual resource-specific confirmation
producer and negative cases; exactly one authorized gold restoration with
verified budget 1->0; one post-restoration battle; full tests and branch CI;
then conditional merge, clean portable rebuild and a new immutable r2 archive.
The old snapshot and deployment remain unchanged. Do not infer runtime safety
across process restarts from the in-memory uncertain-attempt latch; after any
uncertain input, inspect the game manually before restarting automation.


Offline validation for this unmerged follow-up: **670 cases, 667 passed and
three existing local-integration skips**. Compileall, whitespace checks and
baseline AI strategy AST preservation pass. Branch CI is checked separately;
these offline results do not complete the missing real AP recovery gate.
