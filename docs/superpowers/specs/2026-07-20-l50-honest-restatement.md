# Level-50 Capstone — Honest Restatement (EPIC)

**Date:** 2026-07-20
**Status:** DESIGNED — increment 1 in progress
**Trigger:** adversarial review 2026-07-20 of `GearedDescent.ai_reaches_fifty_geared`
**Mandate (user):** *"the l50 proof must be an accurate representation of both the game
(to the extent we can derive it) and our AI bot's logic."*

---

## 1. The finding

`ai_reaches_fifty_geared` is mathematically sound but its headline is false.
`GearedDescent.lean:16-17` claims "HYPOTHESIS-FREE: no fairness, no quiescence, no spawn,
no adequacy assumption." All four are present — **relocated from the theorem statement into
`cycleStepE`'s definition**, where `#print axioms` cannot see them and the gate goes green.

This is a worse failure than the two removed earlier the same day. Proofs over unreachable
code (`0d12a9f0`) and proofs with unsatisfiable-status hypotheses (`29c4c80f`) are both
*visible*. A hypothesis discharged into the model definition is not.

### The three grants (verified, not inferred)

| | Where | What it does |
|---|---|---|
| **G1** | `CycleStepE.lean:55-61` | `perceptionRefreshE` sets `objectiveStepFires := true, objectiveStepIsFight := true` on every sub-50 non-defer cycle when `loadoutAdequate`. This **overwrites an opaque production observation** (`Measure.lean:161-164`: the arbiter yields a step *iff* one exists). It is the retired `hfightFires` fairness obligation, relocated. |
| **G2** | `CycleStepE.lean:47,65-71` | `GEAR_CAP := 8`; `gearProgress` decrements `gearGap` and restores `loadoutAdequate` at zero cost. Nine cycles after any level-up, gear is adequate again — no gold, drop, recipe, or RNG. |
| **G3** | `Plan.lean:296-303`, `CycleStepE.lean:74-78` | `.fight` grants constant `xp + 10` and cannot fail. `fightLoss` models death as respawn-at-full, which **lowers** `hpDeficit` (slot 18) — the model prices dying better than surviving. |

Supporting evidence, all verified:
- The cited grounding is **prose only**. `GearedDescent.lean:11` and `CycleStepE.lean:19`
  name `WitnessAcquirable.acquirableFrontier_empty`; `GearedDescent` imports exactly
  `BlockerDescentE` and `DeferFaithful`. `WitnessAcquirable`/`WinnableGrounded` appear in no
  import and no proof term.
- `EMeasure.lean:12-15` documents slot 3 as existing to pay for a cycle that *"moves nothing
  the measure sees — a livelock the row analysis caught before proving."* A discovered
  livelock answered by adding a slot the action definitionally decrements.
- Eight of 27 means dispatch to `absurd hmem (by decide)` (`GearedDescent.lean:167-174`):
  `acceptTask`, `taskExchange`, `maintainConsumables`, `sellIdle`, `recycleSurplus`,
  `bankExpand`, `drainBankJunk`, `wait` are **provably unselectable below 50**.
- The E-layer has **zero production differential**. `test_cycle_step_e_diff.py` checks the
  Lean oracle against hand-built vectors, not against Python.

---

## 2. The destination — and what it is NOT

**Not "hypothesis-free."** Chasing that label is what produced this. Some of these facts are
about a live server and a stochastic world; they are not derivable offline, and pretending
otherwise is the failure mode.

**Target shape:**

```
theorem ai_reaches_fifty_geared
    (hArms  : AdequateArmsFight)        -- residual, differentially pinned
    (hGear  : GearCycleMakesProgress)   -- residual, rate claim
    (hXp    : FightYieldsXp)            -- residual, server
    (s : State) : ∃ k, (cycleStepEN k s).level ≥ 50
```

with, for **every** hypothesis, a satisfiability lemma in the
`GearTierLeveling.winnableAcrossBand_satisfiable` style (`:151-159`) so none can be a
vacuous `False → P` — the 2026-06-19 lesson.

A capstone with three named, satisfiable, individually-owned hypotheses is **strictly more
honest** than today's silent-grant version, even though it reads weaker.

---

## 3. Per-grant verdicts and work

### G1 — PARTIAL. Provable half + named residual.

**Provable now:** *at every band level a winnable XP-positive target exists for the witness
loadout* — `WinnableGrounded.winnableAcrossBand_grounded` (`:128-158`), which has **no
hypotheses**. It is a `decide`-checked certificate over the 49-row `winnableWitness` fixture;
the ∀-over-band reduction is genuine Lean/omega.

**Irreducible residual `AdequateArmsFight`:** asserts an equality between an opaque model
Bool and a Python computation over `state.equipment`, `monster_spawn_known`, and a
`LearningStore`. Only a differential can bind it.

**The gap that forces this** — `winnableConcrete` (`WinnableGrounded.lean:72`) evaluates
`predictWin` over scalars projected from the *obtainable* pool; production's
`combat_targets.py:66-70` evaluates against **current** `state.equipment`. The theorem proves
"a target exists *if you hold the witness loadout*" and says nothing about the state the
E-tower is in. That gap is exactly why `loadoutAdequate` was introduced as an opaque Bool.

