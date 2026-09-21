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
| Robby | 30    | 18,757 / 19,700| **2026-08-25**    | 4,260  | **3** (death_knight, vampire, spider) — plus `rat`, see F3 |

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

## F3 — Robby: 26 days without a single character XP point

**Severity: high. Ongoing. CORRECTED 2026-09-20 after investigation — the cause
below replaces this section's first diagnosis.**

Robby's last fight was 2026-08-26 and his last character-XP gain was
**2026-08-25**. He sits at 18,757 / 19,700 — 943 XP, 4.8%, short of level 31 —
and has spent 4,040 of his 4,260 cycles this session (94.8%) on `LevelSkill`.
Zero `FightAction` in 94.7 hours.

### What this section first said, and why it was wrong

The first pass reported that Robby's grind target `rat` "has no mapped spawn
location", inferred from `gd.monsters.locations` being empty for it, and
generalised that to "28 of 58 monsters have no mapped tile".

That measurement was taken through the wrong index. `monsters.locations` is the
LEGACY index, and `_build_maps` keeps it **overworld-only by design** (P5b, its
own docstring: "the LEGACY indexes … ingest OVERWORLD tiles only"). The probe
also built its own `FightAction` from that index rather than asking the action
factory. Through the factory the same monster looks completely different:

```
rat in layered_content: [(-3, 12, 'interior'), (-2, 12, 'interior')]
FightAction(rat) emitted: 1
   travel_region=interior:-3,12  locations=[(-3,12), (-2,12)]
   structural=True  applicable=True
```

The fight is emitted, structural and **applicable right now**. Of the 28
index-empty monsters, 15 genuinely have no tile anywhere (event-only); the rest
have real spawns the legacy index cannot see.

### The actual root cause: no goal admits `MapTransitionAction`

`planner.py:293-295` skips any action whose `travel_region` differs from
`game_data.state_region(node.state)`. Crossing regions is `MapTransitionAction`
— 30 of them are in the pool — and it carries the tag `"movement"`.

**No goal admits it.** `grep -rn "MapTransitionAction\|'transition'"` over
`src/artifactsmmo_cli/ai/goals/` returns nothing, and 32 of the 40 goal files
override `relevant_actions` with a whitelist. Measured on Robby's live pool:

```
relevant_actions: 4 of 1932
   FightAction(rat) admitted: 1
   MapTransitionAction admitted: 0        <-- 30 in the pool
```

So the planner holds an applicable fight it can never legally step to, and the
search dies at 3 nodes. That is the `plan_len=0` this section first attributed
to a missing spawn.

Admitting the transitions — probe only, no production change — resolves it, and
cheaply:

```
HEAD (whitelist)   explored=3   created=3   depth=1  plan_len=0
+ transitions      explored=17  created=53  depth=5  plan_len=2
      1. Transition((-3,12,overworld)->(-3,12,interior))
      2. Fight(rat)
```

`rat` is also Robby's held task (`rat 0/107`), so the same two actions unblock
the task and the character grind together.

### Blast radius

Every piece of off-region content is emitted, applicable and unreachable — 16
monsters, 8 resources, 4 other:

```
lvl 25 rat                 interior:-3,12        adamantite_rocks   underground:-5,18
lvl 30 lich                underground:9,7       enchanted_mushroom restricted:overworld:-5,8
lvl 35 goblin_guard        underground:3,-5      gold_rocks         underground:3,-5
lvl 35 goblin_priestess    underground:1,-4      lava_fish_spot     underground:5,0
lvl 38 bat                 underground:-3,4      mithril_rocks      underground:-3,4
lvl 40 cultist_alchemist   interior:0,13         palm_tree          overworld:-4,17
lvl 40 dryad               restricted:ow:-5,8    swordfish_spot     overworld:-4,17
lvl 40 rosenblood          interior              torch_cactus       overworld:-4,17
lvl 44 sand_snake          overworld:-4,17
lvl 47 dusk_beetle         underground:-5,18     other: enchanted_fairy, god_of_the_sun,
lvl 50 baby_red_dragon     underground:6,4              sandwhisper_trader, sorceress
lvl 50 desert_scorpion     overworld:-4,17
lvl 50 sandwarden          overworld:-4,17
lvl 52 fennec              underground:5,0
lvl 52 flameche            underground:5,0
lvl 55 sandwhisper_empress interior:-4,19
```

