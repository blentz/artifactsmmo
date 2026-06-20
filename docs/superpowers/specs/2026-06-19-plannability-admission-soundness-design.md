# Plannability admission soundness — design

Date: 2026-06-19
Related: [[project_zombie_commitment_livelock]] (root selection now reaches
feather_coat), [[feedback_planner_depth]], [[feedback_proofs_tell_false_stories]]
(honest proof scope).

## Problem

A committed equippable objective can be **admitted as plannable yet yield no
plan**, wasting the cycle and silently falling back to char-leveling instead of
making progress.

Concrete, live-verified (Robby, level 6, feather_coat = `{feather:5, ash_plank:2}`,
gearcrafting 5 ✓):

```
UpgradeEquipment(feather_coat)   is_plannable=True   plan_len=0   (180 nodes, depth 15, NOT a timeout)
```

`UpgradeEquipmentGoal.is_plannable` (`goals/progression.py:101-142`) admits a goal
when `ceil_gathers(min_gathers(item)) <= max_depth`. For feather_coat:
`min_gathers = 15` (5 feathers + 10 ash_wood) `== max_depth = 15` → admitted. But
`min_gathers` counts ONLY raw-material mints (gathers / monster-drop fights for
leaves). It **omits the craft and equip actions** in the plan. The true plan is
≈ 15 mints + 2 `Craft(ash_plank)` + 1 `Craft(feather_coat)` + 1 `Equip` ≈ **19
actions > 15** — no plan exists within depth 15. So the goal is admitted, the A*
search exhausts the depth and returns `plan_len=0`, and `objective_step_goal`'s
branch-1 (`goals/progression.py` via `strategy_driver.py:488-493`) returns the
empty-plan `UpgradeEquipmentGoal` instead of falling to branch-3
(`gather_step_target` → incremental gather), so the cycle makes zero progress and
the arbiter falls to `GrindCharacterXP(green_slime)`.

This is an **unproven trust boundary**: the formal `plan_length_le_max_depth`
(`PlannerDepthBound.lean`) bounds the planner's OUTPUT, but nothing binds the
admission estimate (`min_gathers`) to the actual plan length. `min_gathers` is a
lower bound on GATHERS, used as if it bounded TOTAL plan length — it doesn't.

## Goal

Tighten the depth-admission estimate to count **all mandatory plan actions**
(mints + crafts + equip), and **prove it is a sound lower bound on plan length**,
so admission can never claim "plannable" for a goal that is unplannable purely
because of the omitted craft/equip steps. With the estimate honest, feather_coat
(≈19 > 15) is correctly REJECTED → `objective_step_goal` falls to branch-3
(`gather_step_target` → gather ash_wood incrementally) → the chain shortens →
`UpgradeEquipment` becomes genuinely plannable → the bot fights chickens for the
final feathers (live-verified: `GatherMaterials(feather,{feather:5})` plans to
`Fight(chicken)×5`).

## The discovered gap this discharges (why the proof is the centerpiece)

The existing depth-bound proof (`PlannerDepthBound.lean:94-103`,
`reachable_not_satisfying_when_lb_exceeds_depth`) proves the *mechanism* — IF a
sound lower bound `lb` on satisfying-plan length exceeds `maxDepth`, no reachable
node is satisfied — but it takes the lower-bound property as an **UNPROVEN
HYPOTHESIS**:

```lean
(hsat_lb : ∀ n, satisfyingLen n → n.planLen ≥ lb)   -- assumed, never discharged
```

`satisfyingLen` is an abstract `Node → Prop` with no tie to the action semantics
or to what `minGathers` computes. So the production gate `is_plannable` rests on
an *assumed* connection between its estimate and real plan length. That assumption
is the trust gap. **This work DISCHARGES it** (full, zero assumed hypothesis).

## What is proven — and what is NOT (honest scope)

**PROVEN (full discharge):**
- A minimal **plan-action model** in Lean: an `Action` (`gather code | craft code
  | equip code`), a `Plan = List Action`, and an `apply`/`produces` semantics
  giving the multiset of items a plan yields from `owned` holdings, plus a
  predicate `SatisfiesEquip plan item` ("plan crafts and equips `item`").
