/-
Formal model of `pick_loadout` (per-slot pick) from
`src/artifactsmmo_cli/ai/equipment/scoring.py`.

The Python routine optimizes each equipment slot INDEPENDENTLY. For a slot it:
1. gathers the owned items that FIT the slot and are LEVEL-FEASIBLE
   (`_candidates_for_slot`: `state.level < stats.level` is filtered out, and the
   item's type must map to the slot via `ITEM_TYPE_TO_SLOTS`),
2. takes the argmax-score candidate (`max(candidates, key=score)`), and
3. swaps to it ONLY on a STRICT score improvement over the currently-equipped
   item (`weapon_score(best) > weapon_score(current)` / armor analogue). Ties and
   downgrades keep the current item.

SCORES. The Python scores are floats:
  * weapon: `Σ_elem atk * max(0.0, 1 - res%/100)`
  * armor:  `Σ_elem mon_atk * armor_res% / 100`
`pick_loadout` only ever COMPARES two scores (argmax, and the strict-improvement
test). So we use an ORDER-PRESERVING INTEGER SURROGATE — multiply each float by
100 — which preserves every `<`/`=`/`>` comparison the Python makes:
  * `WScore = Σ_elem atk * max(0, 100 - res)`   (= 100 × weapon_score; the inner
    `max(0, 100-res)` mirrors the float `max(0.0, 1 - res/100)` clamp exactly:
    `100 * max(0, 1 - res/100) = max(0, 100 - res)` for integer `res`)
  * `AScore = Σ_elem mon_atk * armor_res`        (= 100 × armor_score; NO clamp —
    the float armor_score has no `max`, and neither does the surrogate)
Because `100 > 0`, `a < b ↔ 100a < 100b` etc., so the surrogate is order-equivalent
to the float and `pick_loadout`'s behavior over the surrogate is identical to its
behavior over the floats. We model `score` as a single abstract integer function on
items, instantiated to `WScore`/`AScore` at the call site; the pick theorems hold
for ANY integer score, and `weapon_score_nonneg` is the one theorem that EARNS the
weapon clamp (`WScore ≥ 0`; a non-clamped surrogate could go negative when
`res > 100`).

Lean core only — no mathlib. Integer arithmetic via `omega`; argmax via `List.foldr`
and induction.
-/

namespace Formal.EquipmentScoring

/-- A per-element integer stat (attack or resistance), as an association list over
the 4 elements (fire/earth/water/air). Absent element ⇒ 0 (Python `.get(elem, 0)`). -/
abbrev ElemStats := List (Int × Int)

/-- Look up one element's value, defaulting to 0 (Python `dict.get(elem, 0)`). -/
def elemGet (s : ElemStats) (e : Int) : Int :=
  match s.find? (fun kv => kv.1 == e) with
  | some kv => kv.2
  | none => 0

/-- A model item: integer code, level, per-element attack and resistance, and a
`fits` flag that abstracts "this item's type maps to the slot under study"
(Python `slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, [])`). -/
structure Item where
  code : Int
  level : Int
  attack : ElemStats
  resistance : ElemStats
  fits : Bool
deriving Repr, DecidableEq

/-- The 4 game elements as integer keys (fire, earth, water, air). -/
def elements : List Int := [0, 1, 2, 3]

/-- Per-element weapon surrogate term: `atk * max(0, 100 - res)`. The clamp mirrors
the Python float `max(0.0, 1 - res/100)`; here `res` is the MONSTER's resistance. -/
def wTerm (atk monRes : Int) : Int := atk * max 0 (100 - monRes)

/-- `WScore = Σ_elem atk(elem) * max(0, 100 - monsterRes(elem))`
(= 100 × `weapon_score`, the order-preserving integer surrogate). -/
def WScore (item : Item) (monsterRes : ElemStats) : Int :=
  (elements.map (fun e => wTerm (elemGet item.attack e) (elemGet monsterRes e))).sum

/-- Per-element armor surrogate term: `monAtk * armorRes` (NO clamp — the float
`armor_score` has none). -/
def aTerm (monAtk armorRes : Int) : Int := monAtk * armorRes

/-- `AScore = Σ_elem monsterAtk(elem) * armorRes(elem)`
(= 100 × `armor_score`, the order-preserving integer surrogate). -/
def AScore (item : Item) (monsterAtk : ElemStats) : Int :=
  (elements.map (fun e => aTerm (elemGet monsterAtk e) (elemGet item.resistance e))).sum

/-! ### Feasibility and the per-slot pick. -/

/-- A candidate is FEASIBLE for the slot iff it is level-feasible
(`playerLevel ≥ item.level`, i.e. Python NOT `state.level < stats.level`) AND its
type fits the slot. `_candidates_for_slot` returns exactly the feasible items. -/
def feasible (playerLevel : Int) (item : Item) : Bool :=
  decide (item.level ≤ playerLevel) && item.fits

/-- The feasible candidate sublist (`_candidates_for_slot`). -/
def candidates (playerLevel : Int) (items : List Item) : List Item :=
  items.filter (feasible playerLevel)

/-- Argmax of a nonempty list under integer `score`, mirroring Python's
`max(candidates, key=score)` left-fold semantics: scan left→right, keep the
current best unless a strictly-greater score appears (ties keep the EARLIER item,
matching CPython `max`). We fold over the tail starting from the head. -/
def argmaxBy (score : Item → Int) : Item → List Item → Item
  | best, [] => best
  | best, x :: xs =>
      if score x > score best then argmaxBy score x xs else argmaxBy score best xs

/-- The picked item for a slot, OPTION-typed (`none` = leave slot as-is because no
feasible candidate exists, Python `if not candidates: continue`). Otherwise we run
the no-downgrade rule against `current`:
* if `current = none` (empty slot), take the argmax candidate;
* else swap to the argmax ONLY on a STRICT score improvement, keeping `current`
  on ties / downgrades. -/
def pickSlot (score : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item) : Option Item :=
  match candidates playerLevel items with
  | [] => current
  | c :: cs =>
      let best := argmaxBy score c cs
      match current with
      | none => some best
      | some cur => if score best > score cur then some best else some cur

/-- The score of an option, treating `none` as the LOWEST: an empty slot scores
below any real item, so any feasible candidate is a strict improvement (Python:
`current_stats is None ⇒ result[slot] = best.code` unconditionally). We use this
only to STATE no-downgrade uniformly; the pick logic itself handles `none`
specially as above. -/
def optScore (score : Item → Int) : Option Item → Option Int
  | none => none
  | some i => some (score i)

/-! ### Argmax lemmas. -/

/-- The argmax is a member of `best :: xs`. -/
theorem argmaxBy_mem (score : Item → Int) (best : Item) (xs : List Item) :
    argmaxBy score best xs ∈ best :: xs := by
  induction xs generalizing best with
  | nil => simp [argmaxBy]
  | cons x xs ih =>
    unfold argmaxBy
    by_cases h : score x > score best
    · simp only [h, if_true]
      have := ih x
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inl he)))
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))
    · simp only [h, if_false]
      have := ih best
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inl he)
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))

