-- @concept: core, planner @property: safety, totality
/-
Affordability fast-fail for a currency-buy recipe-closure leaf in
`GatherMaterialsGoal.is_plannable` (src/artifactsmmo_cli/ai/goals/currency_afford_core.py).

A closure leaf (e.g. jasper_crystal) acquired ONLY by NpcBuy for a currency
(tasks_coin) cannot have its owned count raised while UNAFFORDABLE: the buy is
inapplicable (currency_on_hand < price·qty) and GatherMaterials' action set has NO
task-earning action, so the currency cannot rise mid-search. Affordability is
therefore CONSTANT across the plan. Pruning loses no satisfiable plan. (This is
now the ONLY fast-fail arm of `is_plannable`: the former crafting-skill gate was
retired in the LevelSkill epic P2, since the planner can now grind the skill
mid-plan via a `LevelSkill` action — a crafting skill level is NOT constant
across the plan the way a currency balance is.)

Lean core only — no mathlib.
-/

namespace Formal.CurrencyAffordFastFail

/-- A plan step: either the currency buy of the target, or any other action (which
never increases the target's owned count, since the target is buy-acquired). -/
inductive Step where
  | buy
  | other
deriving DecidableEq

/-- `buy` raises owned by one ONLY when affordable (NpcBuy applicable); `other`
never touches the leaf. -/
def applyStep (affordable : Bool) (owned : Nat) : Step → Nat
  | .buy => if affordable then owned + 1 else owned
  | .other => owned

/-- Fold a plan (action sequence) over the owned count. Affordability is fixed for
the whole plan: currency cannot rise mid-search. -/
def runPlan (affordable : Bool) (owned : Nat) : List Step → Nat
  | [] => owned
  | s :: rest => runPlan affordable (applyStep affordable owned s) rest

/-- The fast-fail predicate, mirroring `GatherMaterialsGoal.is_plannable`. -/
def isPlannable (targetInClosure affordable : Bool) (owned needed : Nat) : Bool :=
  !targetInClosure || affordable || decide (needed ≤ owned)

/-! ### Dynamics under unaffordable state. -/

/-- **UNAFFORDABLE-BLOCKS-BUY.** When unaffordable, NO step changes the owned count
(buy is blocked, other never touches the target). -/
theorem applyStep_unaffordable (owned : Nat) (s : Step) :
    applyStep false owned s = owned := by
  cases s <;> simp [applyStep]

/-- **OWNED-INVARIANT.** When unaffordable, the owned count is invariant across
an ENTIRE plan — no action sequence can raise it. -/
theorem runPlan_unaffordable (owned : Nat) (plan : List Step) :
    runPlan false owned plan = owned := by
  induction plan generalizing owned with
  | nil => rfl
  | cons s rest ih => rw [runPlan, applyStep_unaffordable, ih]

/-! ### Headline soundness. -/

/-- **SOUNDNESS.** When the fast-fail fires (`isPlannable = false`), EVERY plan
leaves the owned count below `needed` — so the goal `owned ≥ needed` is
unreachable and pruning it discards no satisfiable plan.

`isPlannable = false` forces: target IS in the closure, UNAFFORDABLE, and
`owned < needed`. Unaffordability means the buy action is never applicable, so
by `runPlan_unaffordable` the final owned equals the initial `owned < needed`. -/
theorem fastfail_sound (targetInClosure affordable : Bool) (owned needed : Nat)
    (h : isPlannable targetInClosure affordable owned needed = false) :
    ∀ plan, runPlan affordable owned plan < needed := by
  simp only [isPlannable, Bool.or_eq_false_iff, Bool.not_eq_false',
    decide_eq_false_iff_not, Nat.not_le] at h
  obtain ⟨⟨_, haff⟩, hown⟩ := h
  intro plan
  rw [haff, runPlan_unaffordable]
  exact hown

/-! ### Non-vacuity / completeness witnesses. -/

-- The fast-fail GENUINELY fires (in closure, unaffordable, owns 0 < 1).
example : isPlannable true false 0 1 = false := by decide

-- Affordable ⇒ plannable (do not prune a buyable goal).
example : isPlannable true true 0 1 = true := by decide

-- Already owns enough ⇒ plannable even when unaffordable.
example : isPlannable true false 1 1 = true := by decide

-- Target NOT in closure ⇒ plannable regardless.
example : isPlannable false false 0 1 = true := by decide

-- Model non-vacuity: with affordable, buying DOES raise the owned count.
example : runPlan true 0 [Step.buy, Step.buy] = 2 := by decide
example : runPlan false 0 [Step.buy, Step.buy] = 0 := by decide

end Formal.CurrencyAffordFastFail
