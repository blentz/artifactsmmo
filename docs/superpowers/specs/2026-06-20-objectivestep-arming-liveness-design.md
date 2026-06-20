# Discharging the objective-step arming — "always a right next action toward 50"

Date: 2026-06-20
Related: [[project_plannability_soundness]] (approach 2 — the liveness reframing),
[[project_o54_select_differential]], [[project_levelfifty_vacuity]],
[[feedback_proofs_tell_false_stories]].

## Problem

The entire level-50 reach proof hangs on ONE asserted if-then. `perceptionRefresh`
(`formal/Formal/Liveness/PerceptionRefresh.lean:52`) does, below the cap:

```lean
def perceptionRefresh (s) :=
  if s.level < 50 then { s with objectiveStepFires := true, objectiveStepIsFight := true } else s
```

`objectiveStepFires : Bool` is documented (`Measure.lean:153`) as "the objective
tier yields a **plannable** step." Below 50, `perceptionRefresh` simply **asserts
it true** — it does not prove the objective tier actually yields a plannable
progress step. The strongest non-vacuous capstone
`cycleStepF_reaches_fifty_of_fights` (`LevelingDescent.lean:114`) inherits this as
its central hypothesis `FightsBelowCap`. So "the bot always has a right next
action toward 50" is *defined into existence*, not proven — the O5.4 binding
residual.

**The alignment with corner 3 (do NOT route around it — fix it here).**
`WinnableAcrossBand`'s soundness rests on `best_weapon_for_level` — an OPTIMISTIC
proxy that assumes the bot can OBTAIN the best weapon at level L. That
obtainability is exactly the gather/craft-feasibility question corner 3 (the
`minGathers` lower bound) is about. So corner 3 is not off-path — it is the
FOUNDATION of the gear-tier assumption that grounds `WinnableAcrossBand`. And the
gear-obtainment context is precisely where corner 3 becomes TRACTABLE: obtaining
ONE equippable item is **demand-1, craft exactly the recipe closure, NO surplus**
— so the wasteful-surplus cross-branch max-cut pathology that defeated the general
arbitrary-plan corner 3 (14 rounds, [[project_plannability_soundness]]) cannot
arise. "Equipment capping is obviously monotone" (the user's insight) holds
exactly in this no-surplus gear setting. Fixing corner 3 in the gear-obtainment
framing both CLOSES it (unconditional `minGathers_le_gathers` for the
gear-obtainment class) and GROUNDS the `best_weapon_for_level` obtainability that
`WinnableAcrossBand` needs — removing the proxy's optimism gap. The two soundness
stories (gear feasibility + leveling liveness) are one.

The grounding hypothesis already exists: `WinnableAcrossBand`
(`GearTierLeveling.lean:54`) — at every band `1 ≤ L < 50`, the catalog has a
winnable, XP-positive, not-overleveled monster — and `combatObjective_live_below_fifty`
(`GearTierLeveling.lean:84`, already PROVEN from it) gives a combat target. The
fight step itself is still crafting-free (`planFor = [.fight]`); corner 3 enters
not on the fight action but on grounding that the WINNABILITY-enabling gear is
obtainable.

## Goal

Replace `perceptionRefresh`'s asserted `objectiveStepFires/IsFight := true` (below
50) with a PROOF; ground its hypothesis `WinnableAcrossBand` from live data BOTH
empirically (differential sweep) AND by a pure-Lean kernel proof over the
extracted monster catalog; and CLOSE corner 3 in the gear-obtainment context
(unconditional `minGathers_le_gathers` for no-surplus gear plans + a constructive
obtainability witness), which grounds the `best_weapon_for_level` obtainability
the kernel proof needs. Result: `cycleStepF_reaches_fifty_of_fights`'s
`FightsBelowCap` becomes a result (modulo the honestly-named residuals below),
on a now-unconditional gear-feasibility foundation rather than a banked min-cut.

## Components

### C0. Close corner 3 in the gear-obtainment context (foundation)
Corner 3 (`PlanModel.lean`, `minGathers_le_gathers_of_corner3`) is the `δ ≤ ε`
craft-monotonicity coupling that 14 rounds could not breach for ARBITRARY plans —
because a plan may craft SURPLUS of an intermediate `c` that competes for raw
shared with another branch (the max-cut). Discharge it in the gear-obtainment
class, where it is tractable:
- **The no-surplus restriction kills the coupling.** Obtaining ONE equippable is
  demand-1: the minimal plan crafts each intermediate EXACTLY the amount consumed
  upstream — never surplus. A* never wastes toward a single gear target, so every
  production gear plan is no-surplus. In the no-surplus class the wasteful-`c`
  pathology cannot arise → craft-monotonicity holds → `minGathers_le_gathers`
  unconditional (no `corner3` hypothesis) FOR THAT CLASS. Prove the lower bound
  directly for no-surplus plans (do NOT reduce arbitrary plans — that reduction
  was the wall).
