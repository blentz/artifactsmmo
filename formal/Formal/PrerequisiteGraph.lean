-- @concept: crafting, items @property: safety, totality
/-
Formal model of the data-derived EDGE STRUCTURE of `prerequisites` and the
`combat_capable` aggregation from
`src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`.

## `prerequisites(node, state, game_data)` — the `ObtainItem code` branch

After the `is_satisfied` short-circuit (which we treat as already false — we
model the DATA-DERIVED edges of an unsatisfied node), the direct prerequisites
of `ObtainItem code` are:

* if `code` is RECOVERABLE (`recoverable.get(code, 0) > 0` — recycling licensed
  surplus can supply it, per `ai/recoverable_materials`): NO prerequisites (a
  LEAF). It is directly actionable, so the descent must NOT fall into its
  recipe and re-derive from raw resources what the bag already holds in crafted
  form;
* else if `code` HAS a recipe (`crafting_recipe(code) is not None`): ONE
  `ObtainItem(mat, qty)` edge per `(mat, qty)` ingredient, in recipe
  (insertion) order — and NOTHING else. The crafting-skill gate is NO LONGER
  emitted as a prerequisite node: under-skill gear is grinded planner-natively
  by UpgradeEquipmentGoal via the LevelSkill action (epic P3), not by a
  tree-level skill root;
* else (buyable / monster-drop / gatherable / unknown): NO prerequisites (a
  leaf). The old "resource-drop → ReachSkillLevel" branch is GONE.

We model item/material codes as `Nat`. A prerequisite edge is only ever an item
requirement `ObtainItem code qty` (the sole `MetaGoal` constructor the ObtainItem
branch now emits — no `ReachSkillLevel`, and `ReachCharLevel` is never produced
by the ObtainItem branch).

The recipe is `recipe : Option (List (Nat × Nat))` (the `crafting_recipe(code)`
lookup: `none` = not craftable, `some ingredients` = `(mat, qty)` list).

## `combat_capable(state, game_data)`

`return any(predict_win(state, game_data, code) for code in _monster_level)`.
We abstract the per-monster `predict_win` verdict as an input boolean (the real
`predict_win` is proven in `PredictWin.lean`). `combatCapable beatable` is the
`List.any` over the monster list; we prove it equals `∃ m, beatable m` via De
Morgan (an INDEPENDENT existential formulation, not the function reapplied).

Lean core only — no mathlib.
-/

namespace Formal.PrerequisiteGraph

/-! ### MetaGoal edges. -/

/-- A prerequisite edge — the sole `MetaGoal` constructor the `ObtainItem`
branch of `prerequisites` can emit (an `ObtainItem(code, qty)` material). -/
inductive Edge where
  | item (code qty : Nat)
deriving DecidableEq, Repr

/-! ### The edge list of the `ObtainItem code` branch. -/

/-- `prereqEdges recoverable recipe`: the direct prerequisite edges of an
UNSATISFIED `ObtainItem code`, exactly mirroring the Python branch.

`recoverable` is `recoverable.get(code, 0) > 0` — the code has RECYCLABLE
licensed surplus (`ai/recoverable_materials`), so it is DIRECTLY ACTIONABLE and
the descent must NOT fall into its recipe: a leaf. Otherwise one `Edge.item` per
recipe ingredient when craftable, else a leaf. No skill edge; no resource
branch. -/
def prereqEdges (recoverable : Bool) (recipe : Option (List (Nat × Nat))) : List Edge :=
  if recoverable then [] else
    match recipe with
    | some ingredients => ingredients.map (fun p => Edge.item p.1 p.2)
    | none => []

/-! ### The recoverable YIELD (`ai/recoverable_materials`).

`actions/factory` emits quantity=1 `RecycleAction`s, so GOAP recovers from `n`
licensed copies by applying a UNIT recycle `n` times, each returning
`max(1, (qty * 1) // 2)` per `RecycleAction.apply`. The total is the UNIT form
`n * max(1, qty / 2)` — NOT the BATCH form `max(1, (qty * n) / 2)`. If this term
drifts from `RecycleAction.apply`, the tier descent promises materials the
executor cannot deliver and the bot stalls at a leaf with no plan. -/

/-- `recoverableYield copies qty`: units of an ingredient recovered by applying
`copies` UNIT recycles, each returning `max 1 (qty / 2)`. Mirrors
`copies * max(1, mat_qty // 2)` in `recoverable_materials`. -/
def recoverableYield (copies qty : Nat) : Nat :=
  copies * max 1 (qty / 2)

/-- `recoverableBatchYield copies qty`: the BATCH expression the executor does
NOT perform — modelled ONLY so the unit-vs-batch divergence below is stated
against something independent, never used by `prereqEdges`. -/
def recoverableBatchYield (copies qty : Nat) : Nat :=
  max 1 (qty * copies / 2)

/-! ### combat_capable aggregation. -/

/-- `combatCapable beatable monsters`: `any(predict_win(m) for m in monsters)`,
where `beatable m` abstracts the proven `predict_win` verdict for monster `m`. -/
def combatCapable (beatable : Nat → Bool) (monsters : List Nat) : Bool :=
  monsters.any beatable

