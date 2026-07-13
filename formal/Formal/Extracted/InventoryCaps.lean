-- GENERATED from src/artifactsmmo_cli/ai/inventory_caps.py (sha256: 9639304ec50c615cedc3835553ebce4c21b1a6a5391b4de7ee10740768a02f82) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.InventoryCaps

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Python `d[k] = v` over an insertion-ordered association list: replace the
first matching entry in place, else append — every other entry is preserved
bit-for-bit, mirroring dict update semantics (value-polymorphic). -/
def _dictSet {α : Type} (m : List (String × α)) (k : String) (v : α) : List (String × α) :=
  match m with
  | [] => [(k, v)]
  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: _dictSet rest k v

/-- Extracted module constant `EQUIPPABLE_KEEP` (line 116). -/
def EQUIPPABLE_KEEP : Int := 1

/-- Extracted module constant `CONSUMABLE_KEEP` (line 128). -/
def CONSUMABLE_KEEP : Int := 999

/-- Extracted from `overstock_excess` (line 86). -/
def overstock_excess (held : Int) (profile_target : Int) (useful_floor : Int) (used : Int) (cap : Int) (watermark_num : Int) (watermark_den : Int) :
    Int :=
  (if ((decide (cap ≤ 0)) || (decide ((used * watermark_den) < (cap * watermark_num))))
   then
    0
   else
    let floor := (if (decide (profile_target > useful_floor)) then profile_target else useful_floor)
    (if (decide (held > floor))
     then
      (held - floor)
     else
      0))

/-- Extracted from `_is_dominated_pure` (line 229). -/
def _is_dominated_pure (peers : List (Bool × Bool × Bool × Int)) (slot_count : Int) :
    Bool :=
  let dominator_owned := 0
  let dominator_owned := List.foldl
    (fun dominator_owned _x =>
      let fits := (_x.1)
      let higher := (_x.2.1)
      let covers := (_x.2.2.1)
      let owned := (_x.2.2.2)
      let dominator_owned := (if (fits && higher && covers) then (dominator_owned + owned) else dominator_owned)
      dominator_owned)
    dominator_owned peers
  (decide (dominator_owned ≥ slot_count))

/-- Extracted from `_task_chain_demand_pure` (line 351; the Python `fuel <= 0` guard
is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/
def _task_chain_demand_pure :
    Nat → String → String → Int → (List (String × List (String × Int))) → (List (String × Int)) → Int
  | 0, _, _, _, _, _ =>
    0
  | fuel + 1, target_item, root_item, root_qty, recipes, visited =>
    (if (decide (target_item = root_item))
     then
      root_qty
     else
      (if (decide ((_dictGetD visited root_item 0) = 1))
       then
        0
       else
        let recipe := (_dictGetD recipes root_item [])
        let sub := visited
        let sub := (_dictSet sub root_item 1)
        let total := 0
        let total := List.foldl
          (fun total _x =>
            let mat := (_x.1)
            let qty_per := (_x.2)
            let total := (total + (_task_chain_demand_pure fuel target_item mat (qty_per * root_qty) recipes sub))
            total)
          total recipe
        total))

/-- Extracted from `useful_quantity_cap_excl_equipped_pure` (line 377). -/
def useful_quantity_cap_excl_equipped_pure (item_code : String) (recipe_max : Int) (batch_buffer : Int) (safety_floor : Int) (task_type : String) (task_code : String) (task_total : Int) (task_progress : Int) (recipes : List (String × List (String × Int))) (action_cap : Int) (is_equippable : Bool) (is_dominated : Bool) (hp_restore : Int) :
    Int :=
  let recipe_cap := (if (decide (recipe_max > 0)) then (recipe_max * batch_buffer) else 0)
  (if (decide (recipe_max > 0))
   then
    let recipe_cap := (max recipe_cap safety_floor)
    let task_cap := 0
    (if ((decide (task_type = "items")) && (!(decide (task_code = ""))))
     then
      let remaining := (max 0 (task_total - task_progress))
      (if (decide (remaining > 0))
       then
        let no_visited : List (String × Int) := []
        let task_cap := (_task_chain_demand_pure (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item_code task_code remaining recipes no_visited)
        let equippable_cap := 0
        let consumable_cap := 0
        (if (is_equippable && (!is_dominated))
         then
          let equippable_cap := EQUIPPABLE_KEEP
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
         else
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))))
       else
        let equippable_cap := 0
        let consumable_cap := 0
        (if (is_equippable && (!is_dominated))
         then
          let equippable_cap := EQUIPPABLE_KEEP
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
         else
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))))
     else
      let equippable_cap := 0
      let consumable_cap := 0
      (if (is_equippable && (!is_dominated))
       then
        let equippable_cap := EQUIPPABLE_KEEP
        (if (decide (hp_restore > 0))
         then
          let consumable_cap := CONSUMABLE_KEEP
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
         else
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
       else
        (if (decide (hp_restore > 0))
         then
          let consumable_cap := CONSUMABLE_KEEP
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
         else
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))))
   else
    let task_cap := 0
    (if ((decide (task_type = "items")) && (!(decide (task_code = ""))))
     then
      let remaining := (max 0 (task_total - task_progress))
      (if (decide (remaining > 0))
       then
        let no_visited : List (String × Int) := []
        let task_cap := (_task_chain_demand_pure (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item_code task_code remaining recipes no_visited)
        let equippable_cap := 0
        let consumable_cap := 0
        (if (is_equippable && (!is_dominated))
         then
          let equippable_cap := EQUIPPABLE_KEEP
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
         else
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))))
       else
        let equippable_cap := 0
        let consumable_cap := 0
        (if (is_equippable && (!is_dominated))
         then
          let equippable_cap := EQUIPPABLE_KEEP
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
         else
          (if (decide (hp_restore > 0))
           then
            let consumable_cap := CONSUMABLE_KEEP
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
           else
            (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))))
     else
      let equippable_cap := 0
      let consumable_cap := 0
      (if (is_equippable && (!is_dominated))
       then
        let equippable_cap := EQUIPPABLE_KEEP
        (if (decide (hp_restore > 0))
         then
          let consumable_cap := CONSUMABLE_KEEP
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
         else
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap)))))
       else
        (if (decide (hp_restore > 0))
         then
          let consumable_cap := CONSUMABLE_KEEP
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))
         else
          (max recipe_cap (max task_cap (max action_cap (max equippable_cap consumable_cap))))))))

/-- Extracted from `useful_quantity_cap_pure` (line 424). -/
def useful_quantity_cap_pure (item_code : String) (recipe_max : Int) (batch_buffer : Int) (safety_floor : Int) (task_type : String) (task_code : String) (task_total : Int) (task_progress : Int) (recipes : List (String × List (String × Int))) (action_cap : Int) (is_equippable : Bool) (is_dominated : Bool) (hp_restore : Int) (equipped : Bool) :
    Int :=
  let base := (useful_quantity_cap_excl_equipped_pure item_code recipe_max batch_buffer safety_floor task_type task_code task_total task_progress recipes action_cap is_equippable is_dominated hp_restore)
  (if equipped
   then
    (max 1 base)
   else
    base)

end Extracted.InventoryCaps