- **Constructive obtainability witness.** Define the canonical gear-obtainment
  plan (gather raw leaves, craft the recipe closure bottom-up, equip) and prove
  its gather count = `minGathers` and its length = `minPlanLength`. This is the
  EXISTENCE direction: `minPlanLength(gear) ≤ depth ⟹ a plan obtaining+equipping
  the gear within depth EXISTS`. Pure construction, no max-cut.
- This witness GROUNDS `best_weapon_for_level` obtainability (C1b's per-level
  stat model assumes the best weapon is obtainable; C0 proves it is, within the
  depth budget the band allows), closing the kernel proof's optimism gap.
- **Honest boundary:** this discharges corner 3 for the demand-1 / no-surplus
  gear-obtainment class — exactly the equipment domain ("capping is obviously
  monotone") and exactly what every production gear plan and the liveness
  obtainability need. The fully general arbitrary-surplus DAG lower bound is NOT
  claimed; it is not required by any production path. State this in the theorem
  docstring — no flattering over-claim.

### C1. Ground `WinnableAcrossBand` from live data — differential sweep
The sweep `formal/diff/test_winnable_across_band_diff.py::test_winnable_across_band_real_sweep`
already exists and validates the claim against the live snapshot using
production's REAL `is_winnable` / `pick_winnable_monster_pure` /
`best_weapon_for_level`, but SKIPS because `formal/sim/character_base_stats.json`
is absent.
- Capture it: `~/.local/bin/uv run python formal/sim/capture_base_stats.py Robby`
  (per-level base stats, resumable) and re-run `snapshot_game_data.py` so
  `item_stats` carries combat fields. Un-skip + green the sweep (every band 1..49
  has a winnable XP-positive not-overleveled monster). Conservative soundness:
  the best-weapon proxy is a LOWER bound on real capability (real armor only adds
  power), and the learned-loss veto defers to `predict_win` (history=None).

### C1b. Ground `WinnableAcrossBand` — pure-Lean kernel proof
Make `WinnableAcrossBand` kernel-checked (no Lean hypothesis), over the EXTRACTED
catalog:
- **Extract the catalog**: extend `formal/sim/generate_lean_fixture.py:65`
  (currently emits only recipes) to also emit the 48-monster catalog as a
  `List Monster` (code, level, hp, attack-by-element, resistance, crit) into
  `GameDataFixture.lean`, from `game_data_snapshot.json` (which already has
  `monster_level`/`hp`/`attack`/`resistance`/`crit`).
- **Per-level player-stat model (breaks the gear circularity)**: define
  `playerStatsAtLevel L = baseStats(L) + bestWeapon(L)` in Lean, where `baseStats`
  is the captured per-level base (from `character_base_stats.json`, extracted) and
  `bestWeapon(L)` mirrors `best_weapon_for_level` (max-attack weapon with
  `item.level ≤ L`) — the monotone optimistic proxy. This is a LOWER bound on the
  real (also-armored) character.
- **Bridge `winnable → predictWin`**: define the concrete `winnable` and `xpPos`
  `WinnableFn`s as `predictWin(playerStatsAtLevel L reduced-to-scalars, monster
  scalars)` and `xpPerKill > 0` (xp from the curve / LIV-001), instead of the
  opaque parameters. Use `PredictWin.lean`'s monotonicity (`predict_win_mono_player`,
  `:496`) for the conservative-proxy soundness argument.
- **Decide it**: `∀ L ∈ [1,50), ∃ m ∈ catalog, winnable ∧ xpPos ∧ notOverleveled`
  over finite band × finite (48) catalog by `decide`/`native_decide`. (Liveness
  tier permits the classical axioms; `native_decide` use is scoped + justified
  per the axiom gate.)
- Result: a `WinnableAcrossBand_grounded` theorem instantiating the abstract def
  with the concrete catalog/winnable, no remaining hypothesis except LIV-001
  (xp curve) + the captured-data fixtures (whose fidelity the C1 differential
  pins).