**Newly found production falsifiers of `objectiveStepFires`, none modelled and none in the
existing residual prose** (`PerceptionRefresh.lean:119-122` names only the defer case):
`_marginal_provision_goal` returning a non-Fight goal (`strategy_driver.py:782-784`); the
objective step being `ObtainItem` rather than `ReachCharLevel` (`:634+`); the learned-loss
veto overriding a positive `predict_win` (`combat.py:367-377`). Also `monster_spawn_known`
false — 14/58 catalog monsters have no map tile.

### G2 — PARTIAL, and the one place real proof work pays.

**Genuinely applicable and currently unused by the E-tower:**
- `GearBuildTermination.grounded_builds_target` (`:150-153`) and `measure_markSat_lt`
  (`:127-129`) — structurally *exactly* the `gearGap` decrement `gearProgress` asserts.
- `WitnessAcquirable.certClosed` (`:62`) + `acquirable_loadouts_in_cert` (`:65-67`) — every
  witness item is recipe-closure-reachable from gatherables/monster-drops. `certClosed` is
  the real certificate; `acquirableFrontier_empty` alone is a near-content-free tripwire.

**Bridge:** `gearGraph : State → Graph`, `gearTarget : State → Nat` (witness loadout of
`s.level`), redefine `gearGap s := unmetCount (gearGraph s) U` as a **derived** quantity
rather than an opaque field. Decrement then follows from `measure_markSat_lt`; groundedness
from `certClosed`.

**`GEAR_CAP := 8` — cheapest real win.** Self-declared provisional (`CycleStepE.lean:45-46`),
grounded nowhere. Closure depth of each witness loadout is computable from `acquirableCert` +
`allRecipes`, both already in the fixture. Emit `witnessClosureDepth : List Nat` and prove
`witnessClosureDepth.all (· ≤ GEAR_CAP) = true := by decide` — same style as
`acquirable_covers_band`.

**Residual `GearCycleMakesProgress`:** *one `.gearReview` cycle executes ≥1 actionable step
of the band's closure.* A rate claim about production cycles — the arbiter may spend the
cycle moving, or fail an API call. Not derivable offline.

### G3 — RESIDUAL. Cannot be discharged, and should not be attempted.

`Formal/PredictWin.lean` is substantial (`predictWin :145`, `predict_win_eq_sim :424`,
monotonicity `:567`/`:699`, 200k-tuple differential) but **returns a `Bool` verdict over stat
scalars — no xp output, no `State` argument.** No function anywhere maps (player, monster) →
xp. `monster.xp` and the level penalty are not in `GameDataFixture` (witness rows carry
combat scalars only, `CatalogTypes.lean:69`).

`xp + 10` is **exactly faithful to production** (`combat.py:148` literally sets
`state.xp + 10`) and is a deliberate abstraction (`feedback_combat_xp_projection_is_abstract`).
The undischargeable step is planner-projection ⟹ server-reality.

Residuals: `FightYieldsXp`, `FightSucceeds`. Proving the latter would **contradict production's
own design** — the learned-loss veto (`combat.py:367-377`) exists precisely because
`predict_win` is sometimes empirically wrong.

**But one part of G3 is a plain faithfulness BUG, fixable now.** `fightLoss`
(`CycleStepE.lean:76-77`) models death as `hp := maxHp`. Production's `FightAction.apply`
(`combat.py:121-122`) does `max(1, hp - max(1, max_hp // 5))` — it **never dies and floors at
1**. The model is *more optimistic than the production planner*, in the direction that helps
the measure. Dominated (hpDeficit is slot 18 of 20) so descent should survive the correction,
but it is not a faithful image of either planner or server, and the docstring does not say so.

---

## 4. Increments (ordered by value/risk)

| # | Work | Risk |
|---|---|---|
| **1** | **Correct `fightLoss` to production semantics** (floor-at-1, never die) + disclose in docstring. Verify descent survives. | low — dominated slot |
| **2** | **Restate the capstone** with `AdequateArmsFight` / `GearCycleMakesProgress` / `FightYieldsXp` as named hypotheses; thread through `BlockerDescentE`; satisfiability lemma for each; rewrite the false headline. | med — touches every descent row |
| **3** | **Ground `GEAR_CAP`** — emit `witnessClosureDepth`, `decide` the bound. | low |
| **4** | **Bridge `gearGap` → `GearBuildTermination`** — derived `unmetCount`, decrement from `measure_markSat_lt`, groundedness from `certClosed`. | high — redefines a measure slot |
| **5** | **`formal/diff/test_loadout_adequate_diff.py`** — the missing plan item (`PLAN_c2_composed_liveness.md:238-241`). Drives real `state.equipment` → `is_winnable(band target)`. Makes G1's residual *checked* rather than *asserted*. | med |
| **6** | **Extend `test_objectivestep_arming_diff.py`** to cover the three newly-found falsifiers, or document them as accepted gaps. Note its `combat_target_exists` is an injected input flag (`:133`), so it currently assumes what it should derive. | med |
| **7** | Disclose the eight provably-unselectable means in `LEVEL_FIFTY_RESIDUALS.md` — the model asserts a behaviour the real bot does not have. | low |

Increments 1–3 are independently landable and gate-verifiable. 4 is the deepest real proof
work. 5–6 are the differentials that convert asserted residuals into checked ones.

---

## 5. Non-goals

- Reaching "hypothesis-free" again. §2.
- Proving `FightSucceeds`. It contradicts production's own learned-loss veto.
- Modelling server combat rolls. Conceded in `PLAN_c2_composed_liveness.md:244-248`.
- Touching the F/D towers' capstones except where they share `Plan.lean`'s `.fight`.
