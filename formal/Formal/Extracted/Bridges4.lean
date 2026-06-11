import Formal.Extracted.InventoryCaps
import Formal.InventoryCaps
import Formal.InventoryProfile

/-!
# Extracted ↔ hand-model bridge lemmas, part 4 (P3b: inventory_caps)

HAND-WRITTEN (size split of Bridges.lean/Bridges2.lean/Bridges3.lean; same
namespace). The P3b wave hoisted the GameData/WorldState reads out of
`inventory_caps.py` into pure cores over plain data (scalar state fields, a
`recipes` mapping, per-peer dominance verdicts), mechanically extracted to
`Formal/Extracted/InventoryCaps.lean`. This file proves them against the two
pre-existing hand models.

* `overstock_excess_bridge` — FULL bridge: the extracted `overstock_excess`
  (the live space-driven, profile-preserving overstock core) equals the
  proved `Formal.InventoryProfile.overstockExcess` for EVERY input. The two
  design guarantees transfer to the extracted def:
  `overstock_profile_protection_extracted` (held ≤ target ⇒ never shed) and
  `overstock_below_watermark_extracted` (free slots ⇒ nothing is overstock).

* `dominated_bridge` — FULL bridge: the extracted `_is_dominated_pure` fold
  equals the hand `Formal.InventoryCaps.isDominatedBy` over the `Peer`
  encoding (criteria verdicts + owned count), for EVERY peer list and slot
  count — NO wellformedness hypothesis. Honesty note: the original Python
  walked an unordered SET with a prefix-sum early return, which is
  order-DEPENDENT for negative owned counts (unreachable: owned counts are
  sums of inventory/bank/equipped quantities ≥ 0) — the hand model always
  encoded the order-independent total-sum threshold. P3b aligned the Python
  core to the total sum (the only deterministic semantics on the full
  domain), making the universal bridge true rather than carrying a
  non-negativity hypothesis. The production wrapper's `slot_count ≥ 1`
  guard (`if not slots: return False`) stays outside the core: at
  `slot_count ≤ 0` BOTH sides answer `true` (0 ≥ slot_count) — they agree,
  and the hand safety theorem `isDominatedBy_nil_of_positive_slot` carries
  the same `≥ 1` hypothesis. `equip_cap_from_peers_extracted` composes the
  extracted dominance verdict into the hand `equipCapFromPeers`.

* `cap_excl_bridge` / `cap_bridge` — FULL bridges at the extracted plumbing
  term `eTaskCap` (the P3a `eMats`/`eHeld` style): the extracted cap cores
  equal the hand `Formal.InventoryCaps.capExclWith`/`capWith` with the
  equippable/consumable components given by the proved `equipCapValue`/
  `consumableCapValue` predicate models and the task component given by
  `eTaskCap` (gate + remaining + recipe-chain demand). The recipe-chain
  demand itself has NO hand model (the hand `capExclWith` takes
  `taskRemaining` as an input — its computation was always Python-side);
  the extracted `_task_chain_demand_pure` is pinned by the kernel-checked
  lemmas below plus the 300-case differential oracle. Transferred safety:
  `cap_equipped_ge_one_extracted` (an equipped item's cap is never below 1
  — the discard ladder cannot delete the equipped copy) and
  `cap_safety_floor_extracted` (a recipe-demanded item never caps below the
  safety floor).

* `_task_chain_demand_pure` lemmas — extracted-only (no hand counterpart):
  `chain_demand_fuel_zero` (base case), `chain_demand_target_self` (the
  task item itself demands exactly the remaining quantity),
  `chain_demand_visited_blocked` (cycle guard: a revisited root contributes
  0), `chain_pin_cycle` (a self-referential recipe terminates at 0) and
  `chain_pin_ash` (the 2026-06-05 ash_plank→ash_wood 1:1 production trace:
  10 remaining planks demand exactly 10 wood).

Lean core only — no Mathlib. Integer arithmetic via `omega`.
-/

namespace Extracted.Bridges

open Formal.InventoryCaps (Peer)

/-! ### overstock_excess ↔ Formal.InventoryProfile.overstockExcess -/

/-- FULL bridge: extracted `overstock_excess` = hand `overstockExcess`,
for every input (the guard negation `¬(cap ≤ 0 ∨ used·den < cap·num)` is
exactly the hand `underPressure`). -/
theorem overstock_excess_bridge
    (held profileTarget usefulFloor used cap wNum wDen : Int) :
    Extracted.InventoryCaps.overstock_excess
        held profileTarget usefulFloor used cap wNum wDen
      = Formal.InventoryProfile.overstockExcess
          held profileTarget usefulFloor used cap wNum wDen := by
  simp only [Extracted.InventoryCaps.overstock_excess,
    Formal.InventoryProfile.overstockExcess,
    Formal.InventoryProfile.underPressure,
    Formal.InventoryProfile.protectedFloor]
  repeat' split
  all_goals (try simp_all)
  all_goals omega

