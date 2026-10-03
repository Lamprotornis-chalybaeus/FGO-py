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