- A new pure core `min_plan_length(item, recipes, owned)` = `mints + crafts +
  equip` (mints = `min_gathers`; crafts = one per craftable closure node needing
  production; equip = 1 for an equippable).
- **Theorem `min_plan_length_le_plan` (the discharge):** for every `Plan P` with
  `SatisfiesEquip P item`, `min_plan_length(item, recipes, owned) ≤ P.length`.
  Sub-lemmas: `min_gathers ≤ (gather actions in P)` (mass-conservation induction
  over the recipe DAG); `crafts ≤ (craft actions in P)`; `1 ≤ (equip actions in
  P)`; the three action kinds are disjoint so the sum bounds `P.length`.
- **`hsat_lb` is then DISCHARGED**, not assumed: instantiate
  `reachable_not_satisfying_when_lb_exceeds_depth` with `lb = min_plan_length` and
  `satisfyingLen = SatisfiesEquip`, proving the hypothesis from
  `min_plan_length_le_plan`. Result:
  **`min_plan_length(item) > max_depth ⟹ no satisfying plan within max_depth`**,
  with NO remaining assumption — so `is_plannable = False` is proven sound, and
  the crafts+equip terms remove the `mints == max_depth` over-admit.
- Production `min_plan_length` is bound to the Lean model by the differential +
  mutation gate (same function over all inputs), like `min_gathers`
  (`Extracted/MinGathers.lean` + `test_gather_step_target_diff.py`).

**NOT proven — stated, not claimed (named in the theorem docstrings):**
- A* **completeness within the time budget** — a plan may exist but the bounded
  search times out. We do not prove the planner finds every plan.
- **Movement / inventory-space** contributions to plan length — the model counts
  gather/craft/equip actions, not travel or deposit/discard interleavings.
- Therefore `is_plannable = True` stays **necessary, not sufficient**: "not
  excluded by the proven depth lower bound," NOT "a plan is guaranteed." No
  theorem or docstring claims full planner completeness; the model abstracts the
  action set to exactly the kinds the lower bound counts.

Headline, exactly: **the depth-admission estimate is proven (no assumed
hypothesis) to be a sound lower bound on true plan length** for the gather/craft/
equip action model — eliminating the false-"plannable" verdict from omitted
craft/equip actions, and discharging the previously-assumed `hsat_lb`.

## Components

### 1. `min_plan_length` pure core (NEW)
`src/artifactsmmo_cli/ai/min_plan_length.py` —
`min_plan_length(item, qty, recipes, owned) -> int`. Builds on `min_gathers`:
- `mints` = `min_gathers(item, qty, recipes, owned)` (unchanged lower bound on
  leaf acquisitions — gathers + monster-drop fights).
