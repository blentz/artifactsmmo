-- @concept: grandexchange @property: dominance, totality, safety, monotonicity
/-
Formal model of the pure immediate-fill liquidation venue decision extracted from
`src/artifactsmmo_cli/ai/liquidation_venue.py` (`Venue`, `choose_venue`,
`realized_proceeds`).

To sell ONE surplus unit the bot picks the venue with strictly higher REALIZABLE
proceeds: NPC sell-back (always realizable) vs filling an EXISTING Grand Exchange
buy order (realizable ONLY if such an order stands):

    GE  iff  (∃ g, geProceeds = some g  ∧  g > npcPay)
    NPC otherwise

The `geProceeds : Option Int` is the ANTI-SURROGATE guard: `none` encodes
"no fillable standing buy order", so GE is chosen ONLY when a real order exists AND
pays strictly more. Posting a NEW order is deliberately out of scope (an unposted
order may never fill — a posted-price proof would be a surrogate sham). The Python
core mirrors this exactly: `Venue.GE if (ge_proceeds is not None and ge_proceeds >
npc_pay) else Venue.NPC`; we model it over `Int` with `Option Int`.

`realizedProceeds` couples the choice to actual gold — the order price when GE is
chosen and an order exists, else the NPC price — so the decision cannot "win" on a
phantom price.

Lean core only — no mathlib. The decidable `>`/`Option` matching plus
`simp only [...]` / `split` / `omega` close every goal; the same core-only
convention as `Formal/CraftVsBuy.lean`.

NON-VACUITY: all three branches are reachable and exhibited below
(`choose_branch_ge` : g > npcPay → GE ; `choose_branch_npc_low` : g ≤ npcPay → NPC ;
`choose_branch_none` : none → NPC), the dominance ↔ has a true-branch witness, and
`realizedProceeds` is coupled to the same gold the choice is about.
-/

namespace Formal.LiquidationVenue

/-- Liquidation venue for one surplus unit. Mirrors the Python `Venue` enum. -/
inductive Venue where | npc | ge deriving Repr, DecidableEq

/-- GE iff a fillable standing buy order exists AND pays strictly more than the NPC
sell-back; otherwise NPC. Mirrors the Python `choose_venue`. -/
def chooseVenue (npcPay : Int) (geProceeds : Option Int) : Venue :=
  match geProceeds with
  | some g => if g > npcPay then Venue.ge else Venue.npc
  | none => Venue.npc

/-- Gold actually realized at `venue`: the standing order price when GE is chosen
(and an order exists), else the NPC sell-back. Mirrors `realized_proceeds`. -/
def realizedProceeds (npcPay : Int) (geProceeds : Option Int) (venue : Venue) : Int :=
  match venue, geProceeds with
  | Venue.ge, some g => g
  | _, _ => npcPay

/-! ### TOTALITY. -/

/-- TOTALITY: the decision is always either NPC or GE (no third outcome, no stuck
state) — for ANY `npcPay` and ANY (present-or-absent) order. -/
theorem venue_total (npcPay : Int) (geProceeds : Option Int) :
    chooseVenue npcPay geProceeds = Venue.npc ∨ chooseVenue npcPay geProceeds = Venue.ge := by
  unfold chooseVenue
  cases geProceeds with
  | none => exact Or.inl rfl
  | some g =>
    by_cases h : g > npcPay
    · exact Or.inr (by simp [h])
    · exact Or.inl (by simp [h])

/-! ### DOMINANCE. -/

/-- DOMINANCE: GE fires EXACTLY when a fillable order exists and strictly out-pays
the NPC sell-back — the precise firing condition, no over- or under-firing. The
existential right-hand side is the satisfiable-but-nontrivial hypothesis. -/
theorem ge_iff_fillable_and_higher (npcPay : Int) (geProceeds : Option Int) :
    chooseVenue npcPay geProceeds = Venue.ge ↔ ∃ g, geProceeds = some g ∧ g > npcPay := by
  unfold chooseVenue
  cases geProceeds with
  | none =>
    simp only
    constructor
    · intro h; exact absurd h (by simp)
    · rintro ⟨g, hg, _⟩; exact absurd hg (by simp)
  | some g =>
    simp only
    by_cases h : g > npcPay
    · simp only [h, if_true]
      exact ⟨fun _ => ⟨g, rfl, h⟩, fun _ => trivial⟩
    · simp only [h, if_false]
      constructor
      · intro hge; exact absurd hge (by simp)
      · rintro ⟨g', hg', hgt⟩
        rw [Option.some.injEq] at hg'
        subst hg'; exact absurd hgt h

/-! ### SAFETY (anti-surrogate + no value loss). -/