/-! ### THEOREMS for `prerequisites` (the ObtainItem edge structure).

The three original theorems are RESTATED under `recoverable = false` — the
non-recoverable branch is behaviour-preserving, byte-for-byte the pre-epic
descent. -/

/-- `prereqs_recipe`: a craftable, NON-recoverable item produces EXACTLY one item
edge per ingredient, in recipe order, and NO skill edge — pinned against the
independently-built expected list. -/
theorem prereqs_recipe (ingredients : List (Nat × Nat)) :
    prereqEdges false (some ingredients)
      = ingredients.map (fun p => Edge.item p.1 p.2) := by
  rfl

/-- `prereqs_leaf`: a NON-craftable item is a LEAF — NO prerequisites. The old
resource-drop → skill branch is retired, so `none` is always empty. -/
theorem prereqs_leaf : prereqEdges false none = ([] : List Edge) := by
  rfl

/-- `prereqs_membership`: full characterization of edge membership for a
craftable, NON-recoverable item. An edge is in the prereq set IFF it is an
`Edge.item mat qty` for some ingredient `(mat, qty)` in the recipe. This pins the
EXACT edge set (no extra, none missing, NO skill edge) against an independent
existential. -/
theorem prereqs_membership (ingredients : List (Nat × Nat)) (e : Edge) :
    e ∈ prereqEdges false (some ingredients)
      ↔ ∃ mat qty, (mat, qty) ∈ ingredients ∧ e = Edge.item mat qty := by
  unfold prereqEdges
  simp only [Bool.false_eq_true, if_false, List.mem_map]
  constructor
  · rintro ⟨p, hp, he⟩
    exact ⟨p.1, p.2, by simpa using hp, he.symm⟩
  · rintro ⟨mat, qty, hmem, he⟩
    exact ⟨(mat, qty), hmem, he.symm⟩

/-! ### THEOREMS for the RECOVERABLE leaf rule (this epic's core claim). -/

/-- `prereqs_recoverable_leaf`: a RECOVERABLE material has NO prerequisites,
whatever its recipe. Recycling licensed surplus supplies it directly, so the
descent must not re-derive it from raw resources (live 2026-07-13: the descent
chopped 50 ash_wood while 7 fishing_net — 6 ash_plank each — sat in the bag). -/
theorem prereqs_recoverable_leaf (r : Option (List (Nat × Nat))) :
    prereqEdges true r = ([] : List Edge) := by
  rfl

/-- `recoverable_flag_is_load_bearing`: the flag is not ignored — on the SAME
craftable recipe the two branches genuinely differ. Refutes any "recoverable is
inert" reading and is the anti-gaming witness for a dropped leaf branch. -/
theorem recoverable_flag_is_load_bearing :
    prereqEdges true (some [(1, 2)]) ≠ prereqEdges false (some [(1, 2)]) := by
  decide

/-! ### THEOREMS for `recoverableYield` (the term that must not drift). -/

/-- `recoverableYield_pos`: ANY licensed copy recovers at least one unit of every
ingredient (the `max 1` floor). This is what makes the Python gate `> 0` a
faithful "is this material actually obtainable by recycling" test. -/
theorem recoverableYield_pos (copies qty : Nat) (h : 0 < copies) :
    0 < recoverableYield copies qty := by
  have h1 : 0 < max 1 (qty / 2) := by omega
  exact Nat.mul_pos h h1

/-- `recoverableYield_zero_iff`: nothing is recoverable EXACTLY when no licensed
copy exists. The leaf rule therefore fires on copies, never on an empty map. -/
theorem recoverableYield_zero_iff (copies qty : Nat) :
    recoverableYield copies qty = 0 ↔ copies = 0 := by
  constructor
  · intro h
    cases copies with
    | zero => rfl
    | succ n => exact absurd h (Nat.ne_of_gt (recoverableYield_pos (n + 1) qty (Nat.succ_pos n)))
  · intro h
    subst h
    simp [recoverableYield]

/-- `recoverableYield_qty_one`: a 1-quantity ingredient still yields ONE unit per
unit recycle — the `max 1` floor, which is precisely where the unit and batch
forms part company. -/
theorem recoverableYield_qty_one (copies : Nat) :
    recoverableYield copies 1 = copies := by
  simp [recoverableYield]

/-- `yield_unit_exceeds_batch_at_qty_one`: 4 unit recycles of a 1-qty ingredient
recover 4 — the batch expression predicts 2 and would UNDER-promise. -/
theorem yield_unit_exceeds_batch_at_qty_one :
    recoverableYield 4 1 = 4 ∧ recoverableBatchYield 4 1 = 2 := by
  decide

/-- `yield_batch_exceeds_unit_at_qty_three`: 2 unit recycles of a 3-qty ingredient
recover 2 — the batch expression predicts 3 and would OVER-promise (the executor
cannot deliver it, which is the leaf-with-no-plan stall). -/
theorem yield_batch_exceeds_unit_at_qty_three :
    recoverableYield 2 3 = 2 ∧ recoverableBatchYield 2 3 = 3 := by
  decide