/-- The argmax score is ≥ the score of every element of `best :: xs`. -/
theorem argmaxBy_ge (score : Item → Int) (best : Item) (xs : List Item) :
    ∀ y ∈ best :: xs, score y ≤ score (argmaxBy score best xs) := by
  induction xs generalizing best with
  | nil =>
    intro y hy
    simp only [argmaxBy]
    rcases List.mem_cons.mp hy with he | hm
    · subst he; exact Int.le_refl _
    · exact absurd hm (List.not_mem_nil)
  | cons x xs ih =>
    intro y hy
    unfold argmaxBy
    by_cases h : score x > score best
    · simp only [h, if_true]
      rcases List.mem_cons.mp hy with he | hm
      · subst he
        have hx : score x ≤ score (argmaxBy score x xs) := ih x x (List.mem_cons_self)
        omega
      · exact ih x y hm
    · simp only [h, if_false]
      have h' : score x ≤ score best := Int.not_lt.mp h
      rcases List.mem_cons.mp hy with he | hm
      · subst he; exact ih y y (List.mem_cons_self)
      · rcases List.mem_cons.mp hm with hx | hrest
        · subst hx
          have hb : score best ≤ score (argmaxBy score best xs) := ih best best (List.mem_cons_self)
          omega
        · exact ih best y (List.mem_cons_of_mem _ hrest)

/-- The argmax score is the MAX over `best :: xs`: it is attained by a member and
dominates all members. (Combines `argmaxBy_mem` and `argmaxBy_ge`.) -/
theorem argmaxBy_is_max (score : Item → Int) (best : Item) (xs : List Item) :
    (argmaxBy score best xs ∈ best :: xs) ∧
    (∀ y ∈ best :: xs, score y ≤ score (argmaxBy score best xs)) :=
  ⟨argmaxBy_mem score best xs, argmaxBy_ge score best xs⟩

/-! ### Pick theorems (the strong contracts). -/

