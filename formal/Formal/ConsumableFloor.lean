-- @concept: consumables, fleet, supply @property: safety, dominance, totality
/-
The fleet's consumable floor (Phase 5-2c-iii-c-2 #5, `docs/PLAN_task_value.md`
§10, `src/artifactsmmo_cli/ai/consumable_floor_core.py`).

USER 2026-10-07: "Fishing feeds Cooking, Cooking feeds HP recovery or provides
stat bonuses. Both cases require pre-emptive crafting of an available supply.
The fleet can collectively maintain a minimum supply in the bank." Rulings:
the floor is fleet size × the per-character target; it is for the
TIER-APPROPRIATE consumable (the best usable at the character's level, even if
a skill cannot make it yet — that skill demand is the seesaw); the shortfall is
filled through the demand board, each character publishing its share.

## The model

* `tierPick`: candidates are `(level, restore)` in catalogue order; the pick is
  the index of an eligible candidate (`level ≤ charLevel`, `restore > 0`)
  maximal in `(restore, level)`, the first such in catalogue order.
* `fleetDeficit target fleet stock = target * fleet - stock` (truncated).
* `publishShare deficit fleet = ⌈deficit / fleet⌉`: every character publishes
  this, and the demand board sums the shares.
-/

namespace Formal.ConsumableFloor

def eligible (charLevel : Nat) (c : Nat × Nat) : Bool :=
  decide (c.1 ≤ charLevel) && decide (0 < c.2)

/-- `a` strictly beats `b` in (restore, level). -/
def better (a b : Nat × Nat) : Bool :=
  decide (b.2 < a.2) || (decide (a.2 = b.2) && decide (b.1 < a.1))

def tierPickAux (charLevel : Nat) : List (Nat × Nat) → Nat → Option (Nat × (Nat × Nat)) →
    Option (Nat × (Nat × Nat))
  | [], _, best => best
  | c :: cs, i, best =>
    let best' :=
      if eligible charLevel c then
        match best with
        | none => some (i, c)
        | some (j, b) => if better c b then some (i, c) else some (j, b)
      else best
    tierPickAux charLevel cs (i + 1) best'

/-- The tier-appropriate consumable's index, or none. -/
def tierPick (charLevel : Nat) (cands : List (Nat × Nat)) : Option Nat :=
  (tierPickAux charLevel cands 0 none).map Prod.fst

def fleetDeficit (target fleet stock : Nat) : Nat := target * fleet - stock

def publishShare (deficit fleet : Nat) : Nat := (deficit + fleet - 1) / fleet

/-! ## Theorems -/

theorem fleetDeficit_zero_iff (target fleet stock : Nat) :
    fleetDeficit target fleet stock = 0 ↔ target * fleet ≤ stock := by
  unfold fleetDeficit; omega

theorem fleetDeficit_antitone (target fleet s s' : Nat) (h : s ≤ s') :
    fleetDeficit target fleet s' ≤ fleetDeficit target fleet s := by
  unfold fleetDeficit; omega

/-- The shares the fleet publishes cover the deficit. -/
theorem publishShare_covers (deficit fleet : Nat) (hf : 0 < fleet) :
    deficit ≤ publishShare deficit fleet * fleet := by
  unfold publishShare
  have := Nat.div_add_mod (deficit + fleet - 1) fleet
  have hm := Nat.mod_lt (deficit + fleet - 1) hf
  have : (deficit + fleet - 1) / fleet * fleet = fleet * ((deficit + fleet - 1) / fleet) :=
    Nat.mul_comm _ _
  omega

/-- No character publishes more than the whole deficit. -/
theorem publishShare_le (deficit fleet : Nat) (hf : 0 < fleet) :
    publishShare deficit fleet ≤ deficit := by
  unfold publishShare
  rcases Nat.eq_zero_or_pos deficit with h | h
  · subst h
    rw [Nat.div_eq_of_lt (by omega)]; exact Nat.le_refl 0
  · obtain ⟨f, rfl⟩ : ∃ f, fleet = f + 1 := ⟨fleet - 1, by omega⟩
    obtain ⟨d, rfl⟩ : ∃ d, deficit = d + 1 := ⟨deficit - 1, by omega⟩
    apply Nat.div_le_of_le_mul
    simp only [Nat.add_mul, Nat.mul_add, Nat.mul_one, Nat.one_mul]
    omega

/-- A lone character publishes its whole deficit. -/
theorem publishShare_one (deficit : Nat) : publishShare deficit 1 = deficit := by
  simp [publishShare]

theorem tierPickAux_some_eligible (charLevel : Nat) :
    ∀ (cs : List (Nat × Nat)) (i : Nat) (best : Option (Nat × (Nat × Nat))),
      (∀ j b, best = some (j, b) → eligible charLevel b = true) →
      ∀ j b, tierPickAux charLevel cs i best = some (j, b) → eligible charLevel b = true := by
  intro cs
  induction cs with
  | nil => intro i best hb j b h; exact hb j b h
  | cons c cs ih =>
    intro i best hb j b h
    simp only [tierPickAux] at h
    refine ih (i + 1) _ ?_ j b h
    intro j' b' hj
    by_cases he : eligible charLevel c = true
    · simp only [he, if_true] at hj
      cases best with
      | none => simp at hj; obtain ⟨-, rfl⟩ := hj; exact he
      | some p =>
        obtain ⟨k, d⟩ := p
        by_cases hbt : better c d = true
        · simp [hbt] at hj; obtain ⟨-, rfl⟩ := hj; exact he
        · simp [hbt] at hj; obtain ⟨rfl, rfl⟩ := hj; exact hb k d rfl
    · simp only [Bool.not_eq_true] at he; simp only [he] at hj
      exact hb j' b' (by simpa using hj)