Not only other layers: `overworld:-4,17` and `restricted:overworld:-5,8` are
gated sub-regions of the overworld.

Two consequences worth naming. `god_of_the_sun` is the raid P5b was built for,
and `ParticipateRaidGoal.relevant_actions` admits `FightAction` only — so the
raid chain cannot reach its own tile. `sandwhisper_trader` is the vendor behind
the `sandwhisper_bag` route `_equippable_goal` carries a dedicated branch for.

This is the mechanical reason `project_region_soundness` recorded the region
model as "region-gated but NEVER fired live (0/21987 cycles)": the edges are
emitted and then filtered out of every goal's pool before the planner sees them.

### Fix shape is a decision, not a detail

Three options, in increasing scope:

1. Admit `MapTransitionAction` in the goals that target region-bearing content
   (`GrindCharacterXP`, `ReachUnlockLevel`, `ParticipateRaid`, gathering,
   `PursueTask`). Smallest diff; the next goal to be written forgets it again.
2. Admit it in all 32 whitelisting goals. Exhaustive today, same forgetting
   problem tomorrow, 32 files to review.
3. Re-add every `"movement"`-tagged action structurally after a goal's
   whitelist — one locus, in `Goal.relevant_actions`'s caller or the arbiter, so
   no goal can omit it. This is the shape F1 argues for: an admission rule every
   producer must remember is one that will be forgotten.

(3) is the recommendation, but it changes the pool for all 32 goals at once and
the search-cost effect needs measuring across the scenario set before it lands.
Robby's own case costs 17 nodes against 3.

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

## F5 — RETRACTED. `is_winnable` was right; the probe was wrong

**Severity: none as filed. One dormant defect found alongside it.**

This section reported that `is_winnable(HAL, "pig", history)` returned False
against a 309-10 record, and concluded there were two disagreeing beatability
authorities. Both claims are withdrawn.

The probe passed HAL's LIVE hp, which was 174/520 at the time. Production does
not: `GamePlayer._is_winnable` projects to `max_hp` before asking, and its
docstring says exactly why — "Target-selection beatability: can the bot beat
this monster AFTER a normal HP recovery? … Without projecting to max_hp here, a
single mid-damage cycle narrows the winnable set" (the 2026-06-06 Robby trace,
278 cycles parked at 76/130 with 0 fights). Measured:

```
hp=174/520  is_winnable(HAL, pig) = False
hp=250/520  is_winnable(HAL, pig) = False
hp=350/520  is_winnable(HAL, pig) = False
hp=400/520  is_winnable(HAL, pig) = False
hp=520/520  is_winnable(HAL, pig) = True     <- what production reads
```

So there is one authority and it says True, which is why HAL fights pigs. A
wounded character being told it would lose is the function working.

The three gates were then measured per character per monster at `max_hp`, and
gate 1 is doing real work and doing it correctly — `C3P0/pig 60 samples 0 wins`
and `R2D2/pig 14/0` are vetoed while `Lor/pig 4689/4070` and `HAL/pig 321/311`
are not. Same monster, different gear, per-character learning.

### What is real: the own-loss guard counts transport errors as combat losses

`_won_at_or_above_level` disables the monotonic-win inference with

```python
if history.sample_count(target_repr) > history.win_count(target_repr):
    return False  # at least one loss against this monster
```

`sample_count` counts EVERY cycle with that `action_repr`, so `error:cooldown`,
`error:network` and `error:other` all read as "we lost to this monster". A
cooldown error is the client's own pacing; it is not a combat result.

Ten live pairs have gate 2 switched off by transport errors with **zero**
recorded `error:fight_lost`:

