# CN daily scrollbar index (review branch)

Development branch: `feat/daily-indexed-scan`, based on `05ba7ff` (the daily-entry fix after the requested `c25b140` baseline). This feature has not been merged into `cn-dev`.

## Scan contract

One forward overlapping pass records real title/AP observations and the scrollbar thumb. After at least five overlap samples from three distinct tasks, a filtered median calibrates content displacement. Freshly checked cached calibration permits bounded warm-start movements; cached observations never verify entries. The last actual visible title anchors subsequent bounded forward movements, avoiding inertial jumps. There is no normal reverse pass or whole-list omission rescan.

Title consensus always consults the third grayscale context. A valid grayscale disagreement with a two-color pair triggers two further bounded contexts; unresolved ties or an unsupported color-only pair are rejected. Scores are unchanged and no glyph is repaired from quest/class names.

The accumulator keeps title observations, actual frame order, thumb geometry, overlap edges, unresolved AP rows, absolute positions and median card pitch. Independent confirmation requires fresh frames at different thumb positions and a meaningful thumb or local-title displacement. Top/bottom exceptions require a fresh targeted edge observation. The required final direct return to the top supplies the top-edge recheck, without an additional early trip. A low-position group may also be rechecked on that final journey, but still requires ordinary independent-position evidence, not an edge waiver. Coincident OCR proposals for the same card are merged; identical titles on different cards stop unique positioning.

Gaps produce numeric position candidates, never inferred names. Local title crop consensus and that card's AP must read the actual title. Real title/AP anchors supply the measured card pitch for local leading/trailing/gap proposals. Each proposed slot requires its own Latin AP read and full-title consensus. Insufficient anchors or failed local reads fall back to independent narrow AP-column batches. A positively read AP whose title remains unreadable stops publication. AP-led local recovery also applies during targeted checks. An unreadable title is never filled from the index. Conflicting title aliases are resolved only when fresh positional rechecks leave exactly one independently confirmed title. Conflicts are checked again when targeted observations reveal a real title alongside a previous single-frame alias. Only one independently verified title may survive at a slot. Competing confirmed titles, unresolved gaps, ambiguous scrollbars or page changes prevent publishing a complete list.

## Locate contract

The local index is advisory. A guarded scrollbar jump moves near the target, followed by local OCR and at most two content micro-alignments. A second fresh title/AP confirmation returns `DailyQuestReady`; this function never selects the quest.

If the target fails, before/after anchors identify the physical slot. A confirmed anchor with an unreadable target stops safely. Controlled sequential search is only the last fallback for unusable geometry/calibration or missing anchors. A successful fallback stores its real thumb/local position so later queue requests reuse it. Queue order is unchanged.

A generic balanced bracket annotation immediately before `每日替换` is treated as a campaign display prefix, not as part of the canonical task identity. The actual task body and difficulty still require crop consensus and own AP. No annotation/task/class names are whitelisted; brackets inside a task name or without the replacement marker remain intact. Annotated and ordinary copies on distinct cards still collide and stop unique positioning. This addresses observed compressed-line annotation OCR errors without repairing quest names from neighbors.

The CN scrollbar input uses one held Airtest drag, a bounded in-track excursion, and a held endpoint. Observed movement samples calibrate physical drag gain. Each jump allows at most two corrections. Two-pixel handle quantization is accepted, while the bottom endpoint still requires a positive bottom observation. A transient post-release scrollbar frame permits two read-only recaptures, not repeated input. All inputs require positive DAILY/foreground checks and actual scrollbar geometry.

## Cache and metrics

`fgoTemp/daily-index.json` contains only title strings and numeric geometry/observations. It is ignored by Git and contains no images, account data, support templates or credentials. Version/schema/fingerprint/geometry/order validation and fresh anchors govern reuse. Changed headers, geometry or missing anchors invalidate it. A refresh may reuse calibration after fresh top-anchor checks; cached observations never count toward new scan verification.

`DailyScanMetrics` counts screenshot acquisitions, actual OCR calls (including navigation guards), content swipes, scrollbar drags, targeted checks, gap recovery, micro-adjustments and fallback searches. Batch crops over 300 pixels high count as full OCR; narrow batches and single-line reads count as local OCR. Same immutable-frame foreground OCR is reused for title proposals; title crop consensus and AP verification remain independent. OCR instrumentation is context-local and restored on exit, including exceptions.

Private measurements and local screenshots remain outside the repository. See the local `C:\FGO-Automation\DAILY-INDEXED-SCAN.md` report for live validation. The battle loop, AI, settlement, guardian, counters and drop-recognition removal are unchanged.
