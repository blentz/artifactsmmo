-- @concept: core, planner @property: safety
/-
Formal model of the Action.cost(...) ≥ 0 contract that seals the Phase-2
Dijkstra-optimality proof (`PlannerAdmissibility.lean`).

The Phase-2 proof has `cost ≥ 0` as a load-bearing precondition (see
`planner.py:81` comment + `zero_h_admissible` chain). Phase-3 Task 4
discharges this precondition for the entire concrete Action set under
`src/artifactsmmo_cli/ai/actions/`.

# Structural audit (every concrete Action subclass)

All formulas fall into a small set of structural buckets:

* **Constant** — Equip=1, Unequip=1, Transition=3, MoveSemantic=1,
  Claim=1, Consumable∈{2,100}. Trivially ≥ 0.
* **HP-deficit-dependent** — Rest = `max(3, ⌈missing_HP%⌉)/10` (real server
  cooldown scaled to the 10s cost unit; full-HP rest = 10, min 3/10). No longer
  constant; `≥ 3/10 > 0` via the `max 3` floor.
* **Distance + positive const** — AcceptTask, CompleteTask, TaskCancel,
  TaskExchange, TaskTrade, DepositGold, DepositAll, WithdrawGold,
  WithdrawItem, NpcSell, Npc, BankExpansion, OptimizeLoadout. Formula
  `base + dist` with `dist = |Δx|+|Δy| ≥ 0`.
* **Distance + per-qty** — Craft=5·qty+d, Recycle=3·qty+d. Formula
  `base + per_unit·qty + dist`.
* **Instance-parameterized** — Delete (`cost_weight ∈ {5,25,50}` from
  `player_helpers.delete_cost`).
* **History-dependent** — Fight=10+d (+LOADOUT_PENALTY), Gather=6+d,
  Move=max(5d,1). Formula `if no_hist: static else: learned/max(rate, 0.1)`.

# Writer audit for actual_cooldown_seconds

The history-dependent branch's `learned` comes from
`LearningStore.action_cost = median(Cycle.actual_cooldown_seconds)`. Every
writer site produces a non-negative value:

* `src/artifactsmmo_cli/ai/player.py:312`  writes `0.0`               (no-plan branch)
* `src/artifactsmmo_cli/ai/player.py:362`  writes `max(0.0, …)`        (execute branch)

`statistics.median` over non-negative reals is non-negative, so the stored
fact `learned ≥ 0` holds for every concrete query. The denominator
`max(rate, 0.1) ≥ 0.1 > 0` is bounded away from zero. Hence
`learned / max(rate, 0.1) ≥ 0`.

The pure cost cores live in `src/artifactsmmo_cli/ai/actions/cost_core.py`
(`distance_cost_pure`, `qty_cost_pure`, `learned_cost_pure`); the
differential test (`formal/diff/test_action_cost_nonneg_diff.py`) exercises
them against this Lean model.

Lean core only — no mathlib. `Rat` literals constructed via `mkRat` so the
`decide` reduction terminates.
-/

namespace Formal.ActionCostNonneg

/-! ## Bucket 1 — constant cost (`Nat`). -/

def constantCost (k : Nat) : Nat := k

theorem constantCost_nonneg (k : Nat) : 0 ≤ constantCost k := by
  simp [constantCost]

/-! ## Bucket 2 — distance + base (`Nat`). -/

def distanceCost (base d : Nat) : Nat := base + d

theorem distanceCost_nonneg (base d : Nat) : 0 ≤ distanceCost base d := by
  simp [distanceCost]

theorem distanceCost_ge_base (base d : Nat) : base ≤ distanceCost base d := by
  unfold distanceCost; omega

/-! ## Bucket 3 — distance + per-qty + base (`Nat`). -/

def qtyCost (base qty d perUnit : Nat) : Nat := base + perUnit * qty + d

theorem qtyCost_nonneg (base qty d perUnit : Nat) :
    0 ≤ qtyCost base qty d perUnit := by
  simp [qtyCost]

/-- Per the planner contract `qty ≥ 1` (from `is_applicable`), the per-qty
term contributes at least `perUnit`. -/
theorem qtyCost_ge_per_unit (base d perUnit : Nat) (qty : Nat) (hq : 1 ≤ qty) :
    base + perUnit ≤ qtyCost base qty d perUnit := by
  simp [qtyCost]
  have : perUnit ≤ perUnit * qty := by
    have := Nat.mul_le_mul_left perUnit hq
    simpa [Nat.mul_one] using this
  omega

/-! ## Bucket 4 — history-dependent cost (`Rat`). -/

/-- Symmetric two-arg `max` for `Rat`. -/
def ratMax (a b : Rat) : Rat := if a < b then b else a

