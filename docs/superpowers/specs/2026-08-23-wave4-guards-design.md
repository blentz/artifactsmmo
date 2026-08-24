# Wave 4 — the two sequencing guards, against the graph that actually exists

Date: 2026-08-23
Status: DESIGN, not authorised for implementation
Author task: `docs/PLAN_goal_decision_graph_waves_3_6.md` task 4.1
Parent spec: `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md` §"Wave 4"
Predecessor: `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md`
Worktree read: `/home/blentz/git/artifactsmmo/.worktrees/waves-3-6` at `9dcf851c`
Live figures read from `~/.cache/artifactsmmo/learning.db`, 78,552 cycles,
2026-08-02T15:18Z → 2026-08-23T14:17Z. **The fleet runs `origin/main`, which is
at `ee2d2d67` — the gear-latch split, but NOT wave 3a. Every live number below
is PRE-FLIP.**

---

## 0. Headline conclusions

1. **`MaxGearForLevel` does not exist and never did.** The brief (plan
   `:522`, parent spec `:403`) says `GearLatch` and `deficit_upgrade_target`
   are "absorbed into `MaxGearForLevel`". Nothing by that name is in the
   codebase. §1 does the reconciliation and maps the intent onto what wave 3a
   actually built. This is the ninth spec error this epic has produced; it is
   recorded, not silently retargeted.

2. **The `GearLatch` edge/standing split MUST survive, and the design that
   preserves it is not "port both halves into a node".** The EDGE arm
   (`gear_latch.py:53`) is a *replan trigger*, not a decision, and it already
   has a second, non-guard consumer (`should_replan.py:30`). The STANDING arm
   (`gear_latch.py:78`) is a per-cycle recomputation and is exactly what a
   `Decision.resolve` is. **Absorb the standing arm; leave the edge arm outside
   the graph entirely.** A `Decision` node has no memory between cycles, so
   absorbing the standing half mechanically enforces the rule the incident
   taught. Absorbing the edge half would smuggle a latch back into a walk that
   is re-derived from live state — the 981-cycle freeze with new node names.

3. **`CRAFT_POTIONS` should NOT become a root Decision node, and I recommend
   wave 4 leave it in `GUARD_ORDER` untouched.** Three independent reasons in
   §6, the strongest measured: `ObtainItem`'s slot arm is quantity-blind
   (`meta_goal.py:56-58`), so a potion root is satisfied by one potion against
   a baseline of twelve. Demoting the rung out of `BAND_GUARD` is measurably
   equivalent to deleting it: the sibling rung that already sits in
   `DISCRETIONARY_ORDER` for the same job, `MAINTAIN_CONSUMABLES`, **fired and
   won 3 times in 78,552 live cycles (0.004%)**. This is a departure from the
   brief and it is stated loudly here.

