# Battle cycle audit (before logic changes)

Baseline: add17a8a58f0315e91b695b25693c42431a61424. Dedicated branch: fix/battle-cycle-state-machine.

## Confirmed control-flow asymmetry

In fgoKernel.Main.__call__, first entry follows quest -> chooseFriend -> wait for battleFormation -> team/autoFormation handling -> perform(' M ') -> Battle. Repeated entry follows battleContinue -> chooseFriend -> schedule.sleep(6) -> Battle. chooseFriend permits return when battleFormation is detected, and first-slot selection also returns immediately after an input. Therefore CONTINUE -> FRIEND -> FORMATION -> return -> sleep(6) -> Battle on the formation screen is a possible failure chain. This is structural evidence, not proof that every historical Fused incident has this cause.

## Counters and settlement

battleCount increases before Battle has confirmed TURN_BEGIN. completedAttempts separately counts terminal outcomes, including an immediate-stop defeat. Some callers/averages/Operation queue arithmetic still use battleCount, while GUI adapters partly use completedAttempts. Battle result handling blindly performs ten spaces before checking stopLater. Settlement and repeat preparation need one explicit state-driven path and stable completion boundaries.

## Unbounded waits / Fuse

Battle.__call__ has while True without wall-clock deadline. ClassicTurn.dispatchSkill, ClassicTurn order change, Turn.castServantSkill and Turn.castMasterSkill busy-spin on isTurnBegin. Their exits depend on Fuse or detector/schedule exceptions. Fuse increments per Detect construction, and any successful _compare/_find resets it. It is not elapsed wall time: long valid animations can accumulate counts; a wrong screen matching an unrelated template can keep resetting it indefinitely. Fuse must remain a last-resort safeguard, never the state timeout mechanism.

## Ownership / GUI lifecycle

Guardian reads the shared detector cache and directly presses K on a network error, outside the Kernel operation mutex. Android input mutex serializes individual calls, not logical ownership. Farming uses the Kernel mutex, but GUI navigation adapters can execute outside that mutex. GUI runFunc sets no immediate active guard before starting its Thread; queued funcBegin disables controls later. askQuit performs unbounded worker.join and disconnects completion before knowing that shutdown succeeded.

## Scope / prerequisites

No AI card-selection or skill-strategy changes; no AP/fruit policy changes; no new daily/event/drop/GUI features. Existing CN dialog template remains. All offline tests must pass before any live input. Live stages are strictly X-C 1, then 5, then 10; zero fruit/quartz/AP recovery. Failures stop the current stage and retain diagnostics locally. Unknown/login-sensitive frames must not be persisted without a positively identified safe game state.

Git fetch origin/upstream was attempted but failed due network resets (one sandbox call also lacked the HTTPS helper). Official GitHub API independently confirmed origin/cn-dev=add17a8 and upstream/master=7b0cb32, identical to existing local refs. No remote histories changed. Starting worktree was clean.