theorem ratMax_ge_right (a b : Rat) : b ≤ ratMax a b := by
  unfold ratMax; split
  · exact Rat.le_refl
  · rename_i h; exact Rat.not_lt.mp h

theorem ratMax_ge_left (a b : Rat) : a ≤ ratMax a b := by
  unfold ratMax; split
  · rename_i h; exact Rat.le_of_lt h
  · exact Rat.le_refl

theorem ratMax_pos_of_right_pos (a b : Rat) (hb : 0 < b) : 0 < ratMax a b := by
  have := ratMax_ge_right a b
  grind

/-- The history-fraction core: `learned / max(rate, rateFloor)`. -/
def learnedFraction (learned rate rateFloor : Rat) : Rat :=
  learned / ratMax rate rateFloor

/-- **History-cost non-negativity**. Under the verified writer-site invariant
`learned ≥ 0` and `rateFloor > 0` (production value `1/10`), the history
fraction is non-negative regardless of `rate`. -/
theorem learnedFraction_nonneg
    (learned rate rateFloor : Rat)
    (hl : 0 ≤ learned) (hf : 0 < rateFloor) :
    0 ≤ learnedFraction learned rate rateFloor := by
  unfold learnedFraction
  have hd : 0 < ratMax rate rateFloor := ratMax_pos_of_right_pos rate rateFloor hf
  rw [Rat.div_def]
  exact Rat.mul_nonneg hl (Rat.le_of_lt (Rat.inv_pos.mpr hd))

/-- Combined: the static-or-learned switch (mirror of `learned_cost_pure`). -/
def learnedCost (static learned rate rateFloor : Rat)
    (confidentThreshold : Rat) (hasHistory : Bool) : Rat :=
  if ¬ hasHistory then static
  else if rate < confidentThreshold then learned / ratMax rate rateFloor
  else learned

theorem learnedCost_nonneg
    (static learned rate rateFloor : Rat)
    (confidentThreshold : Rat)
    (hasHistory : Bool)
    (hs : 0 ≤ static) (hl : 0 ≤ learned) (hf : 0 < rateFloor) :
    0 ≤ learnedCost static learned rate rateFloor confidentThreshold hasHistory := by
  unfold learnedCost
  split
  · exact hs
  · split
    · have hd : 0 < ratMax rate rateFloor := ratMax_pos_of_right_pos rate rateFloor hf
      rw [Rat.div_def]
      exact Rat.mul_nonneg hl (Rat.le_of_lt (Rat.inv_pos.mpr hd))
    · exact hl

/-! ## Per-action wrapper theorems. -/

-- Bucket 1b: HP-deficit-dependent cost (`Rat`) — Rest. Real server cooldown
-- `max(3, ⌈missing_HP%⌉)` seconds scaled to the 10s cost unit. `missing` is the
-- Nat truncated sub `maxHp - hp` (0 when hp ≥ maxHp); the Nat ceil
-- `(missing*100 + maxHp - 1)/maxHp` agrees with the Python
-- `-(-(missing*100)//max_hp)` for all inputs (incl. missing=0 → 0). The `max 3`
-- floor makes `restCost ≥ 3/10 > 0`, so non-negativity is trivial.
def restCost (hp maxHp : Nat) : Rat :=
  ((max 3 (((maxHp - hp) * 100 + maxHp - 1) / maxHp) : Nat) : Rat) / 10

theorem restCost_nonneg (hp maxHp : Nat) : 0 ≤ restCost hp maxHp := by
  unfold restCost
  rw [Rat.div_def]
  exact Rat.mul_nonneg (by exact_mod_cast Nat.zero_le _)
    (Rat.le_of_lt (Rat.inv_pos.mpr (by decide)))

-- Bucket 1: constants. Production values, all in `Nat`.
def equipCost : Nat := 1
def unequipCost : Nat := 1
def transitionCost : Nat := 3
def moveSemanticCost : Nat := 1
def claimCost : Nat := 1
def consumableCostFit : Nat := 2
def consumableCostOverheal : Nat := 100
def teleportCost : Nat := 20  -- PLAN #6b: flat warp cost (distance-independent); `TeleportAction.cost`

theorem equip_cost_nonneg : 0 ≤ equipCost := by simp [equipCost]
theorem unequip_cost_nonneg : 0 ≤ unequipCost := by simp [unequipCost]
theorem transition_cost_nonneg : 0 ≤ transitionCost := by simp [transitionCost]
theorem move_semantic_cost_nonneg : 0 ≤ moveSemanticCost := by simp [moveSemanticCost]
theorem claim_cost_nonneg : 0 ≤ claimCost := by simp [claimCost]
theorem teleport_cost_nonneg : 0 ≤ teleportCost := by simp [teleportCost]
theorem consumable_cost_fit_nonneg : 0 ≤ consumableCostFit := by simp [consumableCostFit]
theorem consumable_cost_overheal_nonneg : 0 ≤ consumableCostOverheal := by
  simp [consumableCostOverheal]