4. **The potion route returns to the decision surface in exactly one narrow
   way, and it comes free.** `combat_deficit`'s candidate pool already admits
   `type_ == "utility"` items (`combat_deficit.py:115-119`, and its own
   docstring's live C3P0 chain contains `earth_boost_potion`). Routing the
   deficit chain through the graph therefore restores potions as a decision
   *when a potion is what closes a blocked fight* — and only then. The
   tier-ladder half of GAP-4/GAP-5 stays gone, deliberately: §6.3.

5. **Wave 4 breaks Lean theorems. Wave 3 did not.** Wave 3's §0.3 could say
   "no Lean theorem breaks" because both ranking-dependent `ExtMeasure` slots
   were excluded from `FMeasure`. `gearReviewFlag` is **slot 10 of `FMeasure`**
   (`FMeasure.lean:29`, `:87`, `:135`) — inside the 16-slot measure that
   carries `ai_reaches_fifty_unconditional` — and `craftPotionsFlag` is slot 9.
   Removing either rung is a measure restatement plus a three-way oracle
   renumber. §7 sizes it. This is the single biggest cost difference between
   waves 3 and 4 and the brief does not mention it.

6. **The scenario set cannot exercise any of this.** Measured: **0 of 30
   scenarios carry a task of any kind** (`ScenarioCharacter.task`,
   `scenario.py:84`, defaults `None`, set by nobody). Therefore
   `has_combat_deficit` is `False` in 30/30 and `deficit_upgrade_target` is
   `None` in 30/30. The standing arm and the monster-aware target have **zero
   offline coverage today**. Any wave-4 census or acceptance suite driven off
   `tests/test_ai/scenarios/` is vacuous by construction until new scenarios
   exist. New scenarios are a *prerequisite deliverable*, not a nice-to-have —
   §8.

---

## 1. The reconciliation: `MaxGearForLevel` is not a node

`grep -rn MaxGearForLevel` over `src/`, `tests/`, `formal/`, `docs/` and
`.superpowers/` returns **nine hits, all in prose, zero in code**:

| where | what it says |
|---|---|
| `docs/PLAN_goal_decision_graph.md:51`, `:1052`, `:1301` | wave-1/2 **task name** for Task 6 |
| `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md:284-286` | a column value in a per-character table |
| `…2026-08-22-goal-decision-graph-design.md:381`, `:403` | the wave-2 step and the wave-4 sentence this design answers |
| `docs/PLAN_goal_decision_graph_waves_3_6.md:522` | the brief |
| `…2026-08-23-wave3-resolution-design.md:54` | wave 3 already flagging that its data source was unconsumed |

What wave-1/2 Task 6 actually shipped (`docs/PLAN_goal_decision_graph.md:1052-1064`)
was a **method on `CharacterObjective`**, not a class:

```
CharacterObjective.gear_targets_with_blockers(state, history) -> dict[str, GearTarget]
```

— `tiers/objective.py:424-437`, with `GearTarget` at `:294-330` and
`_classify_target` at `:439-471`.

The five `Decision` nodes that exist are, in `ai/decisions/root.py`:

| node | line | role |
|---|---|---|
| `IsMyGearBehindMyTier` | `:227` | entry; consumes `gear_targets_with_blockers` |
| `WhichSlotIsFurthestBehind` | `:252` | the one list-valued node; largest tier gap + d'Hondt aging |
| `IsThisTargetBlocked` | `:372` | `GearTarget` → `ObtainItem \| ReachSkillLevel` |
| `IsThereACombatTarget` | `:440` | `ctx.combat_monster` → `ReachCharLevel` |
| `CanIClearMyTier` | `:465` | trunk, or the honest `None` wall |

**Mapping the brief's intent onto reality.** "Absorbed into `MaxGearForLevel`"
means: *absorbed into the gear arm of the root graph, which is the subgraph
`IsMyGearBehindMyTier → WhichSlotIsFurthestBehind → IsThisTargetBlocked` fed by
`gear_targets_with_blockers`.* That is the only reading the codebase supports.
This design uses that reading and invents no node named `MaxGearForLevel`.

The reading has one consequence the brief could not have foreseen: **the gear
arm is already the FIRST question the walk asks.** `IsMyGearBehindMyTier` is
`resolve_root`'s entry (`root.py:498`). So `GEAR_REVIEW`-as-a-guard is now a
*second, rival* gear-review producer that preempts the graph from
`BAND_GUARD` — the two-plan-producers shape this repo has a named lesson for.
That, not the brief's sentence, is the real argument for wave 4.

---

## 2. What each guard reads today — every input, by file:line

### 2.1 `GEAR_REVIEW` — the firing predicate

```
guards.py:260-261   if kind is GuardKind.GEAR_REVIEW:
                        return ctx.gear_review_active
```

One input. `ctx.gear_review_active` is declared at `selection_context.py:73`
(`bool = False`) and written at exactly one production site,
`player.py:3734`, from `self._gear_latch.active`.

`GearLatch.active` (`gear_latch.py:29-31`) is `self._active or self._blocked`.
The two are set in `GearLatch.update` (`gear_latch.py:33-79`), whose inputs are:

| input | source | line |
|---|---|---|
| `prev_level` | `GamePlayer._prev_level`, or `state.level` on cycle 1 | `player.py:1128`, `:1019` |
| `state.level` | live state | `gear_latch.py:53` |
| `last_outcome` | `GamePlayer._last_outcome` (`"error:fight_lost"` is the only value read) | `gear_latch.py:53` |
| `game_data` | for `has_craftable_upgrade_any_slot` | `gear_latch.py:55` |
| `winnable_alternative` | `GamePlayer._winnable_farm_target() is not None` | `player.py:1129-1133`, `:1019-1021` |

and its two derived predicates:

* `has_craftable_upgrade_any_slot(state, game_data)` — `gear_appropriateness.py:11-15`,
  a one-line delegate to `UpgradeEquipmentGoal().find_upgrade_target(state, game_data)`
  (`goals/progression.py:549-563`), which itself is
  `_best_by_value(_find_inventory_upgrade, _find_craftable_upgrade_target)`.
  **Measured: `True` in 30/30 scenarios.** The latch's clear condition never
  fires offline.
* `has_combat_deficit(state, game_data)` — `combat_deficit.py:146-161`; one
  `predict_win` at `max_hp` against `_blocked_task_monster(state)`
  (`combat_deficit.py:137-143`: requires `state.task_type == "monsters"`, a
  non-empty `task_code`, `task_total > 0` and `task_progress < task_total`).
  **Measured: `False` in 30/30 scenarios**, because no scenario has a task.

`update` is called from **two** production sites: `player.py:1132` (the run
loop, before selection) and `player.py:1020` (`plan_from_state`, the read-only
diagnostic path). Both compute `combat_monster = self._winnable_farm_target()`
*first* and pass it to both the latch and `_selection_context(combat_monster)`
(`player.py:3730`). So `winnable_alternative` and `ctx.combat_monster` are the
**same value from the same call today** — carried as two parameters that could
drift. §5.3 collapses them.

### 2.2 `GEAR_REVIEW` — the goal mapping

`strategy_driver.map_guard`, `:355-405`. Reads, in order:

| line | input |
|---|---|
| `:356-357` | `state` (raises `ValueError` when `None`) |
| `:366-380` | `_deficit_cost(code)` → `acquisition_actions(code, 1, state, game_data, ctx, equip=True, store=history)` — reads `ctx` and `history`. Its own comment records **386 ms per firing on live C3P0**, 22 priced candidates |
| `:382-383` | `deficit_upgrade_target(state, game_data, cost_of=_deficit_cost)` — `combat_deficit.py:164-211` |
| `:384-385` | fallback `UpgradeEquipmentGoal(initial_equipment=state.equipment).find_upgrade_target(state, game_data)` |
| `:386-389` | second fallback: bare `UpgradeEquipmentGoal` |
| `:391` | `state.inventory.get(item, 0) > 0` |
| `:391` | `_materials_in_hand(item, state, game_data)` — `strategy_driver.py:242-248`, inventory **+ bank** |
| `:402-403` | `_gather_goal_for_unreachable_equippable(item, state, game_data, committed.max_depth, ctx)` — `obtain_item_routing.py:62` |

`deficit_upgrade_target` in turn reads `_blocked_task_monster` and
`combat_deficit(..., max_chain=1, cost_of=…)`, whose candidate pool is
`_pool` (`combat_deficit.py:106-121`): every item whose `type_` is in
`ITEM_TYPE_TO_SLOTS` with `stats.level <= state.level`. **`"utility"` is in
`ITEM_TYPE_TO_SLOTS`** — this is load-bearing for §6.3.

**A duplicate found by reading, not by grep.** `map_guard`'s tail
(`strategy_driver.py:390-405`) is a hand-inlined variant of
`obtain_item_routing._equippable_goal` (`:174-265`), the function
`decisions/obtain_item.py:215` already calls. They differ in the in-hand gate:
the guard checks `state.inventory` only, `_equippable_goal` checks inventory
**and bank**. `obtain_item_routing.py:127-134` documents the resulting
divergence — a bank-only recipe-less equippable reaches
`GatherMaterialsGoal(code, {})` through the guard and not through
`_equippable_goal`. Absorbing `GEAR_REVIEW` deletes the duplicate and leaves
one routing function.

### 2.3 `GEAR_REVIEW` — every consumer, classified

`grep -rn "gear_review\|gear_latch\|latch_active"` over `src/ tests/ formal/`,
each hit classified rather than counted:

| consumer | line | kind |
|---|---|---|
| `guards._fires` GEAR_REVIEW arm | `guards.py:260-261` | **production** |
| `should_replan` latch-edge replan | `should_replan.py:11`, `:30`; `PlanCache.latch_active` `plan_cache.py:20`; written `player.py:821`, read `player.py:811` | **production — NOT the guard.** The one a grep-and-count would miss |
| `LearningStore.save_plan_commitment(latch_active=…)` | `player.py:832`, `store.py:1264`, `:1279`, `:1287`, `models.py:525` | **production (persistence)**; the column is written and read back by `load_plan_commitment` (pinned `tests/test_ai/test_plan_persistence.py:35`) |
| `decide_key._GUARD_REPR[GEAR_REVIEW]` | `decide_key.py:51` | **production** (oracle dispatch table) |
| `formal/diff/test_decide_key_diff.py:35` | index **8** | differential harness |
| `formal/diff/test_ladder_fires_diff.py:217`, `:277`, `:460`, `:806-807`, `:930` | oracle arg **[26]** `gearReviewFires`, passed identically to both sides | differential harness |
| `formal/Formal/DecideKey.lean:50`, `:113`; `formal/Oracle.lean:1183` | Lean mirror, index 8 | Lean |
| `FMeasure.lean:29/87/135/204/214/225/237/250/264/279`; `EMeasure.lean:16/55/62/67/70/98/131/433/461`; `DMeasure.lean:71/112/142/375/396/419/446/474/504` | `gearReviewFlag` slot | Lean |
| `BlockerDescent.lean:313-318`, `BlockerDescentD.lean:102/514`, `BlockerDescentE.lean:222/228/306/322/891/920`, `BlockerMonotone.lean:109-140`, `BlockerQuieting.lean:82-88`, `CycleStepDC.lean:342-356`, `CycleStepE.lean:158` | descent / monotone / quieting lemmas | Lean |
| ~14 `tests/test_ai/*.py` sites passing `gear_review_active=False` into a ctx | — | **test-only fixture noise** |
| `combat_deficit.py:35-39`, `:173-177`; `obtain_item_routing.py:13`, `:74`, `:127-130`; `gear_latch.py:12`, `:61`, `:67`; `player.py:344` | **comments** — no behaviour |

Production consumers: **four** (guard predicate, `should_replan`, the
persistence column, the decide-key table). The "N references" here is ~70; it
collapses to four. Note in particular that **`should_replan` is not the guard**
— a wave-4 plan that deletes `GearLatch` outright silently deletes a plan-cache
invalidation trigger.

### 2.4 `CRAFT_POTIONS` — the firing predicate

```
guards.py:262-263   if kind is GuardKind.CRAFT_POTIONS:
                        return craft_potions_fires(state, game_data, history)
```

`potion_supply.craft_potions_fires`, `:167-230`. Inputs, in evaluation order:

| line | input |
|---|---|
| `:186` | `unlock_boost_target(state, game_data)` — `unlock_boost.py:28-36`; reads `state.equipment`, `state.level`, `state.inventory`, memoised on `(id(game_data), level, equip_sig, owned)` |
| `:188-190` | `game_data.crafting_recipes[boost]` + `_recipe_producible` (`potion_supply.py:119-137`: inventory+bank, NPC gold purchase, or `game_data.gatherable_drop_items()`) |
| `:191` | `target_potion_pure(state, game_data)` — `:34-…`, highest-`hp_restore` craftable-now utility item, smallest-code tiebreak |
| `:194` | `equipped_potion_qty(state, target)` — `equipped_potion.py:10-16`, **sum across BOTH utility slots** |
| `:195-197` | `potion_baseline_pure(state.level, POTION_LOW_LEVEL, POTION_LOW_QTY, POTION_HIGH_LEVEL, POTION_HIGH_QTY)` — `thresholds.py` |
| `:206` | `primary_combat_target(state, game_data)` — `:29-32`, first winnable in-band monster from `combat_targets.combat_target_monsters`. **NOT `ctx.combat_monster`** — a second, independent combat-target opinion |
| `:207-208` | `projected_heal_need_per_fight(state, game_data, monster, history)` — `:140-163`; `history.hp_healed_per_fight(monster, game_data.hp_restore_of)` first, else `expected_damage_per_fight` gated by `fight_is_marginal_pure` |
| `:209-211` | `potion_stock_target_pure(hp_need, game_data.hp_restore_of(target), level_baseline)` |
| `:213-222` | the already-stocked branch: `best_boost_potion(state, game_data, monster)`, a second `potion_baseline_pure`, a second `_recipe_producible` |
| `:227-230` | `game_data.crafting_recipes[target]` + `_recipe_producible` |

Nine distinct helpers, two of which (`primary_combat_target`,
`unlock_boost_target`) are *independent combat-target opinions* that the graph
does not share.

### 2.5 `CRAFT_POTIONS` — every consumer, classified

| consumer | line | kind |
|---|---|---|
| `guards._fires` CRAFT_POTIONS arm | `guards.py:262-263` | **production** |
| `map_guard` → `CraftPotionsGoal(combat_monster=ctx.combat_monster, game_data, history, state)` | `strategy_driver.py:408-413` | **production; the ONLY construction site of `CraftPotionsGoal` in `src/`** |
| `decide_key._GUARD_REPR[CRAFT_POTIONS] = "CraftPotions"` | `decide_key.py:52` | **production** |
| `formal/diff/test_decide_key_diff.py:38` | index **11** | differential harness |
| `formal/diff/test_ladder_fires_diff.py:174`, `:218`, `:466-469`, `:938-940` | oracle arg **[32]** `craftPotionsFires`, computed by production's real predicate | differential harness |
| `DecideKey.lean:53`, `:116`; `Oracle.lean:1190`, `:2444`, `:2505` | Lean mirror, index 11 | Lean |
| `FMeasure.lean:29` (slot 9), `EMeasure.lean`, `BlockerDescentE.lean:138-139` `refreshE_craftPotions` | measure slot + refresh-invariance lemma | Lean |
| `audit/obtain_parity_completeness.py:131`, `audit/recycle_source_completeness.py:99` | **production censuses** — both stock a utility slot *specifically so this guard does not preempt* their subject | **production (indirect)** |
| `goals/craft_potions.py:119` | comment naming the shared core | comment |
| `expected_damage.py:37` | comment | comment |

Because `map_guard` is the only construction site, `selected_goal ==
'CraftPotionsGoal'` in `learning.db` is an **exact** count of cycles this guard
fired *and won*. `UpgradeEquipment(...)` is **not** exact — `map_guard`
GEAR_REVIEW and `objective_step_goal`'s upgrade arm produce the same repr, and
nothing in the cycles table separates them. Say so wherever the 20,829 figure
is used.

### 2.6 Live firing rates (PRE-FLIP, `origin/main` @ `ee2d2d67`)

| measure | value |
|---|---|
| total cycles | 78,552 (2026-08-02 → 2026-08-23) |
| `CraftPotionsGoal` selected | **2,245 (2.86 %)**, 4 of 5 characters, per-character 0.0 – 7.5 % |
| `UpgradeEquipment*` selected | 20,829 (26.52 %) — **both producers, not attributable** |
| of which `→utility*_slot` | 1,185 (1.51 %) |
| `MaintainConsumables` selected | **3 (0.004 %)** |
| `EquipOwnedGear` filling a utility slot | 92 |
| cycles holding a workable monsters task | 15,240 (19.4 %) — the only cycles where the STANDING arm *could* arm |
| latch currently armed | 2 of 5 characters (`plan_commitment.latch_active`, sampled 2026-08-23T14:16Z) |
| longest consecutive `UpgradeEquipment*` run | R2D2 187, Lor 157, HAL 109, Robby 88, C3P0 37 |
| longest consecutive `CraftPotionsGoal` run | HAL 69, Robby 64, C3P0 61, R2D2 10, Lor 0 |

The 187-cycle run does **not** reproduce the incident's 981 figure; a
consecutive-run count is broken by any interleaved `RestoreHP`, so 187 is a
lower bound on how long a latch held, not a measurement of it. Stated as a
limit, not as a refutation.

**Live evidence the edge/standing split works.** R2D2 held a `pig` task for
**3,095 cycles** (2026-08-20T01:15Z → 2026-08-23T14:16Z) and levelled 20 → 21
during it; **396 of those cycles selected `GrindCharacterXP(skeleton)`** and only
187 selected an `UpgradeEquipment*`. That is exactly the behaviour the USER
asked for ("not being able to win against a pig is fine … that shouldn't block
us from fighting other, winnable monsters") and it is measured on the fixed
code, on `origin/main`. Any wave-4 design that regresses it has an explicit
baseline to fail against.

---

## 3. `GearLatch` — the split, and why the design preserves it

### 3.1 The incident and the fix, restated from the code

`gear_latch.py:64-70` records it: R2D2, 2026-08-21/22, held `monsters/pig
0/137` at combat margin −2 for 38 hours. The deficit was real, so the latch
re-armed every cycle, so `GEAR_REVIEW` — a **guard**, therefore `BAND_GUARD`,
therefore ahead of everything in `arbiter_select.select_pure` — preempted
`GrindCharacterXP(skeleton)` (winnable, 37 xp/kill) for 981 consecutive cycles.
Character XP frozen 31.6 h at 1861/8200. `gear_latch.py:70`: *"No level-up and
no `error:fight_lost` occurred in that whole run, so the EDGE arm was never set
and this was the sole cause."*

The fix (`ee2d2d67`, on `origin/main`) is two arms that are **deliberately not
the same shape** (`gear_latch.py:4-9`):

```python
# EDGE — a moment. Latches, holds until no craftable upgrade remains.
if state.level > prev_level or last_outcome == "error:fight_lost":
    self._active = True                                   # gear_latch.py:53-54
craftable = has_craftable_upgrade_any_slot(state, game_data)
if self._active and not craftable:
    self._active = False                                  # gear_latch.py:55-57

# STANDING — a condition. Recomputed every cycle, releases on its own.
self._blocked = (craftable and not winnable_alternative
                 and has_combat_deficit(state, game_data))   # gear_latch.py:78-79
```

The rule, in `gear_latch.py:75-77`: *"STANDING, not latched: a frozen character
has no edge left to re-trigger it, so an arm that only stopped RE-arming would
need a restart to take effect."* Generalised in memory as **a standing
condition must not drive a sticky latch**.

### 3.2 The single most important thing in this document

A `Decision` node's only interface is

```python
def resolve(self, state, game_data, ctx, history) -> "Decision[Leaf] | Leaf | None"
```

It is constructed fresh by `resolve_root` every cycle (`root.py:494-500`) and
carries no state across cycles. `RootWalk` (`root.py:94-125`) is per-walk and
discarded. **A Decision node is structurally incapable of holding a latch.**

That cuts both ways, and both halves matter:

* **Absorbing the STANDING arm is not merely safe — the graph mechanically
  enforces the rule.** `_blocked` is a pure function of
  `(state, game_data, winnable_alternative)`. Written as a node it *cannot*
  become sticky, because there is nowhere to put the stickiness. This is the
  strongest available discharge of the incident's lesson: not a test, a type.

* **Absorbing the EDGE arm would re-merge them, and that is the one thing wave
  4 must not do.** To express `_active` as a node you would have to thread
  `prev_level` / `last_outcome` / a persisted bool through `SelectionContext`,
  and the moment `ctx` carries a latch bit the node reads, the node *is* the
  guard again — a walk answer determined by an event N cycles ago, preempting
  a live objective, with no way to release except a condition the node does not
  own. That is the freeze, with new node names. **Reject any wave-4 plan that
  puts `prev_level`, `last_outcome`, or a latch boolean into a node's
  `resolve`.**

### 3.3 So what happens to `GearLatch`?

It stops being a *decision input* and becomes what its other consumer already
treats it as: a **replan trigger**.

* `_blocked` (the standing arm) **moves into the graph** as
  `IsAFightBlockingMe` (§5.1). `has_combat_deficit` stays where it is; the node
  calls it.
* `_active` (the edge arm) **stays a `GearLatch`**, keeps its `update` and its
  clear condition, and keeps feeding `should_replan` (`player.py:811`) and
  `save_plan_commitment` (`player.py:832`). It stops feeding
  `SelectionContext`.
* `GearLatch.active` (`gear_latch.py:29-31`, `self._active or self._blocked`)
  **is deleted**, along with `_blocked` and the `winnable_alternative`
  parameter. The class narrows to the edge arm and should be renamed to say so
  — `RegearEdge`, with `armed` replacing `active`. Renaming is not cosmetic
  here: `active` is the name that let two different questions share one bool,
  and a name that cannot be misread is the cheapest guard against a tenth
  recurrence.
* `ctx.gear_review_active` (`selection_context.py:73`) is deleted, with its ~14
  test-fixture sites.

**What this buys, precisely.** After wave 4, the standing condition can no
longer preempt from `BAND_GUARD` at all. It competes as a root, inside the
walk, against the tier climb — which is where "my gear is behind what this
fight needs" belongs.

---

## 4. The eleven interrupt guards — named, and the honest count

Removing `GEAR_REVIEW` and `CRAFT_POTIONS` from the 13-member `GuardKind`
(`guards.py:75-89`) leaves **exactly eleven**. The brief's number is correct.
They are, in `GUARD_ORDER` (`guards.py:91-111`) order:

| # | `GuardKind` | fires on | `guards.py` |
|---|---|---|---|
| 1 | `HP_CRITICAL` | `state.hp_percent < CRITICAL_HP_FRACTION` | `:171-172` |
| 2 | `REST_FOR_COMBAT` | target selected, `hp < max_hp`, lose now, win rested | `:173-192` |
| 3 | `BANK_UNLOCK` | bank locked, unlock monster in reach, no xp yet | `:193-200` |
| 4 | `REACH_UNLOCK_LEVEL` | `bank_required_level` within `MAX_ACHIEVABLE_GAP` | `:201-204` |
| 5 | `GE_CANCEL` | `cancel_targets` non-empty (on-need + TTL) | `:264-276` |
| 6 | `DISCARD_CRITICAL` | discardable surplus + quantity ≥ critical | `:205-220` |
| 7 | `CRAFT_RELIEF` | used ≥ `CRAFT_RELIEF_FRACTION` + a relief craft exists | `:221-227` |
| 8 | `RECYCLE_RELIEF` | bank full + recyclable surplus | `:228-239` |
| 9 | `SELL_RELIEF` | bank full + sellable-tradeable now | `:240-243` |
| 10 | `DEPOSIT_FULL` | bank has room + used ≥ `DEPOSIT_FULL_FRACTION` + deposits selected | `:244-250` |
| 11 | `DISCARD_HIGH` | discardable surplus + quantity ≥ high | `:251-259` |

**"Interrupt" is loose for three of them, and the looseness is the point.**
The module docstring (`guards.py:1-2`) says "state-pressure interrupts **+
prerequisite gates**". Rows 2, 3 and 4 are prerequisite gates — they gate a
Fight, they are not pressure. Rows 1, 5-11 are genuine interrupts. The two
leaving are neither: they are *sequencing* guards, which is the plan's own word
(`docs/PLAN_goal_decision_graph_waves_3_6.md:502`) and the correct taxonomy.
**8 interrupts + 3 prerequisite gates + 2 sequencing guards = 13.** Wave 4
touches only the 2. No implementer should read "the eleven interrupt guards" as
licence to reclassify rows 2-4.

---

## 5. The design

### 5.1 Two new nodes

Both live in `ai/decisions/root.py`, beside the existing five, for the reason
that module's docstring already gives (`root.py:16-21`): they are branches of
one graph, only ever constructed by one another, and splitting them across
files would put mutually-referencing halves of a single control-flow structure
behind imports without making any independently usable.

```python
class IsAFightBlockingMe(Decision[MetaGoal]):
    """Is the character held on a fight it cannot win, with nothing else to fight?

    THE STANDING ARM OF `GearLatch`, ABSORBED (wave 4). `gear_latch.py:78`
    computed `craftable and not winnable_alternative and has_combat_deficit(...)`
    and fed it to `ctx.gear_review_active`, which fired the GEAR_REVIEW GUARD —
    and a guard preempts the objective step outright, which is what froze R2D2's
    character XP for 981 cycles / 31.6 h in 2026-08-21/22.

    IT IS A NODE AND NOT A LATCH, AND THAT IS ENFORCED BY THE TYPE. A `Decision`
    is constructed fresh by `resolve_root` every cycle and carries nothing
    across cycles, so this condition cannot become sticky. Do NOT thread
    `prev_level`, `last_outcome`, or any persisted boolean into this signature:
    the moment a node's answer depends on an event N cycles ago, this IS the
    guard again and the freeze is back under a new name. The EDGE arm
    (level-up / `error:fight_lost`) deliberately stays OUTSIDE the graph, in
    `RegearEdge`, where its only job is invalidating the plan cache
    (`should_replan.py:30`).

    `ctx.combat_monster`, not a separate `winnable_alternative` parameter.
    `player.py:1129-1133` computes `_winnable_farm_target()` ONCE and hands the
    same value to `GearLatch.update` and to `_selection_context`, so this is the
    same fact today — but as two parameters they could drift, and the sibling
    node `IsThereACombatTarget` (`root.py:460`) already reads `ctx`. One read.

    `has_craftable_upgrade_any_slot` is NOT re-tested here. In the latch it was
    the AND-guard that stopped the standing arm firing with nothing to build;
    in the graph that job belongs to the child — `WhichSlotClosesTheFight`
    returns None when the deficit chain is empty, and the walk falls through to
    the tier arm. Re-testing it here would be a second, coarser opinion
    (`find_upgrade_target` is monster-BLIND — the ten-hour `iron_boots` failure
    at `combat_deficit.py:35-39`) standing in front of the monster-aware one.
    """

    name = "IsAFightBlockingMe"

    def __init__(self, objective: CharacterObjective, walk: RootWalk) -> None:
        # `objective` is carried, not used, on the positive arm: both children
        # need it (`IsMyGearBehindMyTier` directly, `WhichSlotClosesTheFight`
        # for `classify_target`), and this is the walk's new entry so there is
        # nowhere above it to hold one. Same two-field shape as
        # `IsMyGearBehindMyTier.__init__` (root.py:238-240).
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        if ctx.combat_monster is None and has_combat_deficit(state, game_data):
            return WhichSlotClosesTheFight(self.objective, self.walk)
        return IsMyGearBehindMyTier(self.objective, self.walk)
```

```python
class WhichSlotClosesTheFight(Decision[MetaGoal]):
    """The one acquisition that most improves the margin against the held task's
    monster, per action spent.

    `combat_deficit.deficit_upgrade_target`, ABSORBED (wave 4). It was
    `map_guard`'s GEAR_REVIEW branch (`strategy_driver.py:382-383`), the only
    link the bot has between "I cannot win this fight" and "build this". Its
    predecessor was a monster-BLIND `_best_by_value` scan that chose
    `iron_boots` — already worn, absent from all 24 items that improved the pig
    margin — while the weapon that moved `rounds_to_kill` went unbuilt for ten
    hours (`combat_deficit.py:35-39`).

    THIS IS NOT A FIFTH RANKING MULTIPLIER AND NOT A NEW ARGMAX. It adds no
    scoring surface at all: `combat_deficit`'s greedy walk already exists, is
    already called in production, is already ranked on `margin gain per
    acquisition action` (`combat_deficit.py:268-279`), and `max_chain=1` takes
    its FIRST step. Wave 4 changes WHERE it is called, not WHAT it computes.
    The wave-3 precedent (`WhichSlotIsFurthestBehind`, spec §8 R2) applies here
    verbatim: no multiplier may be added to this ranking. If a future need
    appears to weight this against the tier gap, that is a request for a fifth
    multiplier and must be refused — the two are in DIFFERENT ARMS of a branch,
    never summed, and that is exactly why neither needs a scale.

    Returns None — the honest wall — when the deficit chain is empty. That is
    `combat_deficit`'s own "unwinnable and I do not know what to build" case
    (`CombatDeficit.closes`, `combat_deficit.py:95-98`), and the parent falls
    through to the tier arm rather than inventing a root. NOTE this makes the
    node's contract `Decision | MetaGoal | None` and NOT the narrowed
    `ObtainItem | ReachSkillLevel` of `IsThisTargetBlocked`.
    """

    name = "WhichSlotClosesTheFight"

    def __init__(self, objective: CharacterObjective, walk: RootWalk) -> None:
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)

        def cost_of(code: str) -> float:
            return float(acquisition_actions(code, 1, state, game_data, ctx,
                                             equip=True, store=history))

        target = deficit_upgrade_target(state, game_data, cost_of=cost_of)
        if target is None:
            return IsMyGearBehindMyTier(self.objective, self.walk)
        code, slot = target
        return IsThisTargetBlocked(
            slot, self.objective.classify_target(code, state), self.walk)
```

**Three details in that last line, each load-bearing.**

1. It **reuses `IsThisTargetBlocked`** (`root.py:372-437`) rather than mapping
   the code to a goal itself. That is the whole economy of the design: the
   deficit chain then gets the *same* skill-gate / material-gate routing the
   tier sheet gets. `combat_deficit`'s own docstring
   (`combat_deficit.py:26`) states the layering it needs —
   `fight deficit ← gear deficit ← skill deficit ← material deficit` — and
   `IsThisTargetBlocked` is the node that already implements exactly that
   descent. `map_guard`'s hand-rolled tail does not: it emits
   `UpgradeEquipmentGoal` or `GatherMaterialsGoal` and has no skill arm at all,
   so a skill-gated deficit step routes to gathering materials for a craft the
   character cannot perform — the identical defect wave-1/2 Task 5 fixed one
   layer up (`docs/PLAN_goal_decision_graph.md:1040-1042`).

2. `_classify_target` must be **promoted from private to public** on
   `CharacterObjective` (`objective.py:439`, currently `_classify_target`).
   It is already the single producer of every `GearTarget`
   (`root.py:376-377`) and this is its second consumer. Renaming it
   `classify_target` in the same commit as the new caller is a one-line change
   with one existing call site (`objective.py:436`).

3. `DeficitStep.crafting_skill` / `crafting_level`
   (`combat_deficit.py:79-80`) are **not** read here. `_classify_target`
   re-derives the gate from `game_data.item_stats` and live `state.skills`,
   which is the same rule `IsThisTargetBlocked` uses for the tier sheet
   (`root.py:414-422`: `current + 1`, re-derived every cycle, never the whole
   climb). Two producers of "what skill gates this" would drift; there is one.

### 5.2 The graph after wave 4

```
IsAFightBlockingMe                     ctx.combat_monster is None
  |                                    AND has_combat_deficit(state, game_data)
  |-- yes -> WhichSlotClosesTheFight
  |            |-- chain non-empty -> IsThisTargetBlocked(slot, target)   [existing]
  |            `-- chain empty     -> IsMyGearBehindMyTier                [existing]
  `-- no  -> IsMyGearBehindMyTier                                         [existing]

IsMyGearBehindMyTier ... CanIClearMyTier                       unchanged, root.py:227-487
```

Seven nodes. Two new edges out of each new node. `resolve_root`'s entry
(`root.py:498`) becomes `IsAFightBlockingMe(objective, walk)`.

`RootResolution.alternatives` is **unchanged**: `walk.sibling_targets` is only
ever written by `WhichSlotIsFurthestBehind` (`root.py:302`), and when the
fight arm wins that node never runs, so `alternatives` is
`[ReachCharLevel(milestone_pure(state.level))]` — the trunk alone. That is
correct and deliberate: a character blocked on a fight it cannot win has
exactly one alternative, which is to level. Do **not** add the tier sheet as a
sibling list here; that would re-create a ranking between two arms of a branch.

### 5.3 Why the fight arm goes ABOVE the tier arm — and why that is not the freeze

The obvious objection: putting a blocked-task question in front of the whole
tier climb is the shape that froze R2D2. It is not, for three reasons that must
all hold:

1. **`ctx.combat_monster is None` is in the condition.** The freeze was
   `GEAR_REVIEW` preempting `GrindCharacterXP(skeleton)` — a *winnable
   alternative*. With this clause, the arm cannot fire while anything is
   fightable. And unlike the latch, it reads the **same** `ctx.combat_monster`
   the sibling `IsThereACombatTarget` reads (`root.py:460`), so the two cannot
   disagree about whether a fight exists.
2. **It is recomputed every cycle** and there is nowhere to cache it (§3.2).
3. **It no longer preempts.** Post-wave-4 the answer is a *root*, at
   `BAND_STEP`, not a guard at `BAND_GUARD`. The eleven interrupts, the whole
   `COLLECT_REWARD_ORDER` band, and `EquipOwnedGear` all still precede it.
   That is a strict reduction in the condition's authority even though it moves
   earlier *within* the walk.

The alternative placement — below `IsMyGearBehindMyTier` — was considered and
rejected: `gear_targets_with_blockers` returns non-empty in **28 of 30
scenarios** (measured), so the fight arm would be unreachable in 28/30 and the
absorbed `deficit_upgrade_target` would be dead on arrival. That is the
`justifying_identities` / raid-pole failure mode, and this epic has now hit it
three times.

### 5.4 Deletion list, with a consumer count for each row

| item | file:line | production consumers | note |
|---|---|---|---|
| `GuardKind.GEAR_REVIEW` | `guards.py:86`, `:109` | 4 (§2.3) | see §7 before deleting the enum member |
| `guards._fires` GEAR_REVIEW arm | `guards.py:260-261` | 1 | |
| `map_guard` GEAR_REVIEW branch | `strategy_driver.py:355-405` | 1 (`:1209`) | 51 lines; `:390-405` is a duplicate of `_equippable_goal` (`obtain_item_routing.py:174-265`) |
| `_materials_in_hand` | `strategy_driver.py:242-248` | **1 — the GEAR_REVIEW branch only** (`:391`) | dies with it; grep before deleting |
| `strategy_driver`'s import of `_gather_goal_for_unreachable_equippable` | `:75`, used `:402` | 1 | after this, `obtain_item_routing.py:12-13`'s comment is stale and must be updated in the same commit |
| `SelectionContext.gear_review_active` | `selection_context.py:73` | 1 (`player.py:3734`) | plus ~14 test fixtures |
| `GearLatch.active` / `_blocked` / `winnable_alternative` | `gear_latch.py:29-31`, `:78-79`, `:34` | 1 | the `_active` arm and `update` SURVIVE |
| `combat_deficit.deficit_upgrade_target` | `combat_deficit.py:164-211` | 1 (`strategy_driver.py:382`) | **MOVES, does not die** — the node calls it |
| `has_combat_deficit` | `combat_deficit.py:146-161` | 1 (`gear_latch.py:79`) | **MOVES, does not die** |
| `decide_key._GUARD_REPR[GEAR_REVIEW]` | `decide_key.py:51` | 1 | with its Lean mirror |

**Nothing about `CRAFT_POTIONS` is on this list.** §6.

### 5.5 Migration order

Five increments. Each leaves `bash formal/gate.sh` green.

| # | what | why here |
|---|---|---|
| **4.0** | **Scenarios first.** Add ≥3 scenarios carrying a workable `monsters` task: one unwinnable-with-a-closing-chain, one unwinnable-with-no-closing-chain, one unwinnable-but-with-a-winnable-alternative (`ctx.combat_monster` set). Assert against **today's** `GearLatch`/`map_guard` behaviour. | Without this every later assertion is vacuous (§0.6). Doing it first means the increment-4.2 diff is against recorded numbers, not against nothing |
| **4.1** | Promote `_classify_target` → `classify_target` (`objective.py:439`), one call site | Isolated rename, mechanically verifiable |
| **4.2** | Add `IsAFightBlockingMe` + `WhichSlotClosesTheFight`, wire `resolve_root`'s entry, delete the guard rung, `ctx.gear_review_active`, `GearLatch._blocked`, and `map_guard`'s branch | **The behaviour change.** One commit, because a graph with the node AND the guard is two producers of the same decision |
| **4.3** | Narrow `GearLatch` → `RegearEdge` (edge arm + `should_replan` + `save_plan_commitment` only) | Pure rename after 4.2 removed the other consumer |
| **4.4** | Lean + oracle: retire `gearReview` from the ladder, restate `D`/`E`/`F` measures, renumber `DecideKey` | §7. Separable and mechanical, and it must NOT be interleaved with 4.2 — a measure restatement mixed with a behaviour change is unreviewable |

Increment 4.2 is the only one that can change what a live character does.

---

## 6. `CRAFT_POTIONS`, and the potion route

### 6.1 Recommendation: KEEP the rung, in `GUARD_ORDER`, unchanged

This is a departure from the brief (`docs/PLAN_goal_decision_graph_waves_3_6.md:507`,
parent spec `:401`), stated loudly as required. Four arguments, in decreasing
strength.

**(a) Measured — demotion is deletion.** `CRAFT_POTIONS` sits last in
`GUARD_ORDER` (`guards.py:110`) but still in `BAND_GUARD`. If it becomes
anything below the objective step, it inherits the fate of the rung that
already does that job: `MeansKind.MAINTAIN_CONSUMABLES` (`means.py:121`,
`:197`, `DISCRETIONARY_ORDER`) fired and won **3 times in 78,552 cycles**.
`CRAFT_POTIONS` fired and won **2,245**. The `BAND_RAID` renumber
(`arbiter_select.py:41-60`, wave-3a fix-round 1) exists because the same
mistake was made with `ParticipateRaidGoal`: *"a timed bonus that yields to a
step present in 14,064 of 14,064 cycles is one that expires unused"*. Making
that mistake a third time, knowingly, with the numbers in hand, would be
indefensible.

**(b) `ObtainItem` cannot express a consumable target.** `ObtainItem.is_satisfied`'s
slot arm is `state.equipment.get(self.slot) == self.code`
(`meta_goal.py:56-58`) — **quantity-blind**. A potion root would be satisfied by
one potion against `potion_baseline_pure`'s level-scaled target (up to
`POTION_HIGH_QTY`). Fixing that means changing `ObtainItem.is_satisfied`, which
is the satisfaction rule for **every** gear root in the graph and behind
20,829 live `UpgradeEquipment*` cycles. That is not a wave-4-shaped change.

**(c) A consumable has no honest rung on the ladder.** `_tier_gap`
(`root.py:193-207`) is defined in ladder rungs via `_target_rung` →
`tier_of_level(stats.level)`. Utility potions are **level-exempt by design** —
`objective.py:474`: *"judged by EFFECT not level (potions are
level-exempt)"* — so `stats.level` is not a rung for them and
`WhichSlotIsFurthestBehind`'s key would be comparing a level-1 potion's
"gap" against an iron shield's. That is two unrelated scales in one column,
which is the precise defect wave 3 deleted (`root.py:6-8`).

