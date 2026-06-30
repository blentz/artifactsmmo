# Fight-Applicability Liveness (picker ⟷ applicability consistency)

**Date:** 2026-06-29
**Status:** Design — approved direction (Approach C), pending spec review
**Sub-project:** 1 of 3 in the *Progress-Liveness to L50* epic
(this = bug fix; 2 = exploration floor; 3 = formal non-deadlock proof).

## Problem

Robby (level 3, all level-1 gear) sits crafting a **second** `wooden_shield`
under a `ReachCharLevel(5)` objective instead of grinding XP — even though he
beats `green_slime` reliably (560 wins @ 100%).

Live `plan Robby --learn`:

```
chosen_root:   ReachCharLevel(level=5)
selected_goal: GatherMaterials(wooden_shield, {wooden_shield:1})
goals_tried:   GrindCharacterXP(green_slime): nodes=2 depth=1 plan_len=0  <-- NO PLAN
```

`GrindCharacterXP(green_slime)` produces **no plan**, so the arbiter falls
through to a gearcrafting step (craft a duplicate shield). The user-visible
symptom ("grinding wooden shields when the goal is reach level 5") is this
fall-through.

## Root cause (confirmed by live probe)

`FightAction.is_applicable` (`ai/actions/combat.py:72-77`) gates on:

```python
best_eq = max(level of each EQUIPPED item, default 0)
return best_eq >= monster_level - 1
```

Robby's equipped gear is all **level 1** (copper/wooden) → `best_eq = 1`.
green_slime is **level 4** → `1 >= 3` is **False** → `Fight(green_slime)` is
not applicable. Probe:

```
monster        mlvl  pwin xp/kill applic  reason
chicken           1  True       9   True
yellow_slime      2  True      16   True
green_slime       4  True      30  False  best_eq 1 < ml-1 3   <-- bug
sheep             5 False      38  False
```

The XP-grind target picker (`combat_picker.pick_winnable_monster_pure`)
selects green_slime — highest-level winnable monster in the window
`[max(1, lvl-1), lvl+2] = [2,5]`, `is_winnable=True`. But `is_applicable`
rejects it on the **gear-level** proxy. **Picker and applicability gate
disagree on what is fightable.**

This is a contract violation already written into the code. The picker
docstring (`combat_picker.py:18-22`) asserts:

> "`FightAction.is_applicable` uses the SAME lower gate (`xp_per_kill > 0`)
> and the same `char_level + 2` upper bound, so every target this picker
> returns is level-applicable."

The `best_eq >= monster_level - 1` gate was added to `is_applicable` **without**
updating the picker or its Lean model (`CombatTargetExistence.lean`,
`pickWinnableWindowed`). It is the rogue term. It also conflates *gear level*
with *capability* — capability is already decided authoritatively upstream by
`is_winnable` (`ai/combat.is_winnable`), per the established decision that
`predict_win` stays OUT of `is_applicable`
(memory: `no_predict_win_in_goap_precondition`).

### Secondary (latent — not today's blocker)

`GrindCharacterXPGoal.is_satisfied` (`grind_character_xp.py:81-82`) couples XP
gain with `_loadout_optimal` (added in `fb929887`). The `pick_loadout`
refactor (`44e715c1`) now makes `wooden_staff` the "optimal" weapon vs
green_slime (earth 8 unresisted > copper_dagger air 6 resisted 25), so
`_loadout_optimal` is False and satisfaction requires a weapon swap the
planner is never directed to make (`desired_state` only asks for `{xp:+10}`).
This bites **after** the primary is fixed (Fight is rejected before loadout
matters today), so it is in scope but second.

## Invariant (the deliverable)

