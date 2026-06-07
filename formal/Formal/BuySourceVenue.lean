-- @concept: grandexchange @property: dominance, totality, safety, monotonicity
/-
Formal model of the pure immediate-fill BUY source venue decision extracted from
`src/artifactsmmo_cli/ai/buy_source_venue.py` (`BuyVenue`, `choose_buy_venue`,
`realized_cost`). This is the DUAL of `Formal/LiquidationVenue.lean`.

To buy ONE needed unit the bot picks the venue with strictly LOWER REALIZABLE cost:
NPC buy (always realizable) vs filling an EXISTING Grand Exchange SELL order
(realizable ONLY if such an order stands):

    GE  iff  (∃ g, gePrice = some g  ∧  g < npcPrice)
    NPC otherwise

Liquidating SELLS and maximizes proceeds (fills a standing BUY order); sourcing BUYS
and minimizes cost (fills a standing SELL order). The `gePrice : Option Int` is the
ANTI-SURROGATE guard: `none` encodes "no fillable standing sell order", so GE is
chosen ONLY when a real order exists AND is strictly cheaper. Posting a NEW order is
deliberately out of scope (an unposted order may never fill — a posted-price proof
would be a surrogate sham). The Python core mirrors this exactly:
`BuyVenue.GE if (ge_price is not None and ge_price < npc_price) else BuyVenue.NPC`;
we model it over `Int` with `Option Int`.

`realizedCost` couples the choice to actual gold — the order price when GE is chosen
and an order exists, else the NPC price — so the decision cannot "win" on a phantom
price.

Lean core only — no mathlib. The decidable `<`/`Option` matching plus
`simp only [...]` / `split` / `omega` close every goal; the same core-only
convention as `Formal/LiquidationVenue.lean`.

NON-VACUITY: all three branches are reachable and exhibited below
(`choose_branch_ge` : g < npcPrice → GE ; `choose_branch_npc_high` : g ≥ npcPrice → NPC ;
`choose_branch_none` : none → NPC), the dominance ↔ has a true-branch witness, and
`realizedCost` is coupled to the same gold the choice is about.
-/

namespace Formal.BuySourceVenue

/-- Buy source venue for one needed unit. Mirrors the Python `BuyVenue` enum. -/
inductive BuyVenue where | npc | ge deriving Repr, DecidableEq

/-- GE iff a fillable standing sell order exists AND costs strictly less than the NPC
buy price; otherwise NPC. Mirrors the Python `choose_buy_venue`. -/
def chooseBuyVenue (npcPrice : Int) (gePrice : Option Int) : BuyVenue :=
  match gePrice with
  | some g => if g < npcPrice then BuyVenue.ge else BuyVenue.npc
  | none => BuyVenue.npc

/-- Gold actually spent at `venue`: the standing order price when GE is chosen
(and an order exists), else the NPC buy price. Mirrors `realized_cost`. -/
def realizedCost (npcPrice : Int) (gePrice : Option Int) (venue : BuyVenue) : Int :=
  match venue, gePrice with
  | BuyVenue.ge, some g => g
  | _, _ => npcPrice

/-! ### TOTALITY. -/

/-- TOTALITY: the decision is always either NPC or GE (no third outcome, no stuck
state) — for ANY `npcPrice` and ANY (present-or-absent) order. -/
theorem venue_total (npcPrice : Int) (gePrice : Option Int) :
    chooseBuyVenue npcPrice gePrice = BuyVenue.npc ∨ chooseBuyVenue npcPrice gePrice = BuyVenue.ge := by
  unfold chooseBuyVenue
  cases gePrice with
  | none => exact Or.inl rfl
  | some g =>
    by_cases h : g < npcPrice
    · exact Or.inr (by simp [h])
    · exact Or.inl (by simp [h])

/-! ### DOMINANCE. -/

/-- DOMINANCE: GE fires EXACTLY when a fillable order exists and is strictly cheaper
than the NPC buy price — the precise firing condition, no over- or under-firing. The
existential right-hand side is the satisfiable-but-nontrivial hypothesis. -/
theorem ge_iff_fillable_and_cheaper (npcPrice : Int) (gePrice : Option Int) :
    chooseBuyVenue npcPrice gePrice = BuyVenue.ge ↔ ∃ g, gePrice = some g ∧ g < npcPrice := by
  unfold chooseBuyVenue
  cases gePrice with
  | none =>
    simp only
    constructor
    · intro h; exact absurd h (by simp)
    · rintro ⟨g, hg, _⟩; exact absurd hg (by simp)
  | some g =>
    simp only
    by_cases h : g < npcPrice
    · simp only [h, if_true]
      exact ⟨fun _ => ⟨g, rfl, h⟩, fun _ => trivial⟩
    · simp only [h, if_false]
      constructor
      · intro hge; exact absurd hge (by simp)
      · rintro ⟨g', hg', hlt⟩
        rw [Option.some.injEq] at hg'
        subst hg'; exact absurd hlt h