### C2. Discharge `perceptionRefresh`'s assertion
Replace the unconditional `objectiveStepFires/IsFight := true` (below 50) with a
proof that the objective tier yields a plannable fight step, from:
- `combatObjective_live_below_fifty` (proven from grounded `WinnableAcrossBand`)
  ⟹ a combat target exists at level L < 50;
- a fight step is structurally plannable (`objectiveStepIsFight ⇒ planFor =
  [.fight]`) — the fight ACTION needs no craft; corner 3 enters only on grounding
  the winnability-enabling gear obtainability (C0/C1b), now discharged;
- the **O5.4 binding** (a differential, same pattern as `test_ladder_fires_diff`):
  production's `objective_step_goal(ReachCharLevel)` returns a fight goal
  (`GrindCharacterXPGoal`) when `combat_monster ≠ None` (`strategy_driver.py:578-611`).
  This pins the Lean `objectiveStepFires/IsFight` Bools to production, discharging
  the arming instead of asserting it.

### C3. Re-prove the capstone on the discharged arming
Thread the now-proven arming through `cycleStepF_reaches_fifty_of_fights`
(`LevelingDescent.lean:114`) so its `FightsBelowCap` is a RESULT, not an
assertion — modulo the residuals below.

## Honest scope — what is proven vs named (no flattering proof)

**PROVEN (this work):** corner 3 discharged for the gear-obtainment class
(unconditional `minGathers_le_gathers` for no-surplus gear plans + constructive
obtainability witness, C0); `WinnableAcrossBand` grounded from live data both
empirically (C1 differential) AND in-kernel (C1b, on C0's obtainability);
the objective-step arming (`objectiveStepFires/IsFight` below 50) discharged from
combat-target-existence + structural fight-plannability + the O5.4 binding (C2);
`FightsBelowCap` thereby a result feeding the reach-50 capstone (C3).

**NAMED, NOT discharged (your option-3 follow-on):**
- *blockers-quiet*: that no chore/task means out-prioritizes the objective fight
  step at EVERY below-50 cycle (`objectiveStepBlockers`, `FightFairness.lean:47`).
  The capstone needs this; it stays an honest hypothesis here.
- *LIV-001*: the `xpToNextLevel` server xp-curve axiom (carried throughout).
- The C1b best-weapon proxy's conservative gap (real armor only helps) — named in
  the bridge docstring; the C1 differential is the faithfulness pin.

**NAMED boundary on C0:** corner 3 is discharged for the demand-1 / no-surplus
gear-obtainment class only — the fully general arbitrary-surplus DAG lower bound
is not claimed (and is needed by no production path). Stated in the C0 theorem
docstring.

No theorem or docstring claims more than the above; `native_decide`/axiom use is
scoped and gate-checked.

## Testing / success criteria
- C0: `minGathers_le_gathers` proven 0-sorry for the no-surplus gear class (the
  final theorem carries NO `corner3` hypothesis — grep confirms it gone); the
  constructive obtainability witness (`gear obtainable within depth`) proven; the
  docstring states the no-surplus boundary; differential/mutation anchors hold.
- C1: `test_winnable_across_band_real_sweep` un-skips and PASSES (no band gaps)
  against the live snapshot; the captured fixtures committed.
- C1b: `WinnableAcrossBand_grounded` proven 0-sorry over the extracted catalog;
  `lake build` clean; axiom gate passes (classical + LIV-001 + scoped
  native_decide only).
- C2: a `test_objectivestep_arming_diff.py` (or extend an existing diff) pins
  production `objective_step_goal(ReachCharLevel)` → fight goal when a target
  exists; the Lean `perceptionRefresh` arming proven, not asserted.
- C3: `cycleStepF_reaches_fifty_of_fights` re-proved with `FightsBelowCap`
  discharged from C2 (modulo blockers-quiet + LIV-001); the removed assertion's
  `rfl` arming lemmas updated.
- `gate.sh` ALL GATE PARTS PASSED; full Python suite 100%.

## Non-goals / YAGNI
- No attempt on blockers-quiet / full every-cycle descent (option-3 follow-on).
- No general arbitrary-surplus DAG min-cut lower bound (C0 closes only the
  no-surplus gear class — sufficient for every production path).
- No new combat model — reuse `PredictWin.lean` + `pick_winnable_monster_pure` +
  `best_weapon_for_level`.
