# CN event progression development

Branch: `feat/cn-event-progress`, based on daily acceptance commit
`34d4e24a803bb6e2979cf2ab79c6fa18dbe3b483`. This feature is not merged.

The development entry is `fgoEventCycle.EventRunner(EventResourcePolicy())`.
An explicit resource policy is required. The existing GUI event API keeps its
conservative default unless its caller supplies that policy. The development
runner advances positively recognized main nodes and skips positively identified
story dialogs; it never chooses an arbitrary Free Quest.

## Resource contract

- Apples may be enabled; quartz cannot be enabled, even by configuration.
- Mixed restoration selectors authorize only an explicit apple label. Stock
  and restoration amount must be visible; unknown resource UI stops locally.
- Quartz AP restoration and quartz revival are denied. First defeat stops.
- Reward choices, buying, summoning and formal party modifications are outside
  this runner. A fixed/restricted formation must have a unique start control.
- An already-awarded login notice can only be dismissed. The gift box is not
  opened. Campaign information can only be closed when its independent title,
  ongoing/date labels and sole close button are verified, with no affirmative
  resource controls. Promotional text does not authorize exchanges.

## Shared battle lifecycle

Event battles use the existing `BattleCycle` preparation, support selection,
`Battle` AI and settlement. BOND/BOND_LEVEL_UP/MASTER_EXP/REWARDS and friend
requests keep their established positive detectors. There is no second OCR
result-click loop. The optional settlement boundary recognizes event story/map
UI; UNKNOWN alone cannot end settlement or cause a click. Ordinary farming
without that callback retains its original contract.

Formation start can positively handle event story/start-confirmation boundaries
within the preparation parent's hard deadline. The ordinary Main wait and AI
skill/card strategies are unchanged. No team selection or automatic formation
is enabled by the event subclass.

## Evidence and restart

Ledger and failure images live under the local log root's `event` directory,
outside public fixtures and CI artifacts. An intent precedes node selection;
completion is recorded only after returning to a positive event boundary.
Restart reads actual game UI. The ledger never supplies click coordinates.

Mission requirements are recorded only from explicit wording. A mission gate
without evidenced matching quest data stops for local diagnosis; it does not
invent enemy composition or farm unrelated quests. Live gates are incremental:
zero-AP map, story, one battle, three main nodes, ten nodes, then further
authorized progression. Acceptance results are recorded after actual testing.

Battle P0 remains **mitigated / awaiting longer-term observation**. Event
development does not imply permanent resolution or completed event acceptance.