> **Picker–applicability consistency:** for any state `s` and monster `m`, if
> the combat target picker can return `m` (i.e. `m` is `is_winnable` and within
> the picker's level window/fallback), then `FightAction(m).is_applicable(s)`
> holds — modulo genuinely transient runtime preconditions (HP fraction,
> inventory free capacity).

Equivalently: **`is_applicable` must not reject a fight on capability grounds**;
capability is `is_winnable`'s job, applied upstream. This is the
"fight never deadlocks when a winnable target exists" lemma — the seam handed to
sub-project 3.

## Design

### Component 1 — remove the rogue gate (`ai/actions/combat.py`)

Delete the `best_eq >= monster_level - 1` term (and the `best_eq` computation)
from `FightAction.is_applicable`. The remaining gates are all either transient
runtime preconditions or genuine structural bounds, none of which contradict
`is_winnable`:

- `locations` non-empty (a spawn exists),
- `inventory_free >= _MIN_FREE_SLOTS` (loot capacity — transient),
- `hp_percent > _MIN_FIGHT_HP_FRACTION` (survivability — transient),
- `monster_level <= state.level + 2` (suicide upper bound — **kept**),
- `xp_per_kill(...) > 0` (leveling-relevant lower bound — **kept**).

green_slime then passes: spawn ✓, free=69 ✓, hp 100% ✓, `4 <= 5` ✓,
`xp 30 > 0` ✓ → applicable.

Swap-first ordering is **unaffected**: it is enforced by `LOADOUT_PENALTY` in
`FightAction.cost` (`combat.py:130-136`), not by `is_applicable`. The gate
removal does not let the bot fight *unwinnable* monsters: `is_winnable` filters
those upstream at target selection / feasibility / the prerequisite graph.

### Component 2 — picker alignment audit (`combat_picker.py`)

No logic change expected — the picker already encodes the intended rule. Work:
1. Confirm the picker's selection domain is a subset of the post-fix
   `is_applicable` domain (winnable ∧ window/fallback ∧ structural ⇒ applicable).
2. The docstring claim (lines 18-22) becomes **true** again; tighten its wording
   to name the exact shared gates.

### Component 3 — formal lockstep (`formal/`)

1. **Remove the modeled gate.** Confirmed present: `gearMeetsMonster
   (bestEqLevel monsterLevel) := bestEqLevel ≥ monsterLevel - 1`
   (`ActionApplicability.lean:64-66`), wired into the `fightApplicable`
   conjunction and **consumed by liveness** (`FightProgress.lean`,
   `ProgressAction.lean`). Remove it in lockstep with Component 1 and repair the
   liveness lemmas it fed (each loses one now-vacuous hypothesis — strictly
   weaker, so consumers simplify).
2. **Add the consistency lemma:** `winnable(s,m) ∧ inWindowOrFallback(s,m) ⇒
   FightApplicable(s,m)` (capability-side only; HP/inventory remain runtime
   hypotheses). Ties `CombatTargetExistence.pickWinnableWindowed` to
   `ActionApplicability`. This lemma is the reusable obligation for sub-project 3.
3. Keep `predict_win` **out** of the precondition — the lemma is over the cheap
   structural gate, not the formula.

### Component 4 — decouple grind satisfaction (`grind_character_xp.py`)

`is_satisfied` becomes `state.xp > self._initial_xp` (drop `_loadout_optimal`).
Loadout optimization stays a *cost* signal (`LOADOUT_PENALTY`) plus an optional
`OptimizeLoadoutAction` plan step — never a satisfaction gate. Remove the now-dead
`_loadout_optimal` helper if unused elsewhere. Update any serialize/diff/mutation
lockstep referencing the old predicate.

## Testing

- **Failing test first (TDD):** reproduce `GrindCharacterXP(green_slime)`
  `plan_len=0` from a fixture at `level=3` with all level-1 gear; assert the
  fix yields a plan whose terminal action is `Fight(green_slime)`.
- **Applicability unit:** `FightAction(green_slime).is_applicable` is True at
  `best_eq=1, char_level=3`; `sheep` (unwinnable, but structurally `5<=5`) is
  still admitted structurally and excluded by upstream `is_winnable` — assert
  the picker does not return it.
- **Consistency property test:** over a generated catalog, every picker output
  is `is_applicable` (capability gates only).
- **Differential + mutation:** regenerate anchors for the changed
  `is_applicable` decision and the `is_satisfied` change; confirm a mutant that
  re-introduces the gear gate is killed.
- Full gate green: 0 errors / 0 warnings / 0 skipped / 100% coverage.

## Scope / non-goals

- **In:** Components 1-4 above.
- **Out:** the exploration floor (sub-project 2) and the full non-deadlock
  L50 proof (sub-project 3). This spec only furnishes the
  `winnable ⇒ applicable` lemma those depend on.
- **Out:** re-tuning the XP-grind target *priority* (`GrindCharacterXPGoal.value`)
  or the gearcrafting fall-through ranking — separate concerns.

## Risks

- **Removing a Lean-locked gate** could surface dependent proofs. Mitigation:
  Component 3 audit before edit; run `mutate.py` after the `ai/` change
  (stale anchors — memory: `mutation_ci_oom`).
- **Over-permissive `is_applicable`** admitting unwinnable fights in some
  caller that does *not* pre-filter with `is_winnable`. Mitigation: the
  consistency property test + audit every `FightAction` caller for an upstream
  `is_winnable` gate; the suicide bound + `xp_per_kill>0` remain.
- **Secondary decoupling** might let the bot grind with a suboptimal weapon
  (copper_dagger vs green_slime). Acceptable: `LOADOUT_PENALTY` still biases the
  planner to swap when an `OptimizeLoadoutAction` is available; satisfaction no
  longer deadlocks on it.

## Seam to sub-project 3

The Component-3 lemma `winnable ∧ in-window ⇒ applicable`, composed with
`CombatTargetExistence` (a winnable in-window target exists whenever the char is
below the suicide ceiling and some monster grants XP), gives **"fight never
deadlocks"** — one of the three progress channels (fight / gear / craft) whose
joint non-blocking is the L50 non-deadlock theorem.
