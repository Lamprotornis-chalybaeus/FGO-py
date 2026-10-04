# CN development status

Status: **Development / Experimental**. Development branch: `cn-dev` on the fork; local working branch: `local/cn-gui-navigation`. Last feature baseline: `2db97ad2c90f10d88f9091b12d0b5a55c54c5c1e`. Upstream baseline: `7b0cb32ff8ee8207715f4ea1084c1a86b5412d1f` (v21.1.1).

## Implemented

- Windows GUI startup and automatic connection to a saved device.
- CN continuous-battle dialog recognition compatibility patch; this does not establish reliable repeated farming.
- Bounded CN Free Quest navigation, verified map positioning, and shared home/terminal normalization.
- Dynamic daily-quest scanning, complete-list verification and queue positioning with evidence-based neighboring-card crop recovery.
- Weekly-task feedback, live remaining battle counts, separate task and run limits.
- User-managed support templates and preference/strict/first-selection strategies.
- PyInstaller portable GUI and startup without a console window.
- Farming idle callback repair (`583e058` is in the retained history).
- Item/drop recognition, QP accounting, and their GUI have been removed from the current version.

The feature baseline passed 319 offline regressions. The repository CI separates portable tests from explicitly enabled local integration tests; see [TESTING.md](TESTING.md). Passing mocked/offline tests does not certify live repeated farming.

## Battle-cycle refactor candidate

Dedicated branch: `fix/battle-cycle-state-machine`; baseline `add17a8a58f0315e91b695b25693c42431a61424`. It is not merged into the deployment branch. Added a read-only evidence classifier, common initial/repeat preparation, monotonic phase/whole-battle deadlines, transition/physical-input trace, explicit started/completed/win/defeat counters, notification-only guardian, automation ownership, immediate GUI startup guard and bounded close wait. Queue deduction uses only completed attempts. AI card ranking is protected against baseline AST digests.

The candidate currently passes 411 offline tests (408 executed; three existing local-integration skips), compared with the 320-test repository baseline: 91 new tests. Compile/AST/import smoke also passes. A clean single-stage validation passed all preparation, battle and settlement phases before the latest follow-up fixes. The five-stage trial stopped on the second entry's observed direct-battle route; the route and no-progress-clock fixes have offline regressions but no repeated live pass. Ten-stage was not run; P0 stays open. Source/portable compatibility is verified separately from live farming; the earlier portable executable has not been rebuilt with the latest diagnostic changes. See [BATTLE-CYCLE-AUDIT.md](BATTLE-CYCLE-AUDIT.md) and [BATTLE-CYCLE.md](BATTLE-CYCLE.md).

## Known issues

### P0 — Intermittent farming transition stop / Fused

Longer repeated farming may stop after successful battles, potentially after a continuous-battle dialog. Current evidence does not establish the specific failed transition or its cause. Item recognition has been removed; this must not be described as a proven fix. A safety guard now stops unconfirmed support acquisition instead of allowing a state-loop fallthrough. Live reliability remains unverified.

### P1

- New CN menu or page titles may require additional normalization evidence.
- Complete daily-quest scanning can take several minutes.
- Event-specific restricted formations are not implemented completely.
- A general Mission solver is not implemented; current weekly-task feedback is not a general event Mission solver.

Details and the next reproduction plan: [CURRENT-ISSUES.md](CURRENT-ISSUES.md).

## Development and upstream synchronization

Keep `origin` pointed at the user's fork and `upstream` at the official repository. Preserve the full commit history. Fetch upstream, review its diff, and use a dedicated integration branch to merge changes; run portable tests and review CN recognition changes before merging into `cn-dev`. Do not force-push or automatically merge upstream changes into the deployment branch.

For a contribution upstream, create a narrowly scoped branch and review its code, templates, tests and AGPL attribution. This repository preparation does not create or submit an upstream PR.
# 2026-10-04 diagnostic follow-up

The unmerged `fix/battle-cycle-state-machine` branch traces physical inputs across preparation, Battle and settlement. Local-only formation-start capture signatures, acquisition timestamps and ATTACK scores use four bounded representative slots; UNKNOWN full frames are authorized only in that verified transition. Real loading evidence supports a stall/hard deadline; ATTACK threshold is unchanged and no guessed confirmation detector was added. STARTING was removed; all remaining enum producers are tested. CN first-support body readiness, positive Bond/Master EXP result pages, direct battle after CONTINUE and the no-progress wait after input completion have regressions. Offline suite: 411 cases, 408 executed successfully, three existing integration skips. The interrupted five-stage trial and existing-battle recovery do not establish a repeated gate or validate all latest changes live. P0 remains open.
