# Fleet audit — 2026-09-20

Scope: the live session that started 2026-09-16T23:40Z (94.7 hours, ~4,500 cycles
per character, still running at the time of the audit). Evidence is
`~/.cache/artifactsmmo/learning.db`, the live `/my/characters` API, and one
`uv run artifactsmmo plan <char>` per character. No trace files exist on disk,
so nothing here depends on them.

Fleet state at audit time:

| char  | level | xp             | last char-XP gain | cycles | non-grey winnable & reachable |
|-------|-------|----------------|-------------------|--------|-------------------------------|
| HAL   | 23    | 4,909 / 11,200 | 2026-09-20 (now)  | 4,783  | 0                             |
| R2D2  | 29    | 5,488 / 18,200 | 2026-09-13        | 4,400  | 0                             |
| C3P0  | 29    | 14 / 18,200    | 2026-09-17        | 4,595  | 0                             |
| Lor   | 30    | 8 / 19,700     | 2026-09-18        | 4,566  | 0                             |
| Robby | 30    | 18,757 / 19,700| **2026-08-25**    | 4,260  | **3** (death_knight, vampire, spider) |

---

## F1 — HAL: the equip/loadout livelock is live again, on an unguarded producer

**Severity: high. Ongoing right now.**

HAL has executed `Equip(hard_leather_pants->leg_armor_slot)` **1,464 times since
2026-09-08**, 790 of them in this session — 16.5% of HAL's cycles. The item has
never stayed on: the live API shows `leg_armor: adventurer_pants` with
`hard_leather_pants x1` still sitting in the bag.

The cycle is exactly four actions long and repeats without end:

```
OptimizeLoadout(pig)  ->  drops {"hard_leather_pants": 1}   (adventurer_pants goes on)
Fight(pig)            ->  +39 xp
Rest
Equip(hard_leather_pants->leg_armor_slot)  ->  drops {"adventurer_pants": 1}
```

The `drops_json` column records the displaced item on each leg, so the two
authorities fighting over `leg_armor_slot` are visible directly in the store.

`equipment/slot_occupancy.may_displace` is the one authority meant to prevent
this, and it answers correctly:

```
hard_leather_pants  dmg 0  dmg_el {air:10, earth:10}  res {air:6}  flat 82
adventurer_pants    dmg 5  dmg_el {}                  res {}       flat 80
may_displace(hard over adventurer) = False     # water: 0+0 < 5+0
```

The guard is applied in `goals/progression.py` at `_find_inventory_upgrade`
(:735) and `_committed_upgrade_if_ready` (:663), plus `tiers/progression_tree.py`
(:108). None of those is the producer. `plan HAL` shows the real path:

```
selected_goal: UpgradeEquipment(hard_leather_pants->leg_armor_slot)
PLAN (1 actions):
   1. Equip(hard_leather_pants->leg_armor_slot)
goals_tried:
  CraftPotionsGoal: nodes=30388 depth=17 plan_len=0
  GatherMaterials(lich_race_medal, ...): plan_len=0
  ... five more roots, all plan_len=0 ...
  UpgradeEquipment(hard_leather_pants->leg_armor_slot): nodes=2 depth=1 plan_len=1
```

`obtain_item_routing._equippable_goal` (:190) constructs the committed
`UpgradeEquipmentGoal` with no occupancy gate at all, and its own docstring says
so: *"THIS FUNCTION IS THE PRODUCER OF 'PURSUE THIS UPGRADE'; the goal's
`value()` is NOT."* The gate lives only on the reporting side. Every better gear
root fails to plan, the pants root plans in one action, and `select_pure` takes
the first goal with a non-empty plan.

