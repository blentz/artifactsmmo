# Goal/Decision graph waves 1-2 — live baseline and acceptance

Source: `~/.cache/artifactsmmo/learning.db` only. Never trace files — those are
deleted periodically and are not a durable basis for any claim.

Branch under test: `goal-decision-graph`, commits `32261b35..aaf49b7f`.

## Baseline — captured 2026-08-23T07:31:27Z, BEFORE the fleet runs this branch

DB max ts at capture: `2026-08-23T07:31:09Z`.

### Criterion 1 — `LevelSkill(weaponcrafting->N)` for N > 10

**All-time occurrences: 0.**

Every weaponcrafting grind action ever executed targeted level 10 or below:

| action | count | first | last |
|---|---|---|---|
| `LevelSkill(weaponcrafting->10)` | 11,026 | 2026-08-05T22:09 | 2026-08-20T01:33 |
| `LevelSkill(weaponcrafting->5)` | 408 | 2026-08-02T15:18 | 2026-08-05T02:56 |

Nothing since 2026-08-20T01:33. This is the frozen state the change addresses.

### Criterion 2 — weaponcrafting level per character

| character | weaponcrafting | other skills |
|---|---|---|
| C3P0 | 6 | alchemy 13, cooking 15, gearcrafting 10, mining 12, woodcutting 10 |
| HAL | 10 | alchemy 14, cooking 11, gearcrafting 9, mining 13, woodcutting 11 |
| Lor | 10 | alchemy 4, cooking 4, gearcrafting 9, mining 11, woodcutting 11 |
| R2D2 | 10 | alchemy 7, cooking 5, gearcrafting 9, mining 12, woodcutting 19 |
| Robby | 10 | alchemy 17, cooking 12, gearcrafting 15, jewelrycrafting 15, mining 21, woodcutting 20 |

Four of five are pinned at exactly 10 while other crafting and gathering skills
have moved well past it. Robby is at mining 21 and woodcutting 20 with
weaponcrafting 10.

### Criterion 3 — planner nodes per cycle (regression guard)

Window `ts > 2026-08-22T19:02`:

| character | cycles | avg nodes | max nodes |
|---|---|---|---|
| C3P0 | 647 | 189 | 7,565 |
| HAL | 646 | 473 | 6,047 |
| Lor | 637 | 4,821 | 38,773 |
| R2D2 | 604 | 1,818 | 16,154 |
| Robby | 630 | 255 | 907 |

Waves 1-2 must not make these worse. A material *reduction* is NOT expected
here — the gate-closed action set and the `LevelSkill` deletion are wave 3, so
the search space is unchanged by this branch.

### Context — fleet activity in the same window

| character | cycles | Δxp | level |
|---|---|---|---|
| C3P0 | 647 | 3,115 | 21 |
| HAL | 646 | 4,728 | 20 |
| Lor | 637 | 5,796 | 19 |
| R2D2 | 604 | 8,211 | 21 |
| Robby | 630 | 7,124 | 30 |

## Acceptance — PENDING, requires a fleet restart

None of this can be measured from the current data: the running fleet is on
`main`, not on this branch. To complete Task 7:

1. Merge or check out `goal-decision-graph` and restart the fleet on it.
2. Let it run at least 2 hours (~52 cycles/hour/character, so ~100 cycles each).
3. Re-run the same three queries and compare against the tables above.

Pass conditions:

1. `LevelSkill(weaponcrafting->N)` with N > 10 occurs **at least once**.
   Baseline is 0 and it has never happened.
2. Weaponcrafting rises above 10 on at least one character.
3. Planner nodes per cycle do not regress against the Criterion 3 table.

## Open gap this measurement exists to close

Task 5 disclosed honestly that at implementation time none of Robby, HAL, Lor
or C3P0 had an `ObtainItem` root selected — all were on `ReachCharLevel` trunks
or `RestoreHP` — so the rewired edge did not fire in a live snapshot. The fix is
evidenced by a unit test reproducing Robby's exact recorded case and by a
mutation kill, but **not** by production firing.

This repository's standing rule is that green tests are not runtime activation.
Until criterion 1 is observed, waves 1-2 are verified but not activated, and
that distinction should be stated plainly rather than rounded up.