/-- PROFILE-PROTECTION transferred: the extracted live core never sheds an
item at or below its profile target, regardless of space pressure. -/
theorem overstock_profile_protection_extracted
    (held profileTarget usefulFloor used cap wNum wDen : Int)
    (h : held ≤ profileTarget) :
    Extracted.InventoryCaps.overstock_excess
        held profileTarget usefulFloor used cap wNum wDen = 0 := by
  rw [overstock_excess_bridge]
  exact Formal.InventoryProfile.profile_protection
    held profileTarget usefulFloor used cap wNum wDen h

/-- SPACE-DRIVEN transferred: below the watermark (real free slots) the
extracted live core reports nothing as overstock. -/
theorem overstock_below_watermark_extracted
    (held profileTarget usefulFloor used cap wNum wDen : Int)
    (h : Formal.InventoryProfile.underPressure used cap wNum wDen = false) :
    Extracted.InventoryCaps.overstock_excess
        held profileTarget usefulFloor used cap wNum wDen = 0 := by
  rw [overstock_excess_bridge]
  exact Formal.InventoryProfile.no_overstock_below_watermark
    held profileTarget usefulFloor used cap wNum wDen h

/-! ### _is_dominated_pure ↔ Formal.InventoryCaps.isDominatedBy -/

/-- The hand `Peer` record encoded as the extracted core's verdict tuple. -/
def encPeer (p : Peer) : Bool × Bool × Bool × Int :=
  (p.fitsAllSlots, p.strictlyHigher, p.coversSkillEffects, p.ownedCount)

/-- The extracted fold step (the generated `List.foldl` lambda, zeta-reduced). -/
def eDomStep (acc : Int) (x : Bool × Bool × Bool × Int) : Int :=
  if x.1 && x.2.1 && x.2.2.1 then acc + x.2.2.2 else acc

/-- The extracted def IS the `eDomStep` fold compared to the threshold. -/
theorem is_dominated_pure_eq_fold
    (l : List (Bool × Bool × Bool × Int)) (s : Int) :
    Extracted.InventoryCaps._is_dominated_pure l s
      = decide (l.foldl eDomStep 0 ≥ s) := rfl

/-- One fold step credits exactly the hand `Peer.contribution`. -/
private theorem eDomStep_encPeer (acc : Int) (p : Peer) :
    eDomStep acc (encPeer p) = acc + p.contribution := by
  simp only [eDomStep, encPeer, Formal.InventoryCaps.Peer.contribution,
    Formal.InventoryCaps.Peer.qualifies]
  split <;> simp_all <;> omega

/-- Int `foldl (+)` shifts its initial accumulator out front. -/
private theorem foldl_add_shift (l : List Int) (a : Int) :
    l.foldl (· + ·) a = a + l.foldl (· + ·) 0 := by
  induction l generalizing a with
  | nil => simp
  | cons x xs ih =>
    simp only [List.foldl]
    rw [ih (a + x), ih (0 + x)]
    omega

/-- The extracted fold over encoded peers = initial accumulator + the hand
`dominatorOwned` total. -/
private theorem eDomStep_fold_shift (peers : List Peer) (acc : Int) :
    (peers.map encPeer).foldl eDomStep acc
      = acc + Formal.InventoryCaps.dominatorOwned peers := by
  induction peers generalizing acc with
  | nil => simp [Formal.InventoryCaps.dominatorOwned]
  | cons p ps ih =>
    simp only [List.map, List.foldl, Formal.InventoryCaps.dominatorOwned]
    rw [ih, eDomStep_encPeer]
    rw [foldl_add_shift ((ps.map Formal.InventoryCaps.Peer.contribution)) (0 + p.contribution)]
    have : Formal.InventoryCaps.dominatorOwned ps
        = (ps.map Formal.InventoryCaps.Peer.contribution).foldl (· + ·) 0 := rfl
    omega