- `crafts` = the number of CRAFT actions in the recipe closure that are NOT
  already covered by held intermediates — i.e. one craft per craftable node that
  must be produced (recipe-closure count, holdings-credited, mirroring
  `min_gathers`'s greedy-consume). A raw leaf contributes 0 crafts.
- `equip` = `1` when the caller is acquiring an equippable for its slot
  (UpgradeEquipment), else `0`.
- `min_plan_length = mints + crafts + equip`.
Pure, fuel-bounded recursion mirroring `min_gathers._min_gathers` so it extracts
to Lean cleanly.

### 2. `is_plannable` rewire
`goals/progression.py:139-142`: replace
`gathers = ceil_gathers(min_gathers(item, 1, ...)); return gathers <= max_depth`
with the full estimate. Note `ceil_gathers` divides mints by `max_gather_yield`
(a gather yields ≥1 unit) — crafts/equip are 1 action each and are NOT divided.
So: `return ceil_gathers(min_gathers(...), max_yield) + crafts + equip <= max_depth`.
(Compute crafts/equip via `min_plan_length` split, or have `min_plan_length`
take `max_gather_yield` and apply the divide internally to the mint term only.)
The skill-gate fast-fail check above it (lines 135-138) is unchanged.

### 3. Lean plan-action model + discharge proof (the centerpiece)
`formal/Formal/PlanModel.lean` (new) + additions to `PlannerDepthBound.lean`:
- `Action` (`gather String | craft String | equip String`), `Plan := List Action`,
  an `apply`/`produces : Plan → owned → Multiset/assoc-list of items`, and
  `SatisfiesEquip : Plan → String → Prop` ("plan crafts+equips the item").
- `minPlanLength` def (mirrors the production core), extracted to `Extracted/`.
- **Sub-lemmas** (the real proof work):
  - `minGathers_le_gathers` — `min_gathers(item) ≤ (# gather actions in P)` for any
    `P` producing `item`; mass-conservation induction over the recipe DAG with
    holdings credited (mirrors `_min_gathers`'s greedy consume).
  - `crafts_le_crafts` — one craft per produced craftable node ≤ `# craft actions`.
  - `one_le_equips` — `SatisfiesEquip ⟹ ≥ 1 equip action`.
  - disjointness of the three action kinds ⇒ `minPlanLength ≤ P.length`
    (`min_plan_length_le_plan`).
- **Discharge:** `min_plan_length_gt_maxDepth_imp_no_plan` instantiates
  `reachable_not_satisfying_when_lb_exceeds_depth` with `lb = minPlanLength`,
  `satisfyingLen = SatisfiesEquip`, hypothesis proved by `min_plan_length_le_plan`
  — NO assumed `hsat_lb`. Replace/retire the assumed-hypothesis
  `copper_boots_unreachable_under_upgrade_depth` with the discharged version.
- Each "NOT proven" boundary (A* completeness, movement, inventory) is named in
  the theorem docstrings so the model's abstraction is explicit, not hidden.

### 4. Differential + mutation
`formal/diff/` — a `test_min_plan_length_diff.py` (or extend
`test_gather_step_target_diff.py`) asserting production `min_plan_length` ==
oracle over Hypothesis-generated recipe/holdings inputs; `mutate.py` anchors so a
weakened estimate (e.g. dropping the craft term — the exact bug) fails the build.

## Behavioral outcome (verified mechanically)
With the honest estimate, feather_coat from scratch → `min_plan_length ≈ 19 > 15`
→ `is_plannable = False` → branch-3 `gather_step_target(feather_coat, ash_plank)`
→ `GatherMaterials(ash_wood)` (flat, plannable) → planks accumulate → chosen step
advances → once the remaining chain ≤ depth, `UpgradeEquipment` plans and emits
`Fight(chicken)` for feathers. Incremental progress every cycle; no empty-plan
stall; no slime-leveling fallback for an attainable gear objective.

## Testing / success criteria
- `min_plan_length` unit tests: raw leaf (= min_gathers), 1-level craft
  (mints + 1 craft), feather_coat (mints + 3 crafts + 1 equip > 15), holdings
  credited (planks/feathers in hand lower the count).
- `is_plannable` regression: feather_coat from scratch → False; feather_coat with
  ash_plank in hand and few feathers left → True (short chain); a shallow gear
  (copper_helmet with bars in hand) stays True.
- An end-to-end objective-step test: committed feather_coat from scratch →
  `objective_step_goal` returns a `GatherMaterials` step (NOT an empty-plan
  `UpgradeEquipment`), and is non-None (no fallthrough to char-level when the
  gear is attainable).
- Lean: `lake build` 0 sorry; the plan-action model + `min_plan_length_le_plan`
  proven; `hsat_lb` DISCHARGED (the no-plan theorem has no assumed lower-bound
  hypothesis — grep the final theorem for a residual `hsat_lb`/`planLen ≥`
  hypothesis and confirm it is gone); axiom-clean (no new `axiom`/`sorry`/
  `native_decide`); the per-axiom liveness gate passes. Differential green;
  mutation kills the drop-craft-term mutant.
- `formal/gate.sh` ALL GATE PARTS PASSED; full Python suite 100% coverage.

## Non-goals / YAGNI
- No change to the planner's A* search, budget, or `max_depth` value.
- No proof of A* completeness / movement / inventory-space plan-length terms.
- No change to `min_gathers` itself (it stays the leaf-mint lower bound;
  `min_plan_length` composes it).
- No change to root selection (the zombie fix already routes to feather_coat).
