# Goal/Decision graph: unifying the meta-decision layer

Date: 2026-08-22
Status: approved design, waves 1-2 authorised for implementation; waves 3-6 specified but not authorised
Related: `docs/PLAN_unified_acquisition_objective.md`, `docs/LEVEL_FIFTY_RESIDUALS.md`,
`docs/PLAN_boss_achievement_progression.md`

## 1. Problem

The domain is a dependency chain. Character level depends on clearing a content
tier, clearing a tier depends on gear adequate to that tier, that gear depends on
craft-skill level, and craft-skill level depends on materials. The architecture
models this as a flat competition among sibling roots scored by a number.

`StrategyDriver.decide()` returns a `ranking` in which `ReachCharLevel(30)` scores
`1.0` and `ObtainItem(lich_race_trophy, artifact3_slot)` scores `1.19e9`. Those are
not comparable quantities. The unified objective `J` that was meant to make them
comparable has never produced a finite value in production — `j: null` on all
twelve roots as of 2026-08-22 — so the live decision key is `cost`, the trunk's
cost is zero, and the trunk wins unconditionally.

Because a score cannot express "gear before level", that ordering moved into a
second arbitration mechanism: the guard band. Two of the thirteen guard kinds,
`GEAR_REVIEW` and `CRAFT_POTIONS`, are not interrupts at all. They exist solely to
force a prerequisite ahead of the objective step. A guard is unbounded
preemption, which is how R2D2 spent 31.6 hours at zero character XP.

The generator of this defect class is that **meta-decisions are implicit**. They
live as control flow inside `strategy_driver.objective_step_goal`, a 145-line
`if`-pile, and as multiplier terms inside the ranking. Neither form can be
inspected, tested, or reasoned about as a decision.

### 1.1 The concrete failure this design was derived from

`objective_step_goal` at `src/artifactsmmo_cli/ai/strategy_driver.py:972-976`:

```python
if (root_stats is not None and root_stats.crafting_skill
        and state.skills.get(root_stats.crafting_skill, 1)
        < root_stats.crafting_level):
    return GatherMaterialsGoal(target_item=step.code,
                               needed={step.code: step.quantity})
```

Read as a decision, this is `Can_I_Craft_Current_Tier`. Its "no" branch routes to
*gather the materials anyway*. It should recurse to *raise the skill*.

That single mis-wired edge is the entire weaponcrafting freeze. It was invisible
because the decision was never declared as a node — no test, census, or reviewer
had an object to look at.

## 2. Evidence

All figures measured against live state and `~/.cache/artifactsmmo/learning.db`
on 2026-08-22. Trace files are explicitly not used; they are deleted periodically
and are not a reliable basis for durable claims.

### 2.1 Weaponcrafting is frozen fleet-wide

`LevelSkill(weaponcrafting->N)` ran 11,434 times, then stopped:

| character | actions | last run | weaponcrafting |
|---|---|---|---|
| HAL | 3923 | 2026-08-16T09:00 | 10 |
| Lor | 3812 | 2026-08-16T22:34 | 10 |
| R2D2 | 3260 | 2026-08-16T22:17 | 10 |
| C3P0 | 439 | 2026-08-20T01:33 | 6 |
| Robby | 0 | never | 10 |

11,026 of the 11,434 targeted level 10. The rung never once targeted 11 or above.
By contrast, `LevelSkill(woodcutting->20)` advanced its own target to `->30` on
reaching 20.

The action is not at fault: `has_grind_target('weaponcrafting')` is `True` for
Robby with eight obtainable, XP-positive rungs open at level 10, and
`skill_grind_target` returns `iron_dagger`. Nothing demands the skill, so nothing
selects it.

### 2.2 The demand path is structurally absent

`objective.near_term_gear(state)` never proposes a `weapon_slot` target. For
Robby it returns `{artifact1, artifact2, artifact3, boots}`. The reason is that
`_slot_assignments` picks the highest-value **attainable-now** weapon, which is
`battlestaff` — the item he is already wearing.

Eight weapons have strictly positive marginal winnability and large positive
value gain, and every one fails `is_attainable_now`:

| weapon | level | craft gate | marginal winnability | value gain |
|---|---|---|---|---|
| greater_dreadful_staff | 30 | weaponcrafting 30 | 6 | +1.64e9 |
| elderwood_staff | 30 | weaponcrafting 30 | 6 | +1.64e9 |
| death_knight_sword | 30 | none | 5 | +1.68e9 |
| gold_sword | 30 | weaponcrafting 30 | 5 | +1.64e9 |
| perfect_bow | 30 | weaponcrafting 30 | 5 | +1.56e9 |
| obsidian_battleaxe | 30 | weaponcrafting 30 | 4 | +1.64e9 |
| dreadful_staff | 25 | weaponcrafting 25 | 2 | +4.1e8 |
| skull_wand | 25 | weaponcrafting 25 | 1 | +4.1e8 |

Unattainability deletes the candidate instead of emitting the blocker as work.
The same shape appears at five sites: `near_term_gear`'s `is_attainable_now`
filter, `skill_grind_target`'s `_obtainable` filter, `obtain_sources`' `10**6`
sentinel, `objective_step_goal`'s skill-gated branch, and
`cheapest_path_to_level`'s `blocked=True, total_cycles=inf`.

### 2.3 Gear lag, and the absence of any mechanism that measures it

Every equippable item in the game sits on one of eleven levels. Craft
breakpoints use the same eleven values.

```
LADDER = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
```

Against that ladder:

Taking the naive tier for a character's level — `max(t in LADDER if t <= level)`,
which section 3.5 later corrects — the lag is:

| character | level | naive tier | slots below it | worn item levels |
|---|---|---|---|---|
| Robby | 30 | T30 | 10 of 10 | 10,10,10,15,15,20,20,25,25,25 (all worn) |
| R2D2 | 21 | T20 | 9 of 11 | 1,1,5,5,5,5,10,10,10,10,20 (all worn) |
| Lor | 19 | T15 | 9 | 1,1,5,5,5,10,10,10,10 (the 9 below-tier slots) |

R2D2's median worn item is level 5 at character level 21. No current mechanism
asks this question. `near_term_gear` asks "what can I build today that beats what
I wear", answers it correctly, and the gap stays invisible.

### 2.4 The search space contains what the character cannot do

```
CraftActions in the action set:                          321
LevelSkill actions (one per distinct skill x craft_level): 62

For Robby (weaponcrafting 10):
  crafts open at his current skills:                      75
  crafts gated behind a skill he lacks:                   246
  LevelSkill actions above his current skills:          40/62
```

`LevelSkill.apply` optimistically rewrites the skill to its target, so all 246
gated crafts are reachable during search. The entire T15-T50 craft tree is in the
graph for a character who can craft none of it.

This is already measured in the codebase: `LevelSkill.is_applicable` was profiled
at **48.2s of a 67.3s search — 72%** (from-scratch `greater_wooden_staff`,
2026-08-13). Live planner cost today: Lor averages 5,800 nodes per cycle and
peaks at 38,773; Robby has recorded single searches of 28.9s over 75,691 nodes
against a 15s budget floor.

### 2.5 Combat target selection has no lower bound

`cheapest_path_to_level` (`ai/learning/projections.py:351`) filters candidates
with `1 <= lvl <= sim_level + 1`. The floor is literally `1`. The comment above it
mirrors only the upper bound. That line dates to `ed676b81`, 2026-05-18, and was
already inconsistent with the executor on the day it landed; `FightAction`'s own
lower window `monster_level >= max(1, state.level - 1)` was removed on
2026-06-09 and replaced with `xp_per_kill > 0`, so no floor has been enforced
anywhere since.

The projection is tier 2 of the `_winnable_farm_target` cascade and outranks the
windowed picker at tier 3, so `combat_picker`'s correct
`[char_level - 1, char_level + 2]` window never gets a vote.

Consequence, measured over the six hours to 2026-08-23T01:44Z:

| character | level | grinding | monster level | gap |
|---|---|---|---|---|
| Robby | 30 | spider | 20 | 10 |
| Lor | 19 | flying_snake | 12 | 7 |
| C3P0 | 21 | highwayman | 15 | 6 |
| HAL | 19 | highwayman | 15 | 4 |
| R2D2 | 21 | skeleton | 18 | 3 |

Zero tasks have been completed by any character, ever. All five hold a task at
0/N. Lor holds `yellow_slime` (level 2) at character level 19 and HAL holds
`sheep` (level 5) at 19; both are grey, so `xp_per_kill == 0`, so `FightAction`
is structurally inapplicable and the task can never progress.

## 3. The model

Two node types over the existing machinery. **The GOAP planner, the A* search,
the `Goal` ABC, and every `Action` are unchanged.** This is a unification of the
meta-layer, not a replacement of the solver.

### 3.1 Node types

