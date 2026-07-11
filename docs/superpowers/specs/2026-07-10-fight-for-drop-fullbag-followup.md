# Fight-for-drop deadlock — follow-up (Task 6 of fight-loadout-precondition)

Date: 2026-07-10
Status: root-caused, NOT fixed here (out of core scope per the design doc's
§5 "Scope / non-goals" — this document is the required decision record)
Relates to: [[project_gear_pursuit_correctness]] (this feature),
docs/superpowers/specs/2026-07-10-fight-loadout-precondition-design.md §5
("Fight-for-drop full-bag deadlock (secondary)")

## Verdict

**NOT resolved by the shipped hard-gate + relief.** It is also **NOT the
same failure family as the full-bag slot-relief work** ([[project_slot_
exhaustion_livelock]] / this feature's Tasks 1-5): it is not a slot-room
problem at all. `GatherMaterialsGoal(cowhide, ...)` is **completely
unplannable** (`GOAPPlanner.plan(...) == []`) whenever the equipped weapon
does not match the optimal combat loadout for the drop's monster — **at ANY
bag-slot occupancy**, full or empty. Full-bag was the framing the design doc
used to describe the live symptom, but it is not the binding constraint.

## Root cause

`GatherMaterialsGoal.relevant_actions` (`src/artifactsmmo_cli/ai/goals/
gathering.py`) admits `OptimizeLoadoutAction` on exactly one condition
(lines ~242-244):

```python
or (isinstance(action, OptimizeLoadoutAction)
    and action.target_skill in needed_skills)
```

`needed_skills` (lines 209-213) is built ONLY from the **gathering**-resource
skill requirements of the closure materials (`game_data.resource_skill_
level(res)` for each `res` in `needed_resources`) — it never contains a
combat purpose. A combat-purpose `OptimizeLoadoutAction` (constructed by
`actions/factory.py:70` as `OptimizeLoadoutAction(target_monster_code=...)`)
has `target_skill == ""`, which is never a member of `needed_skills`. So
**no combat-purpose `OptimizeLoadoutAction` is EVER admitted by
`GatherMaterialsGoal.relevant_actions`**, regardless of state — this
condition has nothing to do with inventory slots.

This line predates the fight-loadout-precondition feature entirely
(introduced at `32d0408c "fix(gear): activate the gather re-arm..."`,
2026-07-0x, and untouched since — `git log -S"target_skill in needed_skills"
-- src/artifactsmmo_cli/ai/goals/gathering.py` shows exactly one hit). It was
**dormant** before this feature: `FightAction.is_applicable` previously only
SOFT-penalized a mismatched loadout (`LOADOUT_PENALTY` in `.cost`), so
`Fight(cow)`/`Fight(cow, drop_farm=True)` stayed applicable even with a
gathering tool equipped — the goal could still plan, it would just fight
sub-optimally (the exact live-Robby bug this whole feature exists to fix
elsewhere). Task 2 of this feature (`658979b3 "feat(combat): hard optimal-
loadout gate on FightAction.is_applicable"`) added a HARD gate:
`FightAction.is_applicable` now returns `False` whenever `not
equipped_matches_loadout(state.equipment, pick_loadout_cached(Combat(...),
state, game_data))`. That flips this goal's pre-existing action-menu gap
from harmless (goal still had ONE applicable action, just a bad one) to fatal
(goal now has ZERO applicable actions reaching the drop) — a genuine
regression surfaced (not caused, in the sense of new code, but activated) by
the hard gate.

## Reproduction (real bundle + GamePlayer harness, budget 30s)

Script (ad hoc, not committed — see "Files changed" below for what WAS
committed): `dataclasses.replace` on `SCENARIOS["l10_bag_pursuit"]` (level
10, `cow` confirmed winnable and cowhide-demanding by the existing
`test_l10_bag_pursuit_satchel_live_but_vest_outranks` pin in
`tests/test_ai/scenarios/test_slot_coverage.py`), with `weapon_slot` swapped
to `copper_pickaxe` (gather tool) and `iron_dagger` (the scenario's real,
winning weapon) moved to inventory, owned but unequipped — mirrors this
feature's own `_suboptimal_scenario()` pattern in `test_fight_loadout_swap.
py`.

```python
gd = load_bundle_game_data(BUNDLE)
sc = dataclasses.replace(SCENARIOS["l10_bag_pursuit"],
    equipment={**base.equipment, "weapon_slot": "copper_pickaxe"},
    inventory={"iron_dagger": 1})
state = scenario_state(sc, gd)
goal = GatherMaterialsGoal("cowhide", {"cowhide": 6})
player = GamePlayer(character=sc.name, history=None)
player.seed_offline(state, gd)
actions = player._build_actions()          # the SAME action menu plan_from_state uses
relevant = goal.relevant_actions(actions, state, gd)
plan = GOAPPlanner().plan(state, goal, actions, gd, history=None, budget_seconds=30.0)
```

Observed (non-full-bag, `inventory_slots_free` far from 0):
```
is_winnable(state, gd, "cow")                       -> True
[a for a in relevant if isinstance(a, FightAction)]  -> [FightAction(cow, drop_farm=False)]
[a for a in relevant if isinstance(a, OptimizeLoadoutAction)] -> []   # ZERO — the gap
FightAction(cow)._structurally_applicable(state, gd) -> True   # pre-gate gates all pass
FightAction(cow).is_applicable(state, gd)            -> False  # hard gate blocks it
plan                                                 -> []      # DEADLOCK
```

Repeated at **L20** (`l20_dual_utility`, weapon swapped the same way) so the
drop is farmed via the `drop_farm=True` grey-mob path exactly as the brief
frames it (cow is level 8, grey at char level 20):
```
xp_per_kill(cow, level=20)  -> 0
grey_farm_allowed("cowhide", state, gd) -> True
relevant fights -> [FightAction(cow, drop_farm=True)]
relevant OptimizeLoadout(combat) -> []                # same gap
FightAction(cow, drop_farm=True).is_applicable -> False
plan -> []                                             # DEADLOCK
```

And again with the L20 state ALSO packed to `inventory_slots_free == 0`
(17-stack `JUNK_STACKS`, matching `test_fight_loadout_swap.py`'s
`TestFullBagRelief`): identical `plan == []` — full bag changes nothing,
confirming the deadlock is not slot-arithmetic.

**Full-arbiter seam** (`player.plan_from_state()`, the actual per-cycle
call): at the full-bag L20 state, the arbiter does NOT hang or return a
truly empty top-level plan — `near_term_gear` (`tiers/objective.py:361`,
`value > self._item_value(state.equipment.get(slot))`) reads the EQUIPPED
item's value, so a gathering tool in `weapon_slot` makes `weapon_slot`
itself read as a live gear gap and a DIFFERENT candidate wins
(`chosen_root=ObtainItem(mushmush_bow, weapon_slot)`,
`selected_goal=UpgradeEquipment(minor_health_potion->utility1_slot)`,
`plan=[DepositAll, Withdraw(nettle_leaf×2), Withdraw(algae×1),
Craft(minor_health_potion×1), Equip(minor_health_potion->utility1_slot)]`) —
the EXACT same shape Task 5's `TestFullBagRelief` already documented for the
`highwayman`/`GrindCharacterXP` case (same base scenario, same mechanism:
`plan[0]` is a relief action, but the goal that actually ran has nothing to
do with cowhide). This is consistent, not a new finding, and it means the
top-level bot does not visibly "get stuck" — but it also means it never
resolves the ORIGINAL demand (cowhide/whatever recipe needed it) while the
tool stays equipped; if/when `GatherMaterialsGoal(cowhide, ...)` IS the
selected goal in a state where no such distraction candidate exists (e.g.
task-funded cowhide demand with every other slot already at its near-term
fixed point — the isolation shape `l12_bag_pursuit` already uses for the
satchel chain), the arbiter has no fallback and the objective step simply
returns `plan_len == 0` for that cycle, silently stalling until something
else changes state (nothing will, since nothing in this goal can equip the
weapon).

## Same family or distinct?

**Distinct** from the shipped slot-exhaustion fix
([[project_slot_exhaustion_livelock]]) and from this feature's Task 5
full-bag investigation. Both of those are about **slot arithmetic**: an
action is structurally blocked because a displaced item has nowhere to
land, and relief (`DepositAll`/`Recycle`/`NpcSell`) fixes it by freeing a
slot. This deadlock reproduces identically with slots wide open — the
blocker is an **admission gap in `GatherMaterialsGoal.relevant_actions`**
(a missing `or` arm), not a resource constraint. No amount of slot-relief
fixes it; the goal's action menu simply never contains the one action
(`OptimizeLoadoutAction(target_monster_code=...)`) that could unblock the
gate.

## Suggested direction (NOT implemented here — out of scope)

Widen `GatherMaterialsGoal.relevant_actions`'s `needed_skills` check (or add
a sibling condition) to also admit `OptimizeLoadoutAction(target_monster_
code=m)` for every monster `m` this goal's own drop-farm/normal-fight
emission loop (lines ~299-347) already added to `result` — the goal already
computes exactly which monsters it intends to fight; it should also arm the
weapon for them. This is a same-locus, same-shape fix to the existing
`needed_skills`-gated admission (not a new mechanism), analogous to how
`OptimizeLoadoutAction(target_skill=...)` is already admitted for gathering.
Scenario coverage should re-run `test_l10_bag_pursuit_satchel_live_but_vest_
outranks`-style pins plus a new suboptimal-weapon variant once implemented.

## Files changed by this investigation

None in `src/` (no code fix — out of core scope per the design doc). This
document is the required "not allowed to silently remain a deadlock"
decision record for Task 6, per `docs/superpowers/plans/2026-07-10-fight-
loadout-precondition.md`'s Task 6 (Step 2b branch).