```
char   monster       n   wins  lost  transport   g2 now  g2 if combat-only
HAL    blue_slime    42    39     0          3    False  True
Robby  blue_slime    73    71     0          2    False  True
Robby  mushmush      39    35     0          4    False  True
C3P0   red_slime   1383  1378     0          5    False  True
Lor    chicken      267   266     0          1    False  True
Lor    red_slime   1652  1651     0          1    False  True
Lor    sheep        636   631     0          5    False  True
R2D2   blue_slime    86    81     0          5    False  True
R2D2   red_slime   1531  1521     0         10    False  True
R2D2   sheep        489   487     0          2    False  True
```

**It is fully dormant: 0 of the 10 change a verdict today**, because
`predict_win` answers True for every one of them, so the fall-through lands on
the same answer the inference would have given. It bites only where
`predict_win` is pessimistic about a monster the character demonstrably beats —
which is the exact situation gate 2 exists to cover.

Not fixed. The change is one predicate (count `error:fight_lost`, not every
non-`ok` outcome), it has a clean correctness argument, and it has no
observable effect today.

## F6 — Task handling is dormant fleet-wide: FOUR causes, not one

**Severity: medium. Ongoing. Investigated 2026-09-20.**

Fleet state: no `AcceptTaskAction` since 2026-09-14; HAL taskless for 1,403
cycles; the other four holding tasks at **0 progress for the whole 94.7-hour
session**. The instinct that this had "epicycle shape" was right — it is four
separate mechanisms, and fixing any one of them leaves the others standing.

Everything below is measured against live state through the production
functions, not hand-rolled.

### The winnable cascade is behaving CORRECTLY — that is not the bug

```
char   L   task           t1 task-aligned   t2 path-aligned   t3 picker    => farm target
HAL   23   (none)         None              None              pig             pig
Robby 30   rat    0/107   rat               full_moon_vampire death_knight    rat
C3P0  29   pig    0/104   None              skeleton          None            skeleton
Lor   30   spider 0/206   None              pig               None            pig
R2D2  29   ogre   0/327   None              skeleton          None            skeleton
```

Three of the four correctly REFUSE their task monster at tier 1 and grind
something they can actually beat. The task is then simply never let go, and a
held task blocks `ACCEPT_TASK` outright (`if state.task_code: return False`) —
so the character can never draw one it could do.

(Note for the record: `task_decision` returns **PURSUE**, not PIVOT, for every
monster task — `task_requirement` is about SKILL requirements and returns None,
so `task_decision_pure` takes its `req_is_none` arm. The combat arm is not
reached from here.)

### Cause 1 — the cancel rung and target selection ask different questions

For a monsters task, `MeansKind.TASK_CANCEL` fires only on
`resolve_task_horizon(...).verdict == HORIZON_OUT_OF_REACH`, and that walk
returns `None` unless `has_combat_deficit`. `has_combat_deficit` is

```python
return not predict_win(dataclasses.replace(state, hp=state.max_hp),
                       game_data, monster)
```

a bare `predict_win` — no history, no learned-loss veto. Target selection asks
`is_winnable`, which has one. They disagree exactly where it matters:

```
char   task     record   xp/kill  predict_win  is_winnable  deficit  cancel can fire
Robby  rat        0/0        34       True        True       False      False
C3P0   pig       0/60        23       True        False      False      False
Lor    spider     0/0        25       False       False      True       True
R2D2   ogre       0/0        28       False       False      True       True
```

**C3P0 has lost 60 of 60 fights against pig.** `is_winnable` vetoes it, so the
cascade refuses the task; `predict_win` says C3P0 wins, so there is no deficit,
so there is no horizon, so there is no cancel reason. C3P0 holds a provably
impossible task indefinitely. This is a real two-authority split — the shape F5
claimed and did not have, one layer up.

### Cause 2 — `HORIZON_GEAR` carries no distance

Lor and R2D2 DO produce a horizon, and it is not `OUT_OF_REACH`:

```
Lor   spider -> TaskHorizon(verdict='gear', gear_target=('greater_dreadful_staff', 'weapon_slot'))
R2D2  ogre   -> TaskHorizon(verdict='gear', gear_target=('skull_wand',            'weapon_slot'))
```

so the cancel rung correctly declines — the model says gear closes the fight.
What the verdict does not say is how far away the gear is:

