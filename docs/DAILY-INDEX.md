# CN daily scrollbar index

Development history: `feat/daily-indexed-scan`, based on `05ba7ff` (the daily-entry fix after the requested `c25b140` baseline). Integration uses an approved fast-forward after offline, CI and zero-AP live gates; private evidence remains local.

## Scan contract

One forward overlapping pass records real title/AP observations and the scrollbar thumb. After at least five overlap samples from three distinct tasks, a filtered median calibrates content displacement. Freshly checked cached calibration permits bounded warm-start movements; cached observations never verify entries. The last actual visible title anchors subsequent bounded forward movements, avoiding inertial jumps. There is no normal reverse pass or whole-list omission rescan.

Title consensus always consults the third grayscale context. A valid grayscale disagreement with a two-color pair triggers two further bounded contexts; unresolved ties or an unsupported color-only pair are rejected. Scores are unchanged and no glyph is repaired from quest/class names.

The accumulator keeps title observations, actual frame order, thumb geometry, overlap edges, unresolved AP rows, absolute positions and median card pitch. Independent confirmation requires fresh frames at different thumb positions and a meaningful thumb or local-title displacement. Top/bottom exceptions require a fresh targeted edge observation. The required final direct return to the top supplies the top-edge recheck, without an additional early trip. A low-position group may also be rechecked on that final journey, but still requires ordinary independent-position evidence, not an edge waiver. Coincident OCR proposals for the same card are merged; identical titles on different cards stop unique positioning.

Gaps produce numeric position candidates, never inferred names. Local title crop consensus and that card's AP must read the actual title. Real title/AP anchors supply the measured card pitch for local leading/trailing/gap proposals. Each proposed slot requires its own Latin AP read and full-title consensus. Insufficient anchors or failed local reads fall back to independent narrow AP-column batches. A positively read AP whose title remains unreadable stops publication. AP-led local recovery also applies during targeted checks. An unreadable title is never filled from the index. Conflicting title aliases are resolved only when fresh positional rechecks leave exactly one independently confirmed title. Conflicts are checked again when targeted observations reveal a real title alongside a previous single-frame alias. Only one independently verified title may survive at a slot. Competing confirmed titles, unresolved gaps, ambiguous scrollbars or page changes prevent publishing a complete list.

Forward steps also follow verification progress. When a three-card view contains an unverified middle card, the next bounded step keeps it in the overlap for independent title/AP confirmation. Once that card is verified, the larger bounded step resumes. This avoids a sequence of two-card jumps leaving every middle card for a later return trip. It uses actual observations, not cached task names or inferred verification.

## Locate contract

The local index is advisory. A guarded scrollbar jump moves near the target, followed by local OCR and at most two content micro-alignments. A second fresh title/AP confirmation returns `DailyQuestReady`; this function never selects the quest.

If the target fails, before/after anchors identify the physical slot. A confirmed anchor with an unreadable target stops safely. Controlled sequential search is only the last fallback for unusable geometry/calibration or missing anchors. A successful fallback stores its real thumb/local position so later queue requests reuse it. Queue order is unchanged.

A generic balanced bracket annotation immediately before `每日替换` is treated as a campaign display prefix, not as part of the canonical task identity. The actual task body and difficulty still require crop consensus and own AP. No annotation/task/class names are whitelisted; brackets inside a task name or without the replacement marker remain intact. Annotated and ordinary copies on distinct cards still collide and stop unique positioning. This addresses observed compressed-line annotation OCR errors without repairing quest names from neighbors.

The CN scrollbar input uses one held Airtest drag, a bounded in-track excursion, and a held endpoint. Observed movement samples calibrate physical drag gain. Each jump allows at most two corrections. Two-pixel handle quantization is accepted, while the bottom endpoint still requires a positive bottom observation. A transient post-release scrollbar frame permits two read-only recaptures, not repeated input. All inputs require positive DAILY/foreground checks and actual scrollbar geometry.

Top-thumb quantization alone cannot prove the leading card is readable. Before the forward pass and at the final edge recheck, the first verified complete title/AP must occupy the leading-card band. If a near-top frame only contains later full cards, at most two positively guarded, small list-to-top inputs acquire a fresh readable leading card. Otherwise publication stops. The advisory index never supplies a missing title, and an unreadable first card cannot silently become a complete list starting at the second card.

## Cache and metrics

Page context and index validity are separate. `DailyContextError`/`dailyContextLost` stop inputs outside a jointly confirmed DAILY page and preserve the in-memory index, on-disk cache and anchors. `DailyIndexMismatch`/`invalidateIndex` are reserved for contradictory fresh structure after positive DAILY confirmation: geometry, order, or missing target/neighbor anchors. An ordinary terminal/Gate/event/menu journey is not an index mismatch.

DAILY confirmation requires 1280×720, the main-interface template, the exact header and close control, a unique scrollbar, and a real card title paired with its AP row, plus the foreground/modal guard. Header words alone are only a candidate. Navigation waits read-only for up to 25 seconds after each verified Gate/Daily tap; it never repeats a tap on UNKNOWN. The caller independently confirms DAILY before handing off to the index. Directory scrolling during metrics collection uses ROOT/GATE proof rather than a DAILY-only guard. Ordinary menu normalization uses an independently read stable header and a unique MENU control, without a menu-title allowlist; its only action is opening MENU and selecting the positively confirmed terminal.

`fgoTemp/daily-index.json` contains only title strings and numeric geometry/observations. It is ignored by Git and contains no images, account data, support templates or credentials. Version/schema/fingerprint/geometry/order validation and fresh anchors govern reuse. Only contradictory fresh structure on a positively confirmed DAILY page invalidates it. A refresh may reuse calibration after fresh top-anchor checks; cached observations never count toward new scan verification.

`DailyScanMetrics` counts screenshot acquisitions, actual OCR calls (including navigation guards), content swipes, scrollbar drags, targeted checks, gap recovery, micro-adjustments and fallback searches. Batch crops over 300 pixels high count as full OCR; narrow batches and single-line reads count as local OCR. Same immutable-frame foreground OCR is reused for title proposals; title crop consensus and AP verification remain independent. OCR instrumentation is context-local and restored on exit, including exceptions.

Private measurements and local screenshots remain outside the repository. See the local `C:\FGO-Automation\DAILY-INDEXED-SCAN.md` report for live validation. The battle loop, AI, settlement, guardian, counters and drop-recognition removal are unchanged.

## 2026-10-04 acceptance evidence

The context/leading-edge follow-up preserves the original suite and passes 580 tests, with three existing local-integration skips. Six live starting contexts (terminal, event map, friends, shop, formation menu and Free Quest) reach the same indexed target with zero sequential fallbacks, unchanged cache bytes, zero battles and unchanged AP. A fresh complete scan verifies all 75 actual titles in baseline order, with no unresolved gaps: 53 captures/full OCR calls, 715 local OCR calls, 51 scrollbar drags, one list-to-top normalization gesture and one targeted edge check.

The scan took 179.16 seconds, compared with the prior 160.45–172.72-second runs and the 245.99-second sequential baseline. The extra top-edge proof accounts for an additional acquisition/gesture; timings vary with local rendering and OCR. The earlier 74-title proposal was rejected before cache publication by the independent local accuracy gate, and its missing leading-card evidence produced a regression and the bounded top-card fix above. No cached or fabricated title supplied that missing card.
