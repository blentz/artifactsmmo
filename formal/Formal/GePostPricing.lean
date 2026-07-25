-- @concept: grandexchange, undercut @property: fail-closed, dominance, boundedness
/-
Formal model of the pure POSTED-order price-setting extracted from
`src/artifactsmmo_cli/ai/ge_post_pricing.py` (`sell_post_price`, `buy_post_price`).

This is the speculative half deliberately left OUT of `liquidation_venue` /
`buy_source_venue`, made safe by two guards proved below:

  (1) FAIL CLOSED — with no live anchor (best standing order is `none`) the price is
      `none`, so an empty book never yields a speculative post
      (`sell_none_of_no_anchor`, `buy_none_of_no_anchor`, both `rfl`).

  (2) FLOOR / CEILING BOUND — a posted SELL price is never below the NPC sell-back
      plus margin (`sell_price_ge_floor`); a posted BUY price is never above the
      realizable alternative cost minus margin (`buy_price_le_ceiling`). So a post
      can never be strictly worse than dumping to / buying from the alternative, i.e.
      posting weakly dominates the fallback.

We also pin the undercut/overbid-by-one-tick shape: a SELL post never exceeds one
tick below the best sell (or it is exactly the floor) — `sell_price_le_best_minus_one`;
a BUY post is at least one tick above the best buy (or it is exactly the cap) —
`buy_price_ge_best_plus_one`.

The Python core mirrors this exactly:
  `None if best_sell is None else max(best_sell - 1, npc_sellback + margin)`
  `None if best_buy  is None else min(best_buy  + 1, alt_cost   - margin)`
We model it over `Int` with `Option Int`, matching `LiquidationVenue.lean`.
-/

namespace Formal.GePostPricing

/-- Post price for a SELL order: one tick below the best standing sell, floored at
the NPC sell-back plus margin. `none` (no anchor) -> `none`. Mirrors Python. -/
def sellPostPrice (bestSell : Option Int) (npcSellback margin : Int) : Option Int :=
  match bestSell with
  | some b => some (max (b - 1) (npcSellback + margin))
  | none => none

/-- Post price for a BUY order: one tick above the best standing buy, capped at the
alternative cost minus margin. `none` (no anchor) -> `none`. Mirrors Python. -/
def buyPostPrice (bestBuy : Option Int) (altCost margin : Int) : Option Int :=
  match bestBuy with
  | some b => some (min (b + 1) (altCost - margin))
  | none => none

/-! ### FAIL CLOSED. -/

/-- FAIL CLOSED: no standing sell order -> no posted price. -/
theorem sell_none_of_no_anchor (npcSellback margin : Int) :
    sellPostPrice none npcSellback margin = none := rfl

/-- FAIL CLOSED: no standing buy order -> no posted price. -/
theorem buy_none_of_no_anchor (altCost margin : Int) :
    buyPostPrice none altCost margin = none := rfl

/-! ### DOMINANCE (floor / ceiling bound against the realizable alternative). -/

/-- DOMINANCE (sell): a posted sell price is never below the NPC floor+margin, so
posting weakly dominates dumping to the NPC. -/
theorem sell_price_ge_floor (b npcSellback margin : Int) :
    ∀ p, sellPostPrice (some b) npcSellback margin = some p → npcSellback + margin ≤ p := by
  intro p h
  simp only [sellPostPrice, Option.some.injEq] at h
  subst h
  omega

/-- DOMINANCE (buy): a posted buy price is never above the alt-cost minus margin, so
posting weakly dominates buying from the alternative. -/
theorem buy_price_le_ceiling (b altCost margin : Int) :
    ∀ p, buyPostPrice (some b) altCost margin = some p → p ≤ altCost - margin := by
  intro p h
  simp only [buyPostPrice, Option.some.injEq] at h
  subst h
  omega

/-! ### UNDERCUT / OVERBID (one-tick queue placement, or exactly the bound). -/

/-- UNDERCUT (sell): the posted price never exceeds one tick below the best sell. -/
theorem sell_price_le_best_minus_one (b npcSellback margin : Int) :
    ∀ p, sellPostPrice (some b) npcSellback margin = some p →
      p ≤ b - 1 ∨ p = npcSellback + margin := by
  intro p h
  simp only [sellPostPrice, Option.some.injEq] at h
  subst h
  omega

/-- OVERBID (buy): the posted price is at least one tick above the best buy (or the cap). -/
theorem buy_price_ge_best_plus_one (b altCost margin : Int) :
    ∀ p, buyPostPrice (some b) altCost margin = some p →
      b + 1 ≤ p ∨ p = altCost - margin := by
  intro p h
  simp only [buyPostPrice, Option.some.injEq] at h
  subst h
  omega

/-! ### Concrete witnesses (non-vacuity of both branches of the bound). -/

example : sellPostPrice (some 20) 5 1 = some 19 := by decide
example : sellPostPrice (some 6) 5 1 = some 6 := by decide
example : sellPostPrice none 5 1 = none := by decide
example : buyPostPrice (some 8) 15 1 = some 9 := by decide
example : buyPostPrice (some 14) 15 1 = some 14 := by decide
example : buyPostPrice none 15 1 = none := by decide

end Formal.GePostPricing