**`Goal`** — unchanged, `ai/goals/base.py`. Already carries `is_satisfied`,
`is_plannable`, `relevant_actions`, `heuristic`, `max_depth`, `value`/`priority`.
Solved by `GOAPPlanner.plan()`.

**`Decision`** — new. A named predicate over `(state, game_data, ctx)` plus
ordered branches. Never planned; resolves to a child node. Minimal protocol:

```python
class Decision(Node):
    name: str
    def resolve(self, state, game_data, ctx, history) -> Node: ...
```

`Goal` and `Decision` share a `Node` marker so a branch may point at either.

### 3.2 Resolution

Walk from the root, alternating: a `Goal` that is satisfied yields to its parent's
next branch; an unsatisfied `Goal` that is `is_plannable` now is the answer; a
`Decision` evaluates its predicate and recurses into the selected branch. The
resulting `Goal` is handed to the unchanged planner.

Robby's live case:

```
Goal(gear_to_current_level)                        not satisfied
  Decision(Can_I_Craft_Current_Tier)               weaponcrafting 10 < 30 -> no
    Goal(SkillToNextLevel(weaponcrafting, 11))     recurses
      Decision(Can_I_Craft_Current_Tier)           a wc-10 rung exists -> yes
        Goal(CraftBestCurrentTierItem)             one of 18 open rungs
          Goal(GatherRecipe)                       <-- A* runs here, unchanged
```

A* stops early because the graph already answered the meta-questions, not because
of a budget, a node cap, or a depth cutoff.

### 3.3 The increment rule

A gate is never resolved toward its target, only toward its next increment:

| gate | resolves to |
|---|---|
| skill `S >= 30`, current 10 | `SkillToNextLevel(S, 11)` |
| `ClearTier(30)`, lowest uncleared 20 | `ClearTier(20)` |
| char level `>= 35`, current 30 | `LevelUp(31)` |

Nothing between the current value and the target is ever represented. The
increment is re-derived every cycle from live state, so a level-up advances the
target and a changed bag changes the chosen rung, with no commitment state and no
execution-time expansion hook.

### 3.4 Gate-closed action set

Because the resolved `Goal` is by construction achievable with current
capability, `relevant_actions` excludes every gated action: no craft above the
current craft skill, no gather above the current gather skill, and no
`LevelSkill`. The unreachable subtree is not pruned — it is not in the graph.
Robby's craft branching drops from 321 to 75.

### 3.5 Derived tier ladder

`Tier` is derived from game data, never hardcoded.

- `LADDER` = the sorted distinct `level` values of all equippable items:
  `[1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]`.
- `band(T)` = monsters with `T <= level < next(T)`. This partitions all 58
  monsters with no empty band; band sizes range 2 to 9.
- Monster classification comes from the API's own `monster.type` field, already
  read at `ai/monster_catalog.py:128`: `normal` 47, `boss` 6, `elite` 3,
  `raid_boss` 2.

**`ClearTier(T)` is satisfied when every `normal` monster in `band(T)` is
winnable at max HP.** Bosses, elites and raid bosses are optional content with
their own objectives and never gate the ladder. This matters concretely:
`king_slime` is a `boss` at level 15 with 1000 HP and 20 resistance on all four
elements, and it would otherwise stall Robby at T15 permanently at character
level 30.

**Gear target tier is the tier being cleared, not the character's level:**

```
target_tier = min( max(t in LADDER if t <= char_level), tier_being_cleared )
```

Robby: `min(T30, T20) = T20`, which is 5 slots to close rather than the 10 that
section 2.3's naive figure reports. Targeting T30 would demand `cyclops_eye`,
`imp_tail` and `demon_horn` from T25/T30 monsters he cannot beat — the same
unreachable-target failure this design exists to remove. T20 gear crafts from
T15-and-below materials, which he has cleared by definition. Character level only
caps the target; it never sets it.

With that rule the fleet's active link is:

| character | level | next uncleared tier | needs XP? | active link |
|---|---|---|---|---|
| Robby | 30 | T20 (ogre -2, vampire -1, full_moon_vampire -2, corrupted_ogre -38) | no | `MaxGearForLevel` |
| R2D2 | 21 | T15 (pig +0) | no | `MaxGearForLevel` |
| Lor | 19 | T15 (skeleton -3, pig +0) | no | `MaxGearForLevel` |

None of them needs a single point of XP. All three are XP-grinding today.

### 3.6 Rung selection

`SkillToNextLevel(S, C+1)` resolves to the open in-skill rung with the best
**observed craft XP per acquisition action**.