/-- FULL bridge: extracted `_is_dominated_pure` over the `Peer` encoding =
hand `isDominatedBy`, for EVERY peer list and slot count (see the module
docstring for the order-independence honesty note). -/
theorem dominated_bridge (peers : List Peer) (slot_count : Int) :
    Extracted.InventoryCaps._is_dominated_pure (peers.map encPeer) slot_count
      = Formal.InventoryCaps.isDominatedBy peers slot_count := by
  rw [is_dominated_pure_eq_fold, eDomStep_fold_shift]
  simp [Formal.InventoryCaps.isDominatedBy]

/-- The extracted dominance verdict composes into the hand
`equipCapFromPeers` component derivation (the full equippable-cap pipeline
in Lean: criteria fold → dominance threshold → cap value). -/
theorem equip_cap_from_peers_extracted
    (isEquippable : Bool) (peers : List Peer) (slotCount : Int) :
    Formal.InventoryCaps.equipCapValue isEquippable
        (Extracted.InventoryCaps._is_dominated_pure (peers.map encPeer) slotCount)
      = Formal.InventoryCaps.equipCapFromPeers isEquippable peers slotCount := by
  rw [dominated_bridge]
  rfl

/-! ### _task_chain_demand_pure (extracted-only: the hand `capExclWith`
takes `taskRemaining` as an input — the chain computation never had a hand
model; pinned here + covered by the differential oracle). -/

/-- Fuel-zero base case (unreachable from the wrappers: the
`len(recipes) + 1` seed exceeds every path, which marks a distinct key per
recursing frame). -/
theorem chain_demand_fuel_zero (target root : String) (qty : Int)
    (recipes : List (String × List (String × Int)))
    (visited : List (String × Int)) :
    Extracted.InventoryCaps._task_chain_demand_pure 0 target root qty
      recipes visited = 0 := rfl

/-- The task item itself demands exactly the remaining quantity. -/
theorem chain_demand_target_self (fuel : Nat) (item : String) (qty : Int)
    (recipes : List (String × List (String × Int)))
    (visited : List (String × Int)) :
    Extracted.InventoryCaps._task_chain_demand_pure (fuel + 1) item item qty
      recipes visited = qty := by
  simp [Extracted.InventoryCaps._task_chain_demand_pure]

/-- Cycle guard: a revisited root contributes 0 (no infinite recursion,
no double-counting through recycle loops). -/
theorem chain_demand_visited_blocked (fuel : Nat) (target root : String)
    (qty : Int) (recipes : List (String × List (String × Int)))
    (visited : List (String × Int))
    (hne : ¬ (target = root))
    (hv : Extracted.InventoryCaps._dictGetD visited root 0 = 1) :
    Extracted.InventoryCaps._task_chain_demand_pure (fuel + 1) target root qty
      recipes visited = 0 := by
  simp [Extracted.InventoryCaps._task_chain_demand_pure, hne, hv]

/-- Kernel pin: a self-referential recipe terminates at 0 (the per-path
visited map blocks the second visit). -/
theorem chain_pin_cycle :
    Extracted.InventoryCaps._task_chain_demand_pure 2 "gear" "loop" 5
      [("loop", [("loop", 2)])] [] = 0 := by decide

/-- Kernel pin: the 2026-06-05 production trace — with the 1:1
ash_plank ← ash_wood recipe, 10 remaining planks demand exactly 10 wood
(the chain demand that stops DiscardOverstock from deleting mid-chain
materials). -/
theorem chain_pin_ash :
    Extracted.InventoryCaps._task_chain_demand_pure 3 "ash_wood" "ash_plank" 10
      [("ash_plank", [("ash_wood", 1)])] [] = 10 := by decide

/-! ### useful_quantity_cap cores ↔ Formal.InventoryCaps.capExclWith/capWith -/

/-- The extracted task-cap plumbing term: the items-task gate, the
remaining-quantity floor and the recipe-chain demand — exactly the term the
generated `useful_quantity_cap_excl_equipped_pure` computes (the hand model
takes the result as its `taskRemaining` input). -/
def eTaskCap (item_code task_type task_code : String)
    (task_total task_progress : Int)
    (recipes : List (String × List (String × Int))) : Int :=
  if (decide (task_type = "items")) && (!(decide (task_code = ""))) then
    let remaining := max 0 (task_total - task_progress)
    if decide (remaining > 0) then
      Extracted.InventoryCaps._task_chain_demand_pure
        (Int.toNat ((Int.ofNat (List.length recipes)) + 1))
        item_code task_code remaining recipes []
    else 0
  else 0