/-! ### SAFETY (anti-surrogate + no value loss). -/

/-- SAFETY (anti-surrogate): GE is NEVER chosen without a real standing sell order.
`chooseBuyVenue = ge → gePrice.isSome`. This is the guard that blocks a surrogate
"buy from a phantom order" decision. -/
theorem ge_requires_fillable_order (npcPrice : Int) (gePrice : Option Int)
    (h : chooseBuyVenue npcPrice gePrice = BuyVenue.ge) : gePrice.isSome := by
  rw [ge_iff_fillable_and_cheaper] at h
  obtain ⟨g, hg, _⟩ := h
  rw [hg]; simp

/-- SAFETY / no-value-loss: the gold spent at the CHOSEN venue is `≤` the NPC buy
price AND `≤` any fillable order's price. The choice never pays more than a
realizable alternative; `realizedCost` is coupled to the same `npcPrice`/order the
decision ranges over (anti-decoupling). This is the DUAL of `chosen_venue_maximizes`. -/
theorem chosen_minimizes_cost (npcPrice : Int) (gePrice : Option Int) :
    realizedCost npcPrice gePrice (chooseBuyVenue npcPrice gePrice) ≤ npcPrice
    ∧ ∀ g, gePrice = some g →
        realizedCost npcPrice gePrice (chooseBuyVenue npcPrice gePrice) ≤ g := by
  unfold chooseBuyVenue realizedCost
  cases gePrice with
  | none =>
    refine ⟨Int.le_refl _, ?_⟩
    intro g hg; exact absurd hg (by simp)
  | some g =>
    by_cases h : g < npcPrice
    · simp only [h, if_true]
      refine ⟨Int.le_of_lt h, ?_⟩
      intro g' hg'; rw [Option.some.injEq] at hg'; subst hg'; exact Int.le_refl _
    · simp only [h, if_false]
      refine ⟨Int.le_refl _, ?_⟩
      intro g' hg'; rw [Option.some.injEq] at hg'; subst hg'
      exact Int.not_lt.mp h

/-! ### MONOTONICITY. -/

/-- MONOTONICITY (lower the order): if GE is chosen, lowering the standing order's
price keeps the decision GE (a strictly-cheaper order stays strictly cheaper). -/
theorem ge_stable_under_lower_ge (npcPrice g g' : Int)
    (hge : chooseBuyVenue npcPrice (some g) = BuyVenue.ge) (hle : g' ≤ g) :
    chooseBuyVenue npcPrice (some g') = BuyVenue.ge := by
  rw [ge_iff_fillable_and_cheaper] at hge ⊢
  obtain ⟨g0, hg0, hlt⟩ := hge
  rw [Option.some.injEq] at hg0; subst hg0
  exact ⟨g', rfl, by omega⟩

/-- MONOTONICITY (raise the NPC ceiling): if GE is chosen, raising the NPC buy price
keeps the decision GE (the order still strictly undercuts the now-higher ceiling). -/
theorem ge_stable_under_higher_npc (npcPrice npcPrice' : Int) (gePrice : Option Int)
    (hge : chooseBuyVenue npcPrice gePrice = BuyVenue.ge) (hle : npcPrice ≤ npcPrice') :
    chooseBuyVenue npcPrice' gePrice = BuyVenue.ge := by
  rw [ge_iff_fillable_and_cheaper] at hge ⊢
  obtain ⟨g, hg, hlt⟩ := hge
  exact ⟨g, hg, by omega⟩

/-! ### NON-VACUITY witnesses (all three branches reachable). -/

/-- Reachable branch 1: a fillable order strictly cheaper ⇒ GE. -/
theorem choose_branch_ge (npcPrice g : Int) (h : g < npcPrice) :
    chooseBuyVenue npcPrice (some g) = BuyVenue.ge := by
  unfold chooseBuyVenue; simp [h]

/-- Reachable branch 2: a fillable order priced `≥` the NPC ceiling ⇒ NPC. -/
theorem choose_branch_npc_high (npcPrice g : Int) (h : npcPrice ≤ g) :
    chooseBuyVenue npcPrice (some g) = BuyVenue.npc := by
  unfold chooseBuyVenue; simp [Int.not_lt.mpr h]

/-- Reachable branch 3: no fillable order ⇒ NPC (the anti-surrogate default). -/
theorem choose_branch_none (npcPrice : Int) :
    chooseBuyVenue npcPrice none = BuyVenue.npc := rfl

/-- Concrete non-vacuity witness: the GE branch is inhabited (8 < 15 ⇒ GE), so the
dominance ↔ is not vacuously false on its true side. -/
example : chooseBuyVenue 15 (some 8) = BuyVenue.ge := by decide

/-- Concrete witness: the order-ties branch lands on NPC (no strict saving). -/
example : chooseBuyVenue 10 (some 10) = BuyVenue.npc := by decide

/-- Concrete witness: the no-order branch lands on NPC. -/
example : chooseBuyVenue 10 none = BuyVenue.npc := by decide

end Formal.BuySourceVenue