The existing selector already ranks on a rate, but its numerator is
`craft_level`, a known-biased proxy: `ash_plank` and `apprentice_gloves` are both
craft level 1 and pay 5 and 53 XP respectively. The numerator becomes observed
craft XP from the `craft_yield` table, falling back to published game data when
no observation exists. The denominator stays `acquisition_actions` over the
recipe closure.

### 3.7 The XP-grind floor is emergent

XP-grinding occurs only under `LevelUp(to tier floor)`, and a tier floor is by
construction close to the character's level. No explicit `char_level - 2` rule is
needed or wanted. A character whose level has outrun its tier — Robby at 30 with
T20 uncleared — simply has `LevelUp` satisfied and descends past it to gear.

## 4. Termination

Recursion is well-founded on the lexicographic measure

```
(tier, character level, skill level, materials outstanding)
```

each component bounded above and strictly decreasing along an edge. This replaces
today's three-measure F/D/E descent in the Lean liveness development with a
single decreasing tuple.

Two obligations the proof must discharge:

1. Every `SkillToNextLevel(S, C+1)` has at least one open rung, or the node
   reports an honest wall rather than looping. Verified for all seven craft
   skills at every reachable level by the wave-2 census (§7).
2. No `Decision` cycle exists: the graph is a DAG once the increment rule is
   applied, because every recursive edge strictly decreases the measure.

## 5. Stability and interrupts

Long grinds are expected. Robby needs many cycles of weaponcrafting rungs, with
breaks for recycling or GE selling when inventory conditions require it.

The interrupt guards are correct as they stand and are retained unchanged:
`HP_CRITICAL`, `REST_FOR_COMBAT`, `BANK_UNLOCK`, `REACH_UNLOCK_LEVEL`,
`GE_CANCEL`, `DISCARD_CRITICAL`, `CRAFT_RELIEF`, `RECYCLE_RELIEF`, `SELL_RELIEF`,
`DEPOSIT_FULL`, `DISCARD_HIGH`. A relief interrupt takes a cycle or two; the graph
then resumes at the same node.

Stability is emergent, not bookkept. Today's sticky `_committed_repr` and the
doomed memo exist because the ranking is unstable — scores flip between cycles.
A derived graph returns the same node every cycle until state materially changes,
so the commitment machinery is deleted in wave 3.

## 6. Wave plan

Waves 1 and 2 are authorised. Waves 3-6 are specified so the destination is on
record and the ordering is fixed; each requires separate approval.

### Wave 1 — Tier as derived data (authorised)

Add `ai/tiers/tier_ladder.py`: `LADDER`, `band(T)`, `tier_of_level(L)`,
`next_uncleared_tier(state, game_data)`, `gear_target_tier(state, game_data)`.
Derived from `game_data`; no literals. Nothing consumes it yet.

Census: the partition is total and non-empty — every monster binned exactly once,
no empty band, ladder derived from item levels rather than hardcoded, monster
classification read from `monster.type`. This is the census that would have
caught the floor-of-1.

### Wave 2 — Decision node, transcription, and one rewired edge (authorised)

1. Add the `Node` marker and the `Decision` type in `ai/decision.py`.
2. Transcribe each of the eight implicit branches of `objective_step_goal` into a
   named `Decision`, behaviour-identical:

   | line | Decision |
   |---|---|
   | 898 | `Can_I_Afford_The_Currency_Leaf` |
   | 903 | `Is_The_Step_The_Equippable_Itself` |
   | 910 | `Is_This_An_Intermediate_On_A_Chain` |
   | 924 | `Does_The_Recipe_Need_A_Monster_Drop` |
   | 972 | `Can_I_Craft_Current_Tier` |
   | 1003 | `Does_The_Chain_Fit_The_Depth_Budget` |
   | 1008 | `Is_There_A_Combat_Target` |
   | 1039 | `Is_An_Items_Task_Active` |

3. Rewire exactly one edge: `Can_I_Craft_Current_Tier`'s "no" branch resolves to
   `SkillToNextLevel(root_stats.crafting_skill, current + 1)` instead of
   `GatherMaterialsGoal(step)`.
4. Add `MaxGearForLevel`, replacing `near_term_gear`'s attainability *filter*
   with a blocker *subgoal*.
5. Close the gate in `relevant_actions`.
6. Verify nothing else requires `LevelSkill` as a GOAP action; delete it and
   `level_skill_expand` plus the player's grind-expansion hook only if that
   verification passes. If it does not, record why and leave them in place.