/-- SAFETY (anti-surrogate): GE is NEVER chosen without a real standing buy order.
`chooseVenue = ge → geProceeds.isSome`. This is the guard that blocks a surrogate
"sell into a phantom order" decision. -/
theorem ge_requires_fillable_order (npcPay : Int) (geProceeds : Option Int)
    (h : chooseVenue npcPay geProceeds = Venue.ge) : geProceeds.isSome := by
  rw [ge_iff_fillable_and_higher] at h
  obtain ⟨g, hg, _⟩ := h
  rw [hg]; simp

/-- SAFETY / no-value-loss: the gold realized at the CHOSEN venue is `≥` the NPC
sell-back AND `≥` any fillable order's price. The choice never leaves realizable
gold on the table; `realizedProceeds` is coupled to the same `npcPay`/order the
decision ranges over (anti-decoupling). -/
theorem chosen_venue_maximizes (npcPay : Int) (geProceeds : Option Int) :
    npcPay ≤ realizedProceeds npcPay geProceeds (chooseVenue npcPay geProceeds)
    ∧ ∀ g, geProceeds = some g →
        g ≤ realizedProceeds npcPay geProceeds (chooseVenue npcPay geProceeds) := by
  unfold chooseVenue realizedProceeds
  cases geProceeds with
  | none =>
    refine ⟨Int.le_refl _, ?_⟩
    intro g hg; exact absurd hg (by simp)
  | some g =>
    by_cases h : g > npcPay
    · simp only [h, if_true]
      refine ⟨Int.le_of_lt h, ?_⟩
      intro g' hg'; rw [Option.some.injEq] at hg'; subst hg'; exact Int.le_refl _
    · simp only [h, if_false]
      refine ⟨Int.le_refl _, ?_⟩
      intro g' hg'; rw [Option.some.injEq] at hg'; subst hg'
      exact Int.not_lt.mp h

/-! ### MONOTONICITY. -/

/-- MONOTONICITY (raise the order): if GE is chosen, raising the standing order's
price keeps the decision GE (a strictly-higher-paying order stays strictly higher). -/
theorem ge_stable_under_higher_ge (npcPay g g' : Int)
    (hge : chooseVenue npcPay (some g) = Venue.ge) (hle : g ≤ g') :
    chooseVenue npcPay (some g') = Venue.ge := by
  rw [ge_iff_fillable_and_higher] at hge ⊢
  obtain ⟨g0, hg0, hgt⟩ := hge
  rw [Option.some.injEq] at hg0; subst hg0
  exact ⟨g', rfl, by omega⟩

/-- MONOTONICITY (lower the NPC floor): if GE is chosen, lowering the NPC sell-back
keeps the decision GE (the order still strictly out-pays the now-lower floor). -/
theorem ge_stable_under_lower_npc (npcPay npcPay' : Int) (geProceeds : Option Int)
    (hge : chooseVenue npcPay geProceeds = Venue.ge) (hle : npcPay' ≤ npcPay) :
    chooseVenue npcPay' geProceeds = Venue.ge := by
  rw [ge_iff_fillable_and_higher] at hge ⊢
  obtain ⟨g, hg, hgt⟩ := hge
  exact ⟨g, hg, by omega⟩

/-! ### NON-VACUITY witnesses (all three branches reachable). -/

/-- Reachable branch 1: a fillable order paying strictly more ⇒ GE. -/
theorem choose_branch_ge (npcPay g : Int) (h : g > npcPay) :
    chooseVenue npcPay (some g) = Venue.ge := by
  unfold chooseVenue; simp [h]

/-- Reachable branch 2: a fillable order paying `≤` the NPC floor ⇒ NPC. -/
theorem choose_branch_npc_low (npcPay g : Int) (h : g ≤ npcPay) :
    chooseVenue npcPay (some g) = Venue.npc := by
  unfold chooseVenue; simp [Int.not_lt.mpr h]

/-- Reachable branch 3: no fillable order ⇒ NPC (the anti-surrogate default). -/
theorem choose_branch_none (npcPay : Int) :
    chooseVenue npcPay none = Venue.npc := rfl

/-- Concrete non-vacuity witness: the GE branch is inhabited (10 < 15 ⇒ GE), so the
dominance ↔ is not vacuously false on its true side. -/
example : chooseVenue 10 (some 15) = Venue.ge := by decide

/-- Concrete witness: the order-ties branch lands on NPC (no strict gain). -/
example : chooseVenue 10 (some 10) = Venue.npc := by decide

/-- Concrete witness: the no-order branch lands on NPC. -/
example : chooseVenue 10 none = Venue.npc := by decide

end Formal.LiquidationVenue