**(d) The exclusion is deliberate and documented.** Potions are absent from
the walk because `_gear_candidates_by_type` skips `stats.type_ == "utility"` at
**`objective.py:102`**. That is the mechanism — not an oversight in wave 3a —
and it dates to `has_structural_upgrade`'s rule that *consumable restock must
never break adequacy* (quoted at `tests/…/test_slot_coverage.py:885-891`).
Re-opening it re-opens GAP-4's original question with a worse ruler than the
one that answered it.

**What the guard rung is sufficient for.** Provisioning the equipped utility
slots to a combat-justified baseline: `craft_potions_fires` is a **standing**
predicate (recomputed each cycle, releases the moment `equipped >= baseline`),
it self-quiets, and its longest observed run is 69 cycles — bounded by the
crafting work, not by a latch. It is not the freeze shape. It has no live
failure on record.

### 6.2 Correcting a claim wave 3a made

Wave-3a task-6 report §7.4 and `test_slot_coverage.py:907-911` both reassure
that *"Provisioning survives only through the arbiter's own guard rungs
(`MaintainConsumables` / the combat-justified CRAFT_POTIONS rung)"*. Two
things are wrong with that sentence and both should be fixed when wave 4
touches these comments:

* `MaintainConsumablesGoal` and `CraftPotionsGoal` do **different jobs**.
  `consumable_supply.py:1-15` + `HEAL_STOCK_FLOOR = 5` (`:24`) is about
  **inventory** heals to drink mid-fight; `craft_potions_fires` is about
  **equipped utility-slot** quantity. Neither substitutes for the other.