-- Bucket 2: distance + constant.
def acceptTaskCost (dist : Nat) : Nat := distanceCost 1 dist
def completeTaskCost (dist : Nat) : Nat := distanceCost 1 dist
def taskCancelCost (dist : Nat) : Nat := distanceCost 1 dist
def taskExchangeCost (dist : Nat) : Nat := distanceCost 1 dist
def taskTradeCost (dist : Nat) : Nat := distanceCost 2 dist
def depositGoldCost (dist : Nat) : Nat := distanceCost 2 dist
def withdrawGoldCost (dist : Nat) : Nat := distanceCost 2 dist
def withdrawItemCost (dist : Nat) : Nat := distanceCost 2 dist
/-- `NpcSell = 1.5 + dist`. Modeled as `distance 2 d` (over-approximating by
0.5 in the structural model; the diff test pins the exact Python formula). -/
def npcSellCost (dist : Nat) : Nat := distanceCost 2 dist
def npcBuyCost (dist priceQty : Nat) : Nat := distanceCost 2 dist + priceQty
def bankExpansionCost (dist nextExpansion : Nat) : Nat := distanceCost 5 dist + nextExpansion
/-- `OptimizeLoadout = SWAP_COST_PER_SLOT (5) * 2 * n`. -/
def optimizeLoadoutCost (n : Nat) : Nat := 10 * n
/-- `DepositAll = 2 * |inventory| + dist`. -/
def depositAllCost (invSize dist : Nat) : Nat := 2 * invSize + dist

theorem accept_task_cost_nonneg (d : Nat) : 0 ≤ acceptTaskCost d :=
  distanceCost_nonneg 1 d
theorem complete_task_cost_nonneg (d : Nat) : 0 ≤ completeTaskCost d :=
  distanceCost_nonneg 1 d
theorem task_cancel_cost_nonneg (d : Nat) : 0 ≤ taskCancelCost d :=
  distanceCost_nonneg 1 d
theorem task_exchange_cost_nonneg (d : Nat) : 0 ≤ taskExchangeCost d :=
  distanceCost_nonneg 1 d
theorem task_trade_cost_nonneg (d : Nat) : 0 ≤ taskTradeCost d :=
  distanceCost_nonneg 2 d
theorem deposit_gold_cost_nonneg (d : Nat) : 0 ≤ depositGoldCost d :=
  distanceCost_nonneg 2 d
theorem withdraw_gold_cost_nonneg (d : Nat) : 0 ≤ withdrawGoldCost d :=
  distanceCost_nonneg 2 d
theorem withdraw_item_cost_nonneg (d : Nat) : 0 ≤ withdrawItemCost d :=
  distanceCost_nonneg 2 d
theorem npc_sell_cost_nonneg (d : Nat) : 0 ≤ npcSellCost d :=
  distanceCost_nonneg 2 d
theorem npc_buy_cost_nonneg (d p : Nat) : 0 ≤ npcBuyCost d p := by
  simp [npcBuyCost, distanceCost]
theorem bank_expansion_cost_nonneg (d e : Nat) : 0 ≤ bankExpansionCost d e := by
  simp [bankExpansionCost, distanceCost]
theorem optimize_loadout_cost_nonneg (n : Nat) : 0 ≤ optimizeLoadoutCost n := by
  simp [optimizeLoadoutCost]
theorem deposit_all_cost_nonneg (i d : Nat) : 0 ≤ depositAllCost i d := by
  simp [depositAllCost]

-- Bucket 3: distance + per-qty.
def craftCost (qty d : Nat) : Nat := qtyCost 0 qty d 5
def recycleCost (qty d : Nat) : Nat := qtyCost 0 qty d 3

theorem craft_cost_nonneg (qty d : Nat) : 0 ≤ craftCost qty d :=
  qtyCost_nonneg 0 qty d 5
theorem recycle_cost_nonneg (qty d : Nat) : 0 ≤ recycleCost qty d :=
  qtyCost_nonneg 0 qty d 3

-- Bucket 4: instance-parameterized (delete).
def deleteCost (branch : Nat) : Nat :=
  match branch with
  | 0 => 50
  | 1 => 25
  | _ => 5

theorem delete_cost_nonneg (b : Nat) : 0 ≤ deleteCost b := by
  unfold deleteCost
  split <;> simp

-- Bucket 5: history-dependent. Production rate floor and confident
-- threshold pinned as `Rat` literals via `mkRat` so `decide` terminates.
/-- Production rate floor = `1/10`. -/
def rateFloorProd : Rat := mkRat 1 10
/-- Production confident threshold = `95/100`. -/
def confidentThresholdProd : Rat := mkRat 95 100