/-- `yield_unit_and_batch_are_incomparable`: NEITHER form dominates the other, so
"take the bigger one" is not a sound repair and no inequality between them is
provable. Only the UNIT form mirrors `RecycleAction.apply` under the quantity=1
actions `actions/factory` emits — fidelity, not optimism, is the requirement.

(Honest note: the naive `batch ≤ unit` conjecture is FALSE — the second witness
refutes it. This incomparability statement is the strongest true replacement.) -/
theorem yield_unit_and_batch_are_incomparable :
    (∃ c q, recoverableBatchYield c q < recoverableYield c q) ∧
    (∃ c q, recoverableYield c q < recoverableBatchYield c q) :=
  ⟨⟨4, 1, by decide⟩, ⟨2, 3, by decide⟩⟩

/-! ### The `> 0` gate, composed: yield ⇒ leaf.

These two pin the EXACT boundary the Python gate `recoverable.get(code, 0) > 0`
draws, against the two mutations that attack it (`> 0 → >= 0`, and dropping the
branch entirely). -/

/-- `no_licensed_copy_still_descends`: with ZERO licensed copies the yield is 0,
the gate is false, and the recipe descent happens in full. Kills `> 0 → >= 0`. -/
theorem no_licensed_copy_still_descends (qty : Nat) (ingredients : List (Nat × Nat)) :
    prereqEdges (decide (0 < recoverableYield 0 qty)) (some ingredients)
      = ingredients.map (fun p => Edge.item p.1 p.2) := by
  simp [recoverableYield, prereqEdges]

/-- `one_licensed_copy_is_a_leaf`: ONE licensed copy is enough — the descent
stops. The rule is `> 0`, not "fully covers the need": GOAP mixes recycle with
gather/craft to make up any shortfall rather than facing an all-or-nothing
cliff. Kills a dropped leaf branch. -/
theorem one_licensed_copy_is_a_leaf (qty : Nat) (ingredients : List (Nat × Nat)) :
    prereqEdges (decide (0 < recoverableYield 1 qty)) (some ingredients)
      = ([] : List Edge) := by
  have h : 0 < recoverableYield 1 qty := recoverableYield_pos 1 qty (by decide)
  simp [h, prereqEdges]

/-! ### THEOREMS for `combat_capable` (the `any` aggregation, via De Morgan).

`combat_capable_iff` is NOT `X ↔ X`: the LHS is the operational `List.any` fold;
the RHS is an INDEPENDENT existential over the monster list. We prove the
equivalence and the De Morgan dual (`¬ combatCapable ↔ ∀ m, ¬ beatable m`). -/

/-- `combat_capable_iff`: `combat_capable` is true IFF SOME monster is beatable.
The RHS `∃ m ∈ monsters, beatable m = true` is an independent existential, not
the `any` function reapplied. -/
theorem combat_capable_iff (beatable : Nat → Bool) (monsters : List Nat) :
    combatCapable beatable monsters = true ↔ ∃ m ∈ monsters, beatable m = true := by
  unfold combatCapable
  rw [List.any_eq_true]

/-- `combat_capable_demorgan`: NOT combat-capable IFF EVERY monster is unbeatable
(`∀ m, ¬ beatable m`) — the De Morgan dual, the independent formulation the spec
asks for (catches an `any → all` mutation). -/
theorem combat_capable_demorgan (beatable : Nat → Bool) (monsters : List Nat) :
    combatCapable beatable monsters = false ↔ ∀ m ∈ monsters, beatable m = false := by
  rw [← Bool.not_eq_true, combat_capable_iff]
  constructor
  · intro h m hm
    cases hb : beatable m with
    | false => rfl
    | true => exact absurd ⟨m, hm, hb⟩ h
  · intro h hex
    obtain ⟨m, hm, hb⟩ := hex
    rw [h m hm] at hb
    exact Bool.noConfusion hb

/-- `combat_capable_empty`: no monsters ⇒ never combat-capable (the `any` of an
empty list). A boundary anchor distinguishing `any` (false) from `all` (true). -/
theorem combat_capable_empty (beatable : Nat → Bool) :
    combatCapable beatable [] = false := by
  rfl

/-- `combat_capable_witness`: a single beatable monster in the list is enough —
the existential witness direction, the operational "found a target" content. -/
theorem combat_capable_witness (beatable : Nat → Bool) (monsters : List Nat)
    {m : Nat} (hm : m ∈ monsters) (hb : beatable m = true) :
    combatCapable beatable monsters = true := by
  rw [combat_capable_iff]
  exact ⟨m, hm, hb⟩

/-! ### ANTI-GAMING: `any` is genuinely NOT `all`.

A concrete monster list where exactly one of two monsters is beatable: `any`
(combat-capable) is TRUE, but the `all` aggregation would be FALSE. This is the
gate that an `any → all` mutation must trip. -/
example :
    let beatable : Nat → Bool := fun m => decide (m = 0)
    combatCapable beatable [0, 1] = true ∧ ([0, 1].all beatable = false) := by
  decide

end Formal.PrerequisiteGraph