Note that commit a1e67887 (2026-09-10, "gate a COMMITTED upgrade on slot
occupancy too") was written against this exact symptom — its docstring names
"live HAL 2026-09-09 equipped `hard_leather_pants` 203 times in 13.5 hours". The
loop has run for ten more days since that fix, because the fix went on
`_committed_upgrade_if_ready` and the producer is `_equippable_goal`.

Fix direction: apply `may_displace` in `_equippable_goal` before it commits to an
owned equippable, so a non-dominating candidate is never named as a root at all.

Secondary observation from the same run: `CraftPotionsGoal` burns 30,388 nodes to
depth 17 and returns no plan. That search is paid before the one-action plan that
actually gets chosen.

## F2 — HAL threw away a completed task by cancelling it

**Severity: high. One occurrence, 2026-09-19T18:10:10Z.**

HAL ground a skeleton task to **362/362** over roughly a day, then:

```
18:07:10  skeleton 362/362  GrindCharacterXP(skeleton)  Fight(skeleton)  ok
18:10:10  (no task)         CompleteTask                TaskCancel       ok
```

The goal was `CompleteTask`; the action executed was `TaskCancel`. The reward was
forfeited and a `tasks_coin` was spent to forfeit it.

Root cause is an underspecified goal. `CompleteTaskGoal.desired_state` is
`{"task_code": ""}` and `is_satisfied` is `not state.task_code or
state.task_total == 0`. Both `CompleteTaskAction.apply` and
`TaskCancelAction.apply` clear the task, so both satisfy the goal, and both cost
`distance_cost_pure(1.0, dist)` to the same `taskmaster_location` — an exact tie.
The planner had no way to prefer the turn-in, which mints the coin reward and
`TASK_COMPLETE_XP_ESTIMATE`, over the cancel, which burns a coin.

This is the only cancel in the store that happened at full progress. The other 17
cancels all fired at `0/N` under a `TaskCancel` goal and were legitimate.

Fix direction: make the goal's target the reward rather than the absence of a
task — drop `TaskCancelAction` from `CompleteTaskGoal.relevant_actions`, or state
the desired state in terms of the minted `tasks_coin`.

## F3 — Robby: 26 days without a single character XP point, and it is not the grey wall

**Severity: high. Ongoing.**

Robby's last fight was 2026-08-26 and his last character-XP gain was
**2026-08-25**. He sits at 18,757 / 19,700 — 943 XP, 4.8%, short of level 31 —
and has spent 4,040 of his 4,260 cycles this session (94.8%) on `LevelSkill`.
Zero `FightAction` in 94.7 hours.

The grind target is `rat`, which is also Robby's held task (`rat 0/107`). `rat`
has **no mapped spawn location**, so `FightAction._structurally_applicable`
returns False and `GrindCharacterXP(rat)` dies at 3 nodes with `plan_len=0`. The
task is unachievable for the same reason.

Three monsters are applicable *right now* and all are inside the XP band for a
level-30 character:

```
rat           lvl 25  locs=0  structural=False  applicable=False
death_knight  lvl 28  locs=2  structural=True   applicable=True
vampire       lvl 24  locs=2  structural=True   applicable=True
spider        lvl 20  locs=1  structural=True   applicable=True
```

So this is a target-selection stall, not a grey wall: the selector picked an
unreachable monster and never fell through to the reachable ones.

28 of 58 monsters in the catalogue have no mapped location. Any of them can be
handed out as a task or picked as a grind target with the same result.

## F4 — R2D2, C3P0 and Lor are genuinely grey-walled, one to two levels wide

**Severity: medium. Expected behaviour, but the escape is not being worked.**

Measured with `is_winnable(state, game_data, code, history)` against the live
character state and a snapshot of the learning store:

```
R2D2  L29  winnable=12  best=skeleton(18)  non-grey winnable: 0
C3P0  L29  winnable=12  best=skeleton(18)  non-grey winnable: 0
Lor   L30  winnable=12  best=pig(19)       non-grey winnable: 0
```

Every monster these three can beat is at a level gap of 11 or more and therefore
pays no character XP. Skill-grinding instead is the correct response. What is
missing is progress on the thing that would break the wall — better gear — and
all four gear roots in their plans return `plan_len=0`.

C3P0 and R2D2 both now plan `WithdrawGold(12373) -> NpcBuy(lifesteal_rune)`, which
is new and is a direct consequence of gold reaching the bank (see F7). That is the
wall starting to move.

## F5 — `is_winnable` contradicts 96.9% observed wins

**Severity: medium.**

`is_winnable(HAL, pig, history)` returns **False**. HAL's record against pig is
**309 wins / 10 losses (96.9%)** and he is fighting and beating pigs for 39 XP
each right now, this session.

The cause is gate 2 of `is_winnable`, the monotonic-win inference, which is
documented as *"Skipped if we've ourselves lost to this monster (any sub-threshold
result)"*. A single loss disables the inference permanently, and the verdict then
falls to the cold, pessimistic `predict_win`, which says no regardless of how many
hundreds of wins follow.