/-- FULL bridge: the extracted `useful_quantity_cap_excl_equipped_pure` =
the hand `capExclWith` with the equippable/consumable components given by
the proved predicate models and the task component given by `eTaskCap`. -/
theorem cap_excl_bridge (item_code : String)
    (recipe_max batch_buffer safety_floor : Int)
    (task_type task_code : String) (task_total task_progress : Int)
    (recipes : List (String × List (String × Int))) (action_cap : Int)
    (is_equippable is_dominated : Bool) (hp_restore : Int) :
    Extracted.InventoryCaps.useful_quantity_cap_excl_equipped_pure
        item_code recipe_max batch_buffer safety_floor task_type task_code
        task_total task_progress recipes action_cap is_equippable
        is_dominated hp_restore
      = Formal.InventoryCaps.capExclWith batch_buffer safety_floor recipe_max
          (Formal.InventoryCaps.equipCapValue is_equippable is_dominated)
          (Formal.InventoryCaps.consumableCapValue hp_restore)
          action_cap
          (eTaskCap item_code task_type task_code task_total task_progress
            recipes) := by
  simp only [Extracted.InventoryCaps.useful_quantity_cap_excl_equipped_pure,
    eTaskCap, Formal.InventoryCaps.capExclWith,
    Formal.InventoryCaps.recipeCapWith, Formal.InventoryCaps.equipCapValue,
    Formal.InventoryCaps.consumableCapValue,
    Formal.InventoryCaps.equippableKeep, Formal.InventoryCaps.consumableKeep,
    Extracted.InventoryCaps.EQUIPPABLE_KEEP,
    Extracted.InventoryCaps.CONSUMABLE_KEEP]
  repeat' split
  all_goals (try simp_all)
  all_goals omega

/-- FULL bridge: the extracted `useful_quantity_cap_pure` = the hand
`capWith` (the equipped floor of 1 on top of the five-component max). -/
theorem cap_bridge (item_code : String)
    (recipe_max batch_buffer safety_floor : Int)
    (task_type task_code : String) (task_total task_progress : Int)
    (recipes : List (String × List (String × Int))) (action_cap : Int)
    (is_equippable is_dominated : Bool) (hp_restore : Int) (equipped : Bool) :
    Extracted.InventoryCaps.useful_quantity_cap_pure
        item_code recipe_max batch_buffer safety_floor task_type task_code
        task_total task_progress recipes action_cap is_equippable
        is_dominated hp_restore equipped
      = Formal.InventoryCaps.capWith batch_buffer safety_floor recipe_max
          (Formal.InventoryCaps.equipCapValue is_equippable is_dominated)
          (Formal.InventoryCaps.consumableCapValue hp_restore)
          action_cap
          (eTaskCap item_code task_type task_code task_total task_progress
            recipes)
          equipped := by
  simp only [Extracted.InventoryCaps.useful_quantity_cap_pure,
    Formal.InventoryCaps.capWith]
  rw [cap_excl_bridge]

/-- Equipped-floor safety transferred: an equipped item's extracted cap is
never below 1, so the discard ladder cannot delete the equipped copy. -/
theorem cap_equipped_ge_one_extracted (item_code : String)
    (recipe_max batch_buffer safety_floor : Int)
    (task_type task_code : String) (task_total task_progress : Int)
    (recipes : List (String × List (String × Int))) (action_cap : Int)
    (is_equippable is_dominated : Bool) (hp_restore : Int) :
    1 ≤ Extracted.InventoryCaps.useful_quantity_cap_pure
        item_code recipe_max batch_buffer safety_floor task_type task_code
        task_total task_progress recipes action_cap is_equippable
        is_dominated hp_restore true := by
  rw [cap_bridge]
  simp only [Formal.InventoryCaps.capWith, if_true]
  exact Int.le_max_left 1 _

/-- Safety-floor transferred: a recipe-demanded item never caps below the
safety floor (so the bot doesn't immediately re-gather what it discarded). -/
theorem cap_safety_floor_extracted (item_code : String)
    (recipe_max batch_buffer safety_floor : Int)
    (task_type task_code : String) (task_total task_progress : Int)
    (recipes : List (String × List (String × Int))) (action_cap : Int)
    (is_equippable is_dominated : Bool) (hp_restore : Int)
    (h : recipe_max > 0) :
    safety_floor ≤ Extracted.InventoryCaps.useful_quantity_cap_excl_equipped_pure
        item_code recipe_max batch_buffer safety_floor task_type task_code
        task_total task_progress recipes action_cap is_equippable
        is_dominated hp_restore := by
  rw [cap_excl_bridge]
  simp only [Formal.InventoryCaps.capExclWith,
    Formal.InventoryCaps.recipeCapWith, h, if_true]
  omega

end Extracted.Bridges