* `MaintainConsumables` fired **3 times in 78,552 cycles**. Naming it as a
  surviving safety net overstates the net by three orders of magnitude.

There is a third potion pathway neither document names: `EquipOwnedGear` at
`BAND_COLLECT` fills utility slots from already-owned potions — **92 live
cycles**, e.g. `EquipOwnedGear([('utility1_slot', 'air_boost_potion')])`. It
equips; it does not acquire.

### 6.3 So the potion route DOES return — through the fight arm, and only there

`combat_deficit._pool` (`combat_deficit.py:115-119`) admits every item whose
`type_` is in `ITEM_TYPE_TO_SLOTS` at or below the character's level, and
`"utility"` is in that map (`gear_taxonomy.ITEM_TYPE_TO_SLOTS['utility'] ==
['utility1_slot', 'utility2_slot']`). The module docstring's own live example
(`combat_deficit.py:22`) is C3P0's real chain: `iron_sword → iron_armor →
**earth_boost_potion** → earth_ring`.

So `WhichSlotClosesTheFight` can already return a potion, and
`IsThisTargetBlocked` will route it (potions have recipes and skill gates like
anything else). **A potion becomes a decision root exactly when a potion is
what closes a fight the character is blocked on — and never as a tier-ladder
gear target.** That is the honest, narrow restoration, it costs nothing to
build, and it is a *better* answer than the pre-wave-3a one: the old
`_utility_candidates` route put potions on the surface ranked by
`pursuit_value` against gear, and lost that argmax 100 % of the time by design
(GAP-4).

It should be pinned. `test_slot_coverage.py:885` and `:922` are the two tests
wave 3a renamed to assert the absence; wave 4 should add a **third** test in
the same file asserting the presence: a scenario whose blocked task monster is
closed by a boost potion resolves to `ObtainItem(<boost>, slot='utility1_slot')`
with trail `IsAFightBlockingMe → WhichSlotClosesTheFight → IsThisTargetBlocked`.
That scenario is one of increment 4.0's deliverables.

---

## 7. The Lean and oracle cost — wave 4's biggest difference from wave 3

Wave 3's design could open with *"No Lean theorem breaks in wave 3"* (§0.3)
because both meta-decision-dependent `ExtMeasure` slots were **deliberately
excluded** from `FMeasure`. That does not hold here.

`FMeasure.lean:29` — the slot table:

```
| 9  | `craftPotionsFlag` | craftPotions | nothing in-model |
| 10 | `gearReviewFlag`   | gearReview   | nothing in-model |
```

Both are fields of the 16-slot structure (`FMeasure.lean:87`), populated from
`s.gearReviewFires` / `s.craftPotionsFires` (`:135`), and appear in the lex
comparison chain at `:204`, `:214`, `:225`, `:237`, `:250`, `:264`, `:279`.
`FMeasure` is the measure carrying `ai_reaches_fifty_unconditional`.

Retiring `GEAR_REVIEW` from `GUARD_ORDER` therefore requires, at minimum:

| file | what |
|---|---|
| `FMeasure.lean` | drop slot 10; every `hN` hypothesis below it renumbers |
| `EMeasure.lean` `:16/55/62/67/70/98/131/433/461` | same for `gearReviewFlag` at slot 19 |
| `DMeasure.lean` `:71/112/142/375/396/419/446/474/504` | same |
| `BlockerDescent.lean:313-318` | `gearReview_descends` — deleted |
| `BlockerDescentD.lean:102`, `:514`; `BlockerDescentE.lean:222/228/306/322/891/920` | refresh-invariance + per-means descent rows |
| `BlockerMonotone.lean:109-140` | 5 `gearReviewFires_false_*` theorems + `gearReview_quiet_forever` |
| `BlockerQuieting.lean:82-88` | `gearReview` dispatch-clears lemma |
| `CycleStepDC.lean:342-356`, `CycleStepE.lean:158`, `LadderEval.lean:78` | model transitions setting/clearing the flag |
| `DecideKey.lean:50`, `:113` | inductive member + `goalReprOfGuard` arm |
| `Oracle.lean:1183` (and `:1190` if potions go too), `:2438`, `:2502`, `:2552`, `:2621` | index dispatch + arg-vector slots [26]/[32] |
| `formal/diff/test_decide_key_diff.py:27-40` | `_GUARD_INDEX` |
| `formal/diff/test_ladder_fires_diff.py:217`, `:277`, `:460`, `:806`, `:930` | `LadderMeans` map, scenario field, arg vector |

**The renumber is the trap.** `GEAR_REVIEW` is index **8** and
`CRAFT_POTIONS` index **11** of thirteen (`test_decide_key_diff.py:26-40`,
mirrored `DecideKey.lean:43-56`, dispatched `Oracle.lean:1178-1191`). Removing
index 8 shifts `recycleRelief` 9→8, `sellRelief` 10→9, `craftPotions` 11→10,
`geCancel` 12→11. `DecideKey.lean:38-42` explicitly records that variants were
**appended last so the indices stay stable** — this codebase has an
append-only discipline for exactly this reason, and wave 4 would be the first
change to violate it.

**Recommendation.** Delete the `GuardKind.GEAR_REVIEW` **rung** (its
`GUARD_ORDER` entry, `_fires` arm and `map_guard` branch) in increment 4.2, but
**delete the enum member and its Lean mirror last, in 4.4, as its own commit**,
and take the renumber deliberately rather than by side effect. Do not attempt
to preserve index stability by leaving a dead variant in place: a `GuardKind`
member that no ladder contains and no `_fires` arm answers is exactly the
kind of proof-inert residue `feedback_gate_green_does_not_pin_a_constant`
warns about.

I did **not** attempt the Lean edit and I did not run `lake build`. The table
above is a read of the call sites, not a compiled verification; treat the size
as an estimate and the *list* as the checked claim.

---

## 8. Obligations wave 4 owes, and what makes each vacuous

Wave 3 shipped O1 (`src/artifactsmmo_cli/audit/open_rung_completeness.py`) and
O2 (`tests/test_ai/test_decisions_dag.py`). Wave 4 touches both and adds one.

### O2 (inherited) — the graph is still acyclic

`test_decisions_dag.py` enumerates `Decision` subclasses under `ai/decisions/`
and reads each class's AST for calls naming another swept class
(`:57-86`). The new edges are `IsAFightBlockingMe → {WhichSlotClosesTheFight,
IsMyGearBehindMyTier}` and `WhichSlotClosesTheFight → {IsThisTargetBlocked,
IsMyGearBehindMyTier}`. Neither closes a cycle: `IsThisTargetBlocked` has no
`Decision` children (`root.py:392-400`) and `IsMyGearBehindMyTier` is not an
ancestor of either new node.

**Required edits:** `_MIN_CLASSES` 11 → 13 and `_MIN_EDGES` 9 → 13
(`test_decisions_dag.py:39-40`), plus a named pin for
`edges["IsAFightBlockingMe"]` beside the existing one at `:127-128`.

**What makes O2 vacuous.** `static_child_edges` parses
`inspect.getsource(cls)` — the **class body only**. `resolve_root`'s
module-level sibling conversion already constructs `IsThisTargetBlocked`
(`root.py:505`) and that edge is **invisible to the sweep**. If wave 4 puts
the deficit→`IsThisTargetBlocked` conversion in a module-level helper instead
of inside `WhichSlotClosesTheFight.resolve`, the edge vanishes from the
relation and O2 certifies a graph that is missing it. Keep every construction
inside a class body, and if the floors are raised without the named pin, a
sweep that goes blind still passes. (The existing test's own §12-20 docstring
anticipates this; wave 4 must not weaken it.)

### O1 (inherited) — and it is INERT for wave 4 unless 4.0 lands

`open_rung_completeness.routed_skills` (`:248-265`) drives `resolve_root`
whole. Adding a node above the entry therefore *can* change the routed set —
but **measurably does not**, because the arm never fires offline: 0/30
scenarios have a task, so `has_combat_deficit` is `False` in every cell, and
`NO_PROFILE_CONTEXT` makes `ctx.combat_monster` `None` in every cell too.

Two consequences, both must be stated in the wave-4 report:

* Re-running O1 unchanged after wave 4 and finding it green proves **nothing
  about wave 4**. The census's own honesty note already limits it to 19 of 240
  routed cells (spec §3.5); wave 4 adds zero.
* Once increment 4.0 adds task-carrying scenarios, O1's routed set **will**
  widen — a skill-gated deficit step routes to `ReachSkillLevel(S, C+1)`
  through the reused `IsThisTargetBlocked`, and `classify_gap` tests `routed`
  **before** any wall arm (`:329`), so a closed cell in that skill becomes
  `O1_SILENT_STALL` and the gate goes red. That is the census working. Budget
  for it; do not treat it as a wave-4 regression.

One trap in 4.0: a scenario that adds a task **without** also setting
`ctx.combat_monster` makes `IsAFightBlockingMe`'s `ctx.combat_monster is None`
clause true, so the arm fires in every such cell. The third scenario in
increment 4.0 exists precisely to pin the negative case.

### O3 (new) — one gear-review producer, not two

**The obligation.** After wave 4, exactly one code path answers "should this
character be building gear because of a fight it cannot win". Today there are
two and they disagree: the guard's monster-aware `deficit_upgrade_target` and
the graph's tier-driven `gear_targets_with_blockers`.

**The discharge.** A test asserting that `deficit_upgrade_target` has **zero**
callers outside `ai/decisions/root.py` and its own tests, and that
`GuardKind` contains no member whose `map_guard` arm constructs an
`UpgradeEquipmentGoal`. Both are greps expressed as assertions — the shape
`feedback_proof_over_an_uncalled_helper` recommends after
`distance_cost_pure` shipped with a Lean proof and no production caller.

**What makes O3 vacuous.** Asserting "zero callers" of a function that also
has zero *tests* would pass over an empty set. The assertion must be paired
with a positive one: `WhichSlotClosesTheFight` is on the trail of at least one
scenario, and that scenario's `chosen_root` is the deficit chain's first step.
Which requires 4.0. Again.

### O4 (new) — the standing condition is not sticky, proven by exhibition

**The obligation.** The incident's rule, discharged mechanically rather than by
docstring: two consecutive `resolve_root` calls whose only difference is that
`ctx.combat_monster` became non-`None` must produce different roots, with no
persisted state in between.

**The discharge.** Drive `resolve_root` twice over the *same* `WorldState`
object with two `SelectionContext`s differing only in `combat_monster`; assert
`IsAFightBlockingMe` is on both trails, `WhichSlotClosesTheFight` only on the
first, and the second root is not the deficit target. Then **mutate** the node
body to cache its verdict on `self` and assert the test fails.

**What makes O4 vacuous.** Constructing two fresh `resolve_root` calls always
passes trivially, because `resolve_root` builds new nodes each time
(`root.py:494-500`) — the test would be asserting a property of the harness,
not of the node. It only bites if the mutation step is part of the obligation:
the recorded evidence must be *"here is the caching mutant, here is the test
output showing it killed"*, not *"the test passes"*. This repo has shipped ten
decorative tests in this epic; a named guard test that does not kill its mutant
is the failure mode
(`project_supply_claim_and_batch`: *"never name one, say 'find the test that
fails under X'"*).

### O5 (new, small) — the replan trigger survived

**The obligation.** `should_replan`'s latch-edge arm (`should_replan.py:30`)
still fires after `GearLatch` narrows to `RegearEdge`.

**The discharge.** `tests/test_ai/test_plan_or_reuse.py` already sets
`player._gear_latch._active` directly (`:35`, `:79`); those tests must be
updated in increment 4.3 and must still assert a replan on the edge, not merely
compile. **Vacuous if** the field is renamed and the tests are updated to set
the new name without anyone checking the assertion still discriminates —
mutate `should_replan.py:30` to `if False:` and confirm a test fails.

---

## 9. Risks, and what I could not determine

Same shape as wave-3 design §8.

### 9.1 Risks

**R1 — `WhichSlotClosesTheFight` costs 386 ms per firing and the walk runs
every cycle.** `map_guard`'s own comment (`strategy_driver.py:377-379`)
measures the priced `deficit_upgrade_target` at **386 ms on live C3P0** against
a ~70 s cycle — acceptable *as a guard*, which only ran when the latch was
armed. In the graph the parent node gates it on `ctx.combat_monster is None
and has_combat_deficit(...)`, which is **one `predict_win`**
(`combat_deficit.py:160-161`) and is False in 80.6 % of live cycles (the
inverse of the 19.4 % holding a workable monsters task) — so the expensive walk
is still gated. **But `resolve_root` is also called by
`audit/open_rung_completeness.routed_skills` once per (scenario, skill) cell,
240 cells**, and by the plan pane. Mitigation: increment 4.2 must record
`decide_tree` wall-clock over the scenario set before and after. `J`'s
33.9 s-vs-300 ms surprise (`project_objective_cli_diagnostic`) is the precedent.
**Reasoned, not measured** — I did not time it.

**R2 — a live behaviour change with no offline coverage.** Increment 4.2
changes what a blocked character does, and today the change is invisible to
every test in the repo (0/30 scenarios can reach it). Mitigation is increment
4.0 and the ordering that puts it first. This is R3 of the wave-3 design
repeating (`gear_targets_with_blockers`: 5 tests, 0 production callers) and it
is the reason 4.0 is not optional.

**R3 — the fight arm can starve the tier climb in a way the latch could not.**
The latch's standing arm required `has_craftable_upgrade_any_slot`; the node
deliberately does not (§5.1). If `deficit_upgrade_target` returns a target the
planner cannot serve, the arm fires every cycle, `_servable_promotion`
(`progression_tree.py:518-522`) demotes it, and the walk falls to
`alternatives` — which, per §5.2, is the trunk alone. That is a *survivable*
degradation (the character levels) but it is strictly narrower than the tier
sheet the old path would have offered. Mitigation: increment 4.0's
"unwinnable-with-no-closing-chain" scenario must assert the fall-through
reaches the tier arm, i.e. that `WhichSlotClosesTheFight` returning `None`
routes to `IsMyGearBehindMyTier` and not to the trunk.

**R4 — `combat_deficit`'s `max_chain=1` is a one-step view of a multi-step
problem.** `deficit_upgrade_target` calls `combat_deficit(..., max_chain=1)`
(`combat_deficit.py:197-198`), so the root is the chain's *first* step,
re-derived each cycle. That is the right shape (same rule as
`IsThisTargetBlocked`'s `current + 1`) but it means the graph never *shows* the
four-step chain the USER's ruling was about
(`combat_deficit.py:30-33`). Nothing regresses; the plan pane just cannot
display the plan. Flagged, not fixed.

**R5 — the Lean renumber may cascade further than §7's table.** I read the
call sites; I did not build. `EMeasure`/`DMeasure`/`FMeasure` descent lemmas
carry positional hypothesis names (`h15`, `h22`) that renumber with the slot,
and I did not enumerate every one.

**R6 — deleting `_materials_in_hand` (`strategy_driver.py:242-248`).** Its
only caller is the GEAR_REVIEW branch (`:391`). It looks safe and it is on the
deletion list — but `feedback_no_alphabetical_tiebreak`'s sibling lesson
applies (`project_ge_and_sibling_routes`: an unguarded fallthrough), so re-grep
at deletion time rather than trusting this table.

### 9.2 What I could not determine

**U1 — whether the 981-cycle figure is reproducible from `learning.db`.** It
is not, from what is there: the longest consecutive `UpgradeEquipment*` run in
the whole 78,552-cycle window is 187 (R2D2), and consecutive-run counting is
broken by any interleaved `RestoreHP`. The 981 figure is from
`gear_latch.py:64-70`'s own comment. I trust the comment; I could not
independently confirm it, and I did not use it as a number anywhere a decision
rests on.

**U2 — whether `GEAR_REVIEW` or the objective step produced the 20,829 live
`UpgradeEquipment*` cycles.** Both produce the same repr and `cycles` records
no guard/means discriminator. `plan_commitment.latch_active` is a single
current-value row per character, not a history. So I cannot say how much of the
26.5 % is the guard. Everywhere the figure appears I have said so. **A
one-column addition to the `cycles` table (`selected_band` or
`selected_kind`) would settle this permanently and is worth proposing
independently of wave 4.**

**U3 — whether removing the `craftPotionsFires` / `gearReviewFires` State
fields is even required, or only the ladder rows.** `perceptionRefreshE`
already treats `craftPotionsFires` as invariant
(`BlockerDescentE.lean:138-139`), which hints a flag can exist in the model
without a rung. If so, §7's cost is smaller than stated. I did not read enough
of `CycleStepF` to tell, and I did not build.

**U4 — the CPU cost of `resolve_root` after wave 4 (see R1).** Not measured.

**U5 — whether `EquipOwnedGear`'s 92 utility-slot cycles overlap the
`CraftPotionsGoal` 2,245.** Both are potion pathways; I counted them
separately and did not check whether one predominantly follows the other. It
does not change any recommendation here.

### 9.3 Which claims are measured and which are reasoned

**Measured** (offline sweep over `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`,
or `learning.db`): every figure in §2.6; 0/30 scenarios with a task; 30/30
`has_combat_deficit == False`; 30/30 `deficit_upgrade_target is None`; 30/30
`has_craftable_upgrade_any_slot == True`; 28/30 `gear_targets_with_blockers`
non-empty; 3/30 `craft_potions_fires == True`; 2/30 scenarios resolving to the
`None` wall (`l48_band_adequate`, `l48_raid_active`); R2D2's 3,095-cycle pig
window and its 396 `GrindCharacterXP(skeleton)` cycles.

**Reasoned from the code, not measured**: every claim in §7 about the Lean
cost; R1's assertion that the expensive walk stays gated; §5.3's argument that
the fight arm cannot re-create the freeze; §6.1(b)'s claim that a potion root
would be prematurely satisfied (read from `meta_goal.py:56-58`, not exhibited).

**Quoted from existing comments, and inherited rather than confirmed**: the
386 ms `deficit_upgrade_target` timing; the 981-cycle / 31.6 h freeze; the
ten-hour `iron_boots` failure; the 42-loss C3P0 countdown.

---

## 10. Task breakdown for the wave-4 implementation plan

| task | files | gate |
|---|---|---|
| **4.0** scenarios | `ai/scenario.py` (+3 `ScenarioCharacter`s with `task=(...)`), `tests/test_ai/scenarios/test_slot_coverage.py` | new tests assert **today's** behaviour; `bash formal/gate.sh` green |
| **4.1** `classify_target` | `tiers/objective.py:436`, `:439` | rename only |
| **4.2** the nodes | `ai/decisions/root.py` (+2 classes, entry change), `tiers/guards.py` (−`GEAR_REVIEW` rung), `ai/strategy_driver.py` (−`:355-405`, −`:242-248`), `ai/selection_context.py:73`, `ai/gear_latch.py` (−`_blocked`), `ai/player.py:3734`, ~14 test fixtures | O2 floors raised + named pin; O3; O4 with its mutant; the 4.0 scenarios flip to the new expected behaviour |
| **4.3** `RegearEdge` | `ai/gear_latch.py` → renamed module, `ai/player.py:345/811/821/832/1020/1132`, `tests/test_ai/test_plan_or_reuse.py`, `test_player_gear_latch.py`, `test_gear_latch.py` | O5 with its mutant |
| **4.4** Lean + oracle | the §7 table | `bash formal/gate.sh`; `#print axioms` unchanged |

Live acceptance, from `~/.cache/artifactsmmo/learning.db` only: after the fleet
restarts on the flipped code, no character selects an `UpgradeEquipment*` for
more than 200 consecutive cycles while holding a monsters task whose monster is
unwinnable and while a winnable alternative exists. Baseline 2026-08-23,
PRE-flip: R2D2 187, Lor 157, HAL 109, Robby 88, C3P0 37.

---

**Nothing in this document is authorised for implementation.** It is the design
task's deliverable; the implementation plan argues from it and the controller
approves that.
