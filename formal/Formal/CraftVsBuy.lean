-- @concept: crafting, npcs @property: dominance, monotonicity, totality, safety
/-
Formal model of the pure craft-vs-buy acquisition decision extracted from
`src/artifactsmmo_cli/ai/craft_vs_buy.py` (`Method`, `cheaper_acquisition`).

For a needed item an NPC sells, the bot BUYs instead of CRAFTing only when buying
is STRICTLY fewer cooldowns AND affordable above a gold reserve:

    BUY  iff  (gold - total_price ≥ reserve)  ∧  (buy_cooldowns < craft_cooldowns)
    CRAFT otherwise

Cooldowns is the optimization metric; gold is a HARD constraint (the reserve),
never traded off against cooldowns. The Python core computes
`affordable = gold - total_price >= reserve` and
`Method.BUY if (affordable and buy < craft) else Method.CRAFT`; this mirrors it
exactly over `Int` (the Python `gold - total_price` can go negative, so the model
ranges over all integers; the `if` condition is `Decidable`).

Lean core only — no mathlib. The decidable `≥`/`<` on `Int` and `omega`/`decide`
/`split`/`simp only [cheaperAcquisition]` close every goal; the same core-only
convention as `Formal/GatherSelection.lean`.
-/

namespace Formal.CraftVsBuy

/-- Acquisition method for a needed item. Mirrors the Python `Method` enum. -/
inductive Method where | craft | buy deriving Repr, DecidableEq

/-- BUY iff affordable (gold - price ≥ reserve, over ℤ) AND buy strictly fewer
cooldowns than craft. Mirrors the Python `cheaper_acquisition`. -/
def cheaperAcquisition (craftCd buyCd totalPrice gold reserve : Int) : Method :=
  if (gold - totalPrice ≥ reserve) ∧ (buyCd < craftCd) then Method.buy else Method.craft

/-- TOTALITY: the decision is always either CRAFT or BUY (no third outcome,
no stuck state). -/
theorem acquisition_total (a b p g r : Int) :
    cheaperAcquisition a b p g r = Method.craft ∨ cheaperAcquisition a b p g r = Method.buy := by
  simp only [cheaperAcquisition]
  split
  · exact Or.inr rfl
  · exact Or.inl rfl

/-- DOMINANCE: BUY fires EXACTLY at the affordable-and-strictly-cheaper condition
(the precise firing condition — no over- or under-firing). -/
theorem buy_iff_affordable_and_cheaper (a b p g r : Int) :
    cheaperAcquisition a b p g r = Method.buy ↔ (g - p ≥ r ∧ b < a) := by
  simp only [cheaperAcquisition]
  split
  · rename_i h
    exact ⟨fun _ => h, fun _ => rfl⟩
  · rename_i h
    refine ⟨fun hbuy => absurd hbuy (by simp), fun hcond => absurd hcond h⟩

/-- Dominance corollary: a method that is NOT strictly cheaper is never bought. -/
theorem craft_when_not_cheaper (a b p g r : Int) (h : ¬ (b < a)) :
    cheaperAcquisition a b p g r = Method.craft := by
  simp only [cheaperAcquisition]
  split
  · rename_i hc; exact absurd hc.2 h
  · rfl

/-- Dominance corollary: an unaffordable buy (would drop gold below the reserve)
is never taken. -/
theorem craft_when_unaffordable (a b p g r : Int) (h : ¬ (g - p ≥ r)) :
    cheaperAcquisition a b p g r = Method.craft := by
  simp only [cheaperAcquisition]
  split
  · rename_i hc; exact absurd hc.1 h
  · rfl

/-- MONOTONICITY in gold: if BUY is chosen, raising the available gold keeps the
decision BUY (more gold never flips an affordable buy back to craft). -/
theorem buy_stable_under_more_gold (a b p g g' r : Int)
    (hbuy : cheaperAcquisition a b p g r = Method.buy) (hge : g ≤ g') :
    cheaperAcquisition a b p g' r = Method.buy := by
  rw [buy_iff_affordable_and_cheaper] at hbuy ⊢
  exact ⟨by omega, hbuy.2⟩

/-- MONOTONICITY in buy cost: if BUY is chosen, lowering the buy cooldown count
keeps the decision BUY (a strictly cheaper buy stays strictly cheaper). -/
theorem buy_stable_under_lower_buy (a b b' p g r : Int)
    (hbuy : cheaperAcquisition a b p g r = Method.buy) (hle : b' ≤ b) :
    cheaperAcquisition a b' p g r = Method.buy := by
  rw [buy_iff_affordable_and_cheaper] at hbuy ⊢
  exact ⟨hbuy.1, by omega⟩

/-- SAFETY: whenever BUY is chosen, the post-buy gold stays at or above the
reserve (`gold - price ≥ reserve`) — buying never breaches the gold floor. -/
theorem buy_preserves_reserve (a b p g r : Int)
    (h : cheaperAcquisition a b p g r = Method.buy) : g - p ≥ r := by
  rw [buy_iff_affordable_and_cheaper] at h
  exact h.1

end Formal.CraftVsBuy