Everything except step 3 is a transcription, so the censuses and the
planner-completeness oracle stay green throughout and the one real behaviour
change is reviewable in isolation.

### Wave 3 — graph resolution replaces the ranking (spec only)

Resolution walk replaces `StrategyDriver.decide()`'s argmax. Deleted: the flat
ranking, the four ranking multipliers, `J`, the `1e9` score scale, the focus
ledger and d'Hondt aging arbiter, the sticky `_committed_repr` commitment
machinery, and the doomed memo.

### Wave 4 — sequencing guards become Decisions (spec only)

`GEAR_REVIEW` and `CRAFT_POTIONS` leave `GUARD_ORDER` and become Decisions inside
the graph. `GearLatch` and `combat_deficit`'s `deficit_upgrade_target` are
absorbed into `MaxGearForLevel`. The eleven interrupt guards are untouched.

### Wave 5 — combat target from the tier band (spec only)

Combat target becomes `band(next_uncleared_tier)` filtered to `normal` and
winnable. Deleted: `combat_picker`'s window/fallback split, `FightAction`'s
`xp_per_kill > 0` lower gate, `cheapest_path_to_level`'s `1 <= lvl` floor, and the
`marginal_weapon_winnability` suppressor in `_structural_candidates`. A task
monster remains fightable regardless of band via the existing `drop_farm` bypass,
extended to cover task targets — this is what unblocks Lor's `yellow_slime` and
HAL's `sheep`.

### Wave 6 — supporting mechanisms as route options (spec only)

Potion crafting, cooking, task synergy and GE trading stop being roots and become
route options consulted by the relevant `Decision` when it asks for the cheapest
way to satisfy its child. A task becomes a funding route for the active link
rather than a rival objective.

## 7. Verification

The existing safety net carries this: the planner-completeness census, the
obtain-parity census, the mutation gate, and `bash formal/gate.sh` (ruff, mypy
strict, censuses, full suite, 100% coverage). Every wave must leave the gate
green.

Added censuses:

- **Wave 1** — tier partition total and non-empty; ladder derived, not literal.
- **Wave 2** — for every character state in the scenario set, no gear target is
  dropped for unattainability without a corresponding blocker subgoal being
  emitted. This is the invariant whose absence caused the freeze.
- **Wave 2** — every `SkillToNextLevel(S, C+1)` reachable in the scenario set has
  at least one open rung, or reports an honest wall.

Mutation anchors: the rewired edge at step 3 and the gate closure at step 5 each
need an anchor resolving to exactly one site, in the same commit as the edit.

Live acceptance for waves 1-2, read from `~/.cache/artifactsmmo/learning.db`,
never from trace files:

1. `weaponcrafting` exceeds 10 for the first time since 2026-08-16 on at least
   one character.
2. Planner nodes per cycle drop materially against the current baseline (Lor
   averages 5,800, peaks 38,773).
3. Gear-tier lag decreases per character: the count of equipped slots below
   `gear_target_tier` strictly falls.

Baselines are captured before the change so the comparison is against recorded
numbers, not recollection.

## 8. Risks

- **`LevelSkill` removal may be premature.** Wave 2 step 6 is explicitly
  conditional on verification. If some path genuinely needs A* to cross a skill
  gate, the action stays and the CPU win is smaller.
- **`ClearTier` depends on `predict_win`, a model.** A monster the model
  mis-scores can stall or falsely advance the ladder. The learned-loss veto in
  `is_winnable` is the existing mitigation; the boss/elite exclusion removes the
  worst cases.
- **`pig` at margin exactly 0 reads as unwinnable.** Two characters are blocked
  on it. The boundary semantics of `predict_win` at margin 0 should be examined
  during wave 5, not silently changed here.
- **Lean restatement.** Waves 3-5 invalidate the F/D/E descent proofs. The
  replacement measure (§4) should be simpler, but the work is real and is part of
  wave 3, not deferred.
- **Blast radius.** `strategy_driver.py` is 1,910 lines and `tiers/` is 5,413.
  Waves 3-5 touch most of both. The in-place migration discipline — every wave
  green — is what makes this survivable, and is the reason the parallel-spine
  alternative was rejected: two producers of the same decision is a failure mode
  this repository has already realised twice.

## 9. Non-goals

- Rewriting the GOAP planner, A*, the `Goal` ABC, or any `Action`.
- Changing the interrupt guard band.
- Adding a `char_level - 2` grind floor as an explicit rule (§3.7).
- Boss, elite, and raid content progression, which keeps its own objectives.
- Any change to the API client, rate budget, or multi-character coordination.