/-- `pickslot_feasible`: a non-`none` result is a FEASIBLE candidate (level-feasible
AND its type fits the slot) — UNLESS it is just the retained `current` (which the
caller already had equipped). We state the substantive case: when the result is the
freshly-picked `best` (the argmax of the candidates), it satisfies `feasible`. This
is exactly what `_candidates_for_slot`'s filter guarantees: every element of
`candidates` is feasible, and `best` is one of them. -/
theorem pickslot_best_feasible (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    feasible playerLevel (argmaxBy score c cs) = true := by
  have hmem : argmaxBy score c cs ∈ c :: cs := argmaxBy_mem score c cs
  have : argmaxBy score c cs ∈ candidates playerLevel items := by
    rw [hcand]; exact hmem
  unfold candidates at this
  exact (List.mem_filter.mp this).2

/-- `pickslot_score_optimal`: when there IS a feasible candidate, the freshly-picked
`best` has the MAXIMUM score over all feasible candidates. (Pins the argmax to the
exact optimum the Python `max(candidates, key=score)` computes.) -/
theorem pickslot_score_optimal (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      score y ≤ score (argmaxBy score c cs) := by
  intro y hy
  rw [hcand] at hy
  exact argmaxBy_ge score c cs y hy

/-- `pickslot_no_downgrade`: the result's score is ≥ the current item's score.
Stated over `optScore` with `none` as ⊥: an empty slot is improved by any pick, and
a filled slot is never downgraded (swap only on strict improvement, else keep).
We prove: when `current = some cur`, `score cur ≤ score (resulting item)`. -/
theorem pickslot_no_downgrade (score : Item → Int) (playerLevel : Int)
    (cur : Item) (items : List Item) :
    ∃ r, pickSlot score playerLevel (some cur) items = some r ∧ score cur ≤ score r := by
  unfold pickSlot
  cases hcand : candidates playerLevel items with
  | nil => exact ⟨cur, by simp, Int.le_refl _⟩
  | cons c cs =>
    simp only []
    by_cases h : score (argmaxBy score c cs) > score cur
    · refine ⟨argmaxBy score c cs, by simp [h], ?_⟩
      omega
    · have h' : score (argmaxBy score c cs) ≤ score cur := Int.not_lt.mp h
      exact ⟨cur, by simp [h], Int.le_refl _⟩

/-- `pickslot_ties_keep_current`: when `current = some cur` and `cur`'s score already
equals the max feasible score (so the argmax does NOT strictly beat it), the result
is EXACTLY `cur` — no swap on a tie. -/
theorem pickslot_ties_keep_current (score : Item → Int) (playerLevel : Int)
    (cur : Item) (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs)
    (htie : score (argmaxBy score c cs) = score cur) :
    pickSlot score playerLevel (some cur) items = some cur := by
  unfold pickSlot
  simp only [hcand]
  have : ¬ (score (argmaxBy score c cs) > score cur) := by omega
  simp [this]

/-- `pickslot_empty_fills`: an empty slot (`current = none`) with a feasible
candidate is filled with the argmax best (Python `current_stats is None ⇒
result[slot] = best.code`). -/
theorem pickslot_empty_fills (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    pickSlot score playerLevel none items = some (argmaxBy score c cs) := by
  unfold pickSlot
  simp [hcand]

/-- `pickslot_no_candidates_keeps`: no feasible candidate ⇒ slot is left as-is
(Python `if not candidates: continue`). -/
theorem pickslot_no_candidates_keeps (score : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item)
    (hcand : candidates playerLevel items = []) :
    pickSlot score playerLevel current items = current := by
  unfold pickSlot
  simp [hcand]

/-! ### The weapon clamp theorem (what the `max(0, …)` earns). -/

/-- Each weapon term is nonnegative WHEN the attack is nonnegative: `atk ≥ 0 ⇒
atk * max(0, 100 - res) ≥ 0`. The `max 0` clamp guarantees the second factor is
`≥ 0` for ANY resistance (even `res > 100`); without it the factor `100 - res`
could be negative and flip the sign. -/
theorem wTerm_nonneg (atk monRes : Int) (h : 0 ≤ atk) : 0 ≤ wTerm atk monRes := by
  unfold wTerm
  have h2 : 0 ≤ max 0 (100 - monRes) := Int.le_max_left _ _
  exact Int.mul_nonneg h h2

/-- A list-sum of nonnegative integers is nonnegative. -/
theorem sum_nonneg_of_terms (l : List Int) (h : ∀ x ∈ l, 0 ≤ x) : 0 ≤ l.sum := by
  induction l with
  | nil => simp
  | cons a t ih =>
    simp only [List.sum_cons]
    have ha : 0 ≤ a := h a (List.mem_cons_self)
    have ht : 0 ≤ t.sum := ih (fun x hx => h x (List.mem_cons_of_mem _ hx))
    omega

/-- `weapon_score_nonneg`: `WScore ≥ 0` whenever every per-element attack is
nonnegative (which item attacks always are). This is THE theorem the clamp earns —
a non-clamped surrogate (`Σ atk * (100 - res)`) could go NEGATIVE when a monster's
resistance exceeds 100, which would let `pick_loadout` prefer a strictly worse
weapon. The `max(0, …)` clamp makes the surrogate monotone and nonnegative. -/
theorem weapon_score_nonneg (item : Item) (monsterRes : ElemStats)
    (hatk : ∀ e ∈ elements, 0 ≤ elemGet item.attack e) :
    0 ≤ WScore item monsterRes := by
  unfold WScore
  apply sum_nonneg_of_terms
  intro x hx
  rw [List.mem_map] at hx
  obtain ⟨e, he, hxe⟩ := hx
  rw [← hxe]
  exact wTerm_nonneg _ _ (hatk e he)

end Formal.EquipmentScoring