/-- The pick is always an eligible candidate: usable at the character's level
and restoring something. -/
theorem tierPick_eligible (charLevel : Nat) (cands : List (Nat × Nat)) (j : Nat)
    (h : tierPick charLevel cands = some j) :
    ∃ b, tierPickAux charLevel cands 0 none = some (j, b) ∧ eligible charLevel b = true := by
  unfold tierPick at h
  cases hx : tierPickAux charLevel cands 0 none with
  | none => simp [hx] at h
  | some p =>
    obtain ⟨k, b⟩ := p
    simp [hx] at h; subst h
    exact ⟨b, rfl, tierPickAux_some_eligible charLevel cands 0 none (by simp) k b hx⟩

theorem better_le_trans (a b c : Nat × Nat) (hab : better a b = false) (hbc : better b c = false) :
    better a c = false := by
  simp only [better, Bool.or_eq_false_iff, Bool.and_eq_false_iff, decide_eq_false_iff_not] at *
  omega

theorem better_lt_le (c d b : Nat × Nat) (hcd : better c d = true) (hcb : better c b = false) :
    better d b = false := by
  simp only [better, Bool.or_eq_false_iff, Bool.and_eq_false_iff, decide_eq_false_iff_not,
    Bool.or_eq_true, Bool.and_eq_true, decide_eq_true_eq] at *
  omega

theorem tierPickAux_optimal (charLevel : Nat) :
    ∀ (cs : List (Nat × Nat)) (i : Nat) (best : Option (Nat × (Nat × Nat))) (j : Nat) (b : Nat × Nat),
      tierPickAux charLevel cs i best = some (j, b) →
      (∀ c ∈ cs, eligible charLevel c = true → better c b = false) ∧
      (∀ k d, best = some (k, d) → better d b = false) := by
  intro cs
  induction cs with
  | nil =>
    intro i best j b h
    refine ⟨by simp, ?_⟩
    intro k d hb; subst hb; simp [tierPickAux] at h; obtain ⟨-, rfl⟩ := h
    simp [better]
  | cons c cs ih =>
    intro i best j b h
    simp only [tierPickAux] at h
    obtain ⟨hcs, hbest'⟩ := ih (i + 1) _ j b h
    by_cases he : eligible charLevel c = true
    · simp only [he, if_true] at hbest'
      cases best with
      | none =>
        refine ⟨?_, by simp⟩
        intro x hx hex
        rcases List.mem_cons.mp hx with rfl | hx
        · exact hbest' i x rfl
        · exact hcs x hx hex
      | some p =>
        obtain ⟨k0, d0⟩ := p
        by_cases hbt : better c d0 = true
        · simp only [hbt, if_true] at hbest'
          have hcb := hbest' i c rfl
          refine ⟨?_, ?_⟩
          · intro x hx hex
            rcases List.mem_cons.mp hx with rfl | hx
            · exact hcb
            · exact hcs x hx hex
          · intro k d hkd; simp at hkd; obtain ⟨rfl, rfl⟩ := hkd
            exact better_lt_le c d0 b hbt hcb
        · simp only [Bool.not_eq_true] at hbt; simp only [hbt] at hbest'
          have hdb := hbest' k0 d0 (by simp)
          refine ⟨?_, ?_⟩
          · intro x hx hex
            rcases List.mem_cons.mp hx with rfl | hx
            · exact better_le_trans x d0 b hbt hdb
            · exact hcs x hx hex
          · intro k d hkd; simp at hkd; obtain ⟨rfl, rfl⟩ := hkd; exact hdb
    · simp only [Bool.not_eq_true] at he; simp only [he] at hbest'
      refine ⟨?_, fun k d hkd => hbest' k d (by simpa using hkd)⟩
      intro x hx hex
      rcases List.mem_cons.mp hx with rfl | hx
      · simp [he] at hex
      · exact hcs x hx hex

/-- OPTIMALITY: no eligible candidate strictly beats the pick in (restore,
level). -/
theorem tierPick_optimal (charLevel : Nat) (cands : List (Nat × Nat)) (j : Nat) (b : Nat × Nat)
    (h : tierPickAux charLevel cands 0 none = some (j, b)) :
    ∀ c ∈ cands, eligible charLevel c = true → better c b = false :=
  (tierPickAux_optimal charLevel cands 0 none j b h).1

/-! ## Witnesses -/

example : tierPick 30 [(20, 150), (30, 300), (40, 500), (25, 300)] = some 1 := by decide
example : tierPick 10 [(20, 150), (30, 300)] = none := by decide
example : publishShare 25 5 = 5 := by decide
example : publishShare 23 5 = 5 := by decide
example : fleetDeficit 5 5 30 = 0 := by decide

end Formal.ConsumableFloor
