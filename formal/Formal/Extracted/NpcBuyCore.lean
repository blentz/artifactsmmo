-- GENERATED from src/artifactsmmo_cli/ai/actions/npc_buy_core.py (sha256: 66a3650e55cc6f930907b8ea6ff61501cea933300a135da4a6bf81e3635af4bb) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.NpcBuyCore

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

/-- Extracted from `npc_buy_is_applicable_pure` (line 31). -/
def npc_buy_is_applicable_pure (inv_used : Int) (inv_max : Int) (quantity : Int) (gold : Int) (price : Int) :
    Bool :=
  let free := (inv_max - inv_used)
  (if (decide (free < quantity))
   then
    false
   else
    (!(decide (gold < (price * quantity)))))

/-- Extracted from `npc_buy_apply_pure` (line 50). -/
def npc_buy_apply_pure (inventory : List (String × Int)) (item_code : String) (quantity : Int) :
    List (String × Int) :=
  let new_inventory := inventory
  let new_inventory := (_dictSet new_inventory item_code ((_dictGetD new_inventory item_code 0) + quantity))
  new_inventory

end Extracted.NpcBuyCore