theorem rateFloorProd_pos : 0 < rateFloorProd := by
  unfold rateFloorProd; decide

/-- `Fight = (10 + dist) + LOADOUT_PENALTY?` via the history-fraction core. -/
def fightCost (dist : Nat) (learned rate : Rat) (loadoutPenalty : Rat) : Rat :=
  let static : Rat := (10 + dist : Nat)
  learnedCost static learned rate rateFloorProd confidentThresholdProd true + loadoutPenalty

theorem fight_cost_nonneg (dist : Nat) (learned rate loadoutPenalty : Rat)
    (hl : 0 ≤ learned) (hp : 0 ≤ loadoutPenalty) :
    0 ≤ fightCost dist learned rate loadoutPenalty := by
  unfold fightCost
  have hs : (0 : Rat) ≤ ((10 + dist : Nat) : Rat) := by exact_mod_cast Nat.zero_le _
  have h1 := learnedCost_nonneg ((10 + dist : Nat) : Rat) learned rate
    rateFloorProd confidentThresholdProd true hs hl rateFloorProd_pos
  exact Rat.add_nonneg h1 hp

/-- `Gather = 6 + dist` via the history-fraction core. -/
def gatherCost (dist : Nat) (learned rate : Rat) : Rat :=
  let static : Rat := (6 + dist : Nat)
  learnedCost static learned rate rateFloorProd confidentThresholdProd true

theorem gather_cost_nonneg (dist : Nat) (learned rate : Rat) (hl : 0 ≤ learned) :
    0 ≤ gatherCost dist learned rate := by
  unfold gatherCost
  have hs : (0 : Rat) ≤ ((6 + dist : Nat) : Rat) := by exact_mod_cast Nat.zero_le _
  exact learnedCost_nonneg ((6 + dist : Nat) : Rat) learned rate
    rateFloorProd confidentThresholdProd true hs hl rateFloorProd_pos

/-- `Move = max(d*5, 1)` via the history-fraction core. -/
def moveCost (dist : Nat) (learned rate : Rat) : Rat :=
  let static : Rat := ((max (dist * 5) 1 : Nat) : Rat)
  learnedCost static learned rate rateFloorProd confidentThresholdProd true

theorem move_cost_nonneg (dist : Nat) (learned rate : Rat) (hl : 0 ≤ learned) :
    0 ≤ moveCost dist learned rate := by
  unfold moveCost
  have hs : (0 : Rat) ≤ ((max (dist * 5) 1 : Nat) : Rat) := by
    exact_mod_cast Nat.zero_le _
  exact learnedCost_nonneg ((max (dist * 5) 1 : Nat) : Rat) learned rate
    rateFloorProd confidentThresholdProd true hs hl rateFloorProd_pos

/-! ## Headline theorem: the Phase-2 admissibility precondition.

Every concrete Action in `src/artifactsmmo_cli/ai/actions/` returns a
non-negative cost under its enforced invariants. -/

inductive ActionTag where
  | const  (k : Nat)
  | dist   (base d : Nat)
  | qty    (base qty d perUnit : Nat)
  | hist   (static learned rate rateFloor confidentThreshold : Rat)
            (hasHistory : Bool)
  deriving Repr

def evalCost : ActionTag → Rat
  | .const k => (k : Rat)
  | .dist base d => ((distanceCost base d : Nat) : Rat)
  | .qty base qty d perUnit => ((qtyCost base qty d perUnit : Nat) : Rat)
  | .hist s l r rf ct h => learnedCost s l r rf ct h

/-- Under the verified writer invariants (the `hist` constructor's three
non-negativity preconditions), every concrete Action's modeled cost is ≥ 0.
This is the seal on `PlannerAdmissibility.lean`. -/
theorem all_actions_cost_nonneg : ∀ (t : ActionTag),
    (∀ s l r rf ct h, t = .hist s l r rf ct h →
      0 ≤ s ∧ 0 ≤ l ∧ 0 < rf) →
    0 ≤ evalCost t := by
  intro t hyp
  cases t with
  | const k =>
    show (0 : Rat) ≤ (k : Rat)
    exact_mod_cast Nat.zero_le k
  | dist base d =>
    show (0 : Rat) ≤ ((distanceCost base d : Nat) : Rat)
    exact_mod_cast Nat.zero_le _
  | qty base qty d perUnit =>
    show (0 : Rat) ≤ ((qtyCost base qty d perUnit : Nat) : Rat)
    exact_mod_cast Nat.zero_le _
  | hist s l r rf ct h =>
    obtain ⟨hs, hl, hf⟩ := hyp s l r rf ct h rfl
    show 0 ≤ learnedCost s l r rf ct h
    exact learnedCost_nonneg s l r rf ct h hs hl hf

end Formal.ActionCostNonneg