```
greater_dreadful_staff   weaponcrafting@30   Lor  has 11    19 levels
skull_wand               weaponcrafting@25   R2D2 has 13    12 levels
```

Both characters are in fact grinding weaponcrafting, at roughly one level per
94.7 hours this session. A task blocked behind a 19-level craft reads
identically to one blocked behind a craft available this hour, and the rung
declines both. (Nineteen levels is the same number as
`project_craft_skill_gate_asymmetry`'s 82.6%-of-a-39.6h-run finding.)

### Cause 3 — HAL cannot accept, and it is not the draw flag

HAL is the only character who could accept one. `ACCEPT_TASK` has three
conjuncts; measured with `draw_owed` forced True to isolate the rest:

```
HAL    task=None   target_gear=13  deferral_blockers=2   ACCEPT_TASK fires = False
         DEFER: hard_leather_boots   CRAFTABLE NOW (gearcrafting 20>=20)
         DEFER: slime_shield         CRAFTABLE NOW (gearcrafting 20>=20)
```

So the blocker is the **gear-chain deferral**, not `ctx.draw_owed`. The rule is
"target gear is CRAFTABLE under current skill levels → the fallback walk should
drive the gather/craft chain rather than accept another task". But HAL's walk is
not driving those crafts: `chosen_root` is `ObtainItem(lich_race_trophy)` and
the selected goals are `DrainBankJunk` / `GrindCharacterXP(pig)`. The deferral
defers to work that never happens, and the standing FACT that some sheet item is
craftable keeps the rung off permanently — the shape of
`project_gear_latch_task_deficit_freeze`.

### Cause 4 — the two characters most stuck hold no task coin

`TaskCancelAction.is_applicable` needs `tasks_coin >= 1` (the server charges one,
HTTP 478 otherwise):

```
Robby  tasks_coin bag=0 bank=0   is_applicable=False
C3P0   tasks_coin bag=0 bank=0   is_applicable=False
Lor    tasks_coin bag=7 bank=0   is_applicable=True
R2D2   tasks_coin bag=1 bank=0   is_applicable=True
```

C3P0 — the one character with a provably impossible task — could not cancel it
even if Cause 1 were fixed. Coins come from turning tasks in, which is the loop
that is stuck. This is the dormant half recorded in
`project_task_horizon_residuals`.

### Cause 5 (already fixed) — Robby's `rat` was off-region

`@7fb59b7c`. His horizon reads `None` for the right reason now: rat is winnable
and, since the transition edge is admitted, reachable.

### What would actually move it

In dependency order, smallest first:

1. **Cause 1** — give `has_combat_deficit` the history, so the learned-loss veto
   reaches the cancel rung. One argument. Frees C3P0 the moment it has a coin.
2. **Cause 4** — a coin source that does not require completing a task first,
   or let the cancel draw one from the bank.
3. **Cause 3** — arm the gear deferral on the chain actually being PURSUED, not
   on the standing fact that something is craftable.
4. **Cause 2** — give `HORIZON_GEAR` a distance and treat "unreachably far" as
   out of reach. Largest, and the one most likely to need its own design pass.

Not fixed — this was an investigation.

## F9 — HAL's trophy: the fleet surrender machinery already works; one purchase blocks it

**Severity: high (HAL's only root). Verified end-to-end 2026-09-20, read-only.**

The premise — "the other players are holding ingredients for the
lich_race_trophy" — is correct. The chain is all NPC currency, no crafting:

```
event_ticket  --100-->  lich_race_medal  --10-->  lich_race_trophy   (archaeologist)
```

`lich_race_medal` is worn by all five characters, one each, plus one banked.

### The release feature already exists

`SurrenderCurrencyGoal` — "unequip every worn copy and deposit every carried
copy of a dual-role currency this character lost the fleet's `claim_turn_in`
election for". `dual_role_holdings` already counts WORN copies ("a worn medal
is still fleet currency, recoverable in one `UnequipAction`"), and the live
`holding_ledger` already carries all five medals. `_resolve_turn_in`'s docstring
names this very case from a previous round.

It is gated on one number:

```
fleet_total = 5 worn + 1 banked = 6      price = 10
turn_in_ready_pure(6, 10)  = False
turn_in_ready_pure(11, 10) = True
```

### Simulated at 11 medals, every stage works

Throwaway coordination DB, real election / goals / planner:

```
ELECTION
  HAL    turn_in=TurnIn(..., buyer='HAL', fleet_total=11)  recall=None
  Robby  turn_in=TurnIn(..., buyer='HAL')  recall=('lich_race_medal', 1)
  C3P0   ... same        Lor ... same        R2D2 ... same

SURRENDER (each of the four)
  SurrenderCurrency(lich_race_medalx1)  explored=3  plan_len=2
     1. Unequip(artifact1_slot)
     2. DepositItem(lich_race_medal×1)

BUYER (after the four deposits land: bank 5, HAL holds 6)
  CurrencyTurnIn(lich_race_trophy)  explored=5  plan_len=3
     1. Unequip(artifact1_slot)
     2. Withdraw(lich_race_medal×4)
     3. NpcBuy(lich_race_trophy×1@archaeologist)
```

All five pass the buyer election's rules 3 and 4 (`level_ok`, `pick_loadout`
places the trophy), so the election is not fragile either.

NOT covered by the simulation: the live four-process timing — TTL expiry and
claim renewal while four separate processes each take their two surrender
actions.

### The one real blocker: an item-currency purchase that cannot fit the bag

The fleet can reach 11 medals — 6 held plus 5 bought with the 581 banked
`event_ticket`. That purchase never plans:

```
Withdraw(event_ticket×498)                applicable=False   # HAL bag 122/144, 22 free
NpcBuy(lich_race_medal×5@archaeologist)   applicable=False   # needs 500 tickets at once
NpcBuy(lich_race_medal×1@archaeologist)   applicable=True    # with 100 tickets + cleared bag
                                                             # emitted by the factory,
                                                             # NOT admitted to the goal's pool
GatherMaterials(lich_race_medal, x5)      explored=4  plan_len=0
```

`GatherMaterialsGoal` materializes ONE indivisible buy sized to the whole
remaining need, and a withdraw sized to its whole price. Neither fits a
144-item bag. The all-or-nothing shape of `project_jewelry_smelt_stall`.

Fix direction: bound the materialized item-currency buy and its withdraw by
free inventory — `batch = min(needed, free // price)` — so the chain becomes
`DepositAll -> Withdraw(event_ticket×100) -> NpcBuy(medal×1)`, repeated. The
surrender machinery then fires by itself at 10.

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

1. ~~**F1**~~ — DONE @16cddf72. Gated at the walk that NAMES the root
   (`gear_targets_with_blockers`), not at `_equippable_goal`: that function must
   return a Goal, so refusing there only yields an unplannable root. Verified
   live.
2. ~~**F2**~~ — DONE @070777e1.
3. ~~**F3**~~ — DONE @7fb59b7c. Shared, CONDITIONAL re-add in both plan
   producers; unconditional cost 41x the search (1,467 -> 60,662 nodes over 44
   scenarios), gating on the goal's own whitelist restores baseline exactly.
4. ~~**F5**~~ — RETRACTED, see F5. Optional: stop the own-loss guard counting
   transport errors as combat losses (dormant, 10 pairs, 0 live verdict
   changes).
5. **F6** — INVESTIGATED, four independent causes, see F6. Smallest real win
   is Cause 1: pass the history to `has_combat_deficit` so the learned-loss
   veto reaches the cancel rung.

Note on method, earned three times in this audit — every one of them a probe
that bypassed production rather than a bug in production:

* F3 read the LEGACY overworld-only index and hand-built a `FightAction` from
  it, instead of asking `build_actions` what it emits.
* F5 called the module-level `is_winnable` with live hp, instead of the
  `GamePlayer._is_winnable` wrapper that projects to `max_hp` first.
* F1's own fix was first aimed at `_equippable_goal`, which cannot refuse
  because it must return a Goal; the gate belonged at the walk that names the
  root.

Call the function production calls, with the arguments production passes.