The fight still happens, so some other authority is deciding beatability on the
goal path. Two authorities disagreeing about the same question is the defect,
independent of which one is right.

## F6 — Task handling is dormant fleet-wide

**Severity: medium.**

- No `AcceptTaskAction` has fired since 2026-09-14 (R2D2); before that
  2026-09-10 (Lor). C3P0 and Robby have accepted exactly one task each, ever.
- HAL has held **no task at all for 1,403 cycles (~22 hours)** since the F2
  cancel. `AcceptTaskAction.is_applicable(HAL)` returns **True** — the action is
  available and simply never selected.
- The other four hold tasks with **0 progress across the entire 94.7-hour
  session**: C3P0 `pig 0/104`, Lor `spider 0/206`, R2D2 `ogre 0/327`, Robby
  `rat 0/107`. In three of the four cases the character is grinding a different
  monster than the task names, or not fighting at all.

## F7 — Gold banking is live and working (corrects a stale note)

**Severity: none — recorded because a prior note says the opposite.**

Bank gold is **73,184**. C3P0 and Lor each deposited exactly 10,000 via
`DepositAllAction` during this session. An earlier memory entry recording "0
coins banked in 184,010 cycles" is no longer true and should be updated.

Bank occupancy is about 50 of 110 slots — no pressure there.

## F8 — Lower-severity observations

- **Lor's HP economy.** 1,021 of 4,575 cycles (22.3%) below 30% HP, minimum HP 1,
  44 lost fights, 388 consumables burned. Lor is the only character consistently
  fighting hurt.
- **HAL's bag.** Cap 144, the smallest in the fleet (the others are 156-158), and
  currently 119-120 used. Contents are 82% combat junk: `skeleton_bone x41`,
  `algae x34`, `raw_porkchop x25`, `pig_skin x15`.
- **`LevelSkill` 404s.** 72 cycles this session ended `HTTP 404: Item not found.`
  on a `LevelSkill` action — the grind names an item the server does not have.
  Spread across all five characters, mostly `LevelSkill(weaponcrafting->15/20)`
  and `LevelSkill(jewelrycrafting->15)`.
- **Planning-budget exhaustion.** 31 cycles ended with `LevelSkill(<skill>) grind
  sub-plan EXHAUSTED the 15.0s planning budget`.
- **Session bookkeeping.** `sessions.cycle_count` stays 0 and `ended_at` stays
  NULL for every session that was not shut down cleanly, including all five rows
  for the current run and ten stale rows from 2026-09-14. Real per-character
  counts have to be recovered from the `cycles` table. Only the 2026-09-14 22:23
  crash set recorded counts and an `exit_reason`.

---

## Suggested order of work

1. **F1** — gate `_equippable_goal` on `may_displace`. Reclaims 16.5% of HAL's
   cycles and closes a loop that has survived two prior fixes.
2. **F3** — make grind-target selection fall through a monster with no mapped
   location. Unfreezes the fleet's strongest fighter after 26 days.
3. **F2** — make `CompleteTaskGoal` want the reward, not an empty task slot.
4. **F5** — reconcile the two beatability authorities.
5. **F6** — find why a fired, applicable `AcceptTaskAction` is never selected.
