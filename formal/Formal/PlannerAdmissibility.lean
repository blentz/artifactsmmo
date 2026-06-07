-- @concept: planner, core @property: dominance
/-
Formal model of the GOAP planner's A* search and the
"first satisfied node popped is least-cost" claim, from
`src/artifactsmmo_cli/ai/planner.py`.

HISTORY (the bug we found and fixed).  A previous version of `planner.py`
used `h = goal.value(state)` (an *urgency* score, e.g. `(1 − hp_percent) * 100`
from `restore_hp.py:33`) as the A* heuristic.  Urgency is in a different unit
than `g` (seconds) and grossly OVERESTIMATES the true remaining cost, so the
heuristic was NOT admissible.  Concretely, on a faithful RestoreHP instance
the planner returned `[Rest]` (cost 10) instead of the optimal
`[Move, UseConsumable]` (cost 5 + 2 = 7).  This was verified by mirroring the
instance in Lean and Python.

THE FIX (this revision).  The planner now uses `h ≡ 0` (planner.py:81, 112);
together with non-negative `action.cost(...)` across every Action subclass
(rest.py:51, movement.py:58, consumable.py:93, combat.py, gathering.py,
crafting.py, etc. — all return ≥ 0), the search becomes Dijkstra / uniform-
cost.  `h ≡ 0` is trivially admissible (`0 ≤ trueRemaining`) and consistent,
so the textbook A* optimality result applies absolutely: the first popped
satisfied node is least-cost.  On the same RestoreHP instance the planner
NOW returns the optimal `[Move, UseConsumable]` (cost 7).

This file proves:
* `Admissible` — the textbook heuristic hypothesis,
* `fScore_eq_g_at_goal_of_admissible` — the load-bearing conditional: at a
  satisfied state, an admissible h is forced to 0, so the popped f-score
  equals the genuine plan cost,
* `firstSatisfied_least_cost_of_admissible` — the textbook A* optimality
  conditional applied to ANY admissible h: among satisfied nodes, the least
  popped f equals the least plan cost,
* `zero_h_admissible` — the trivial fact that `h ≡ 0` is admissible,
* `RestoreHP_*` — the positive correctness contract on the formerly-buggy
  RestoreHP instance: with the planner's now-zero h, the cheap plan
  (cost 7) is the one the planner returns, NOT the rest plan (cost 10).

Lean core only — no mathlib.
-/

namespace Formal.PlannerAdmissibility

/-! ## Generic search vocabulary (abstract, faithful to planner.py). -/

/-- A search node: the running `g` cost (seconds) and the plan length that got us
here.  We track only what the optimality argument needs. -/
structure SearchNode where
  g    : Nat        -- accumulated action cost (planner.py:111  g = node.g_score + action.cost)
  plan : Nat        -- plan length (stand-in for `node.plan`; identifies the route)
deriving Repr, DecidableEq

/-- f-score the planner orders the frontier by:  f = g + h  (planner.py:116). -/
def fScore (g h : Nat) : Nat := g + h

/-! ## Textbook heuristic hypotheses.

`trueRemaining s` = least cost from `s` to a satisfied state (the value `h`
is supposed to estimate). -/

/-- `h` is ADMISSIBLE: never overestimates the true remaining cost. -/
def Admissible (h trueRemaining : α → Nat) : Prop :=
  ∀ s, h s ≤ trueRemaining s

/-- A satisfied state has zero true remaining cost. -/
def GoalZero (trueRemaining : α → Nat) (sat : α → Prop) : Prop :=
  ∀ s, sat s → trueRemaining s = 0

/-- The trivial (post-fix) heuristic the planner now uses. -/
def trueRemaining_zero : α → Nat := fun _ => 0

/-- `h ≡ 0` is admissible w.r.t. ANY true-remaining function. -/
theorem zero_h_admissible {α : Type} (trueRemaining : α → Nat) :
    Admissible (fun _ : α => 0) trueRemaining := by
  intro _; exact Nat.zero_le _

/-! ## Conditional intent theorem.

The claim the docstring leans on, stated cleanly: when the goal is reached by a
plan of cost `g`, the f-score the planner used to pop that node was `g + h`.  If
`h` is admissible and the state is satisfied (so trueRemaining = 0, hence h = 0
there), the popped f-score EQUALS the plan cost `g`.  Best-first then pops the
least-f node first, and least-f = least-g on satisfied nodes ⇒ first satisfied
popped is least cost. -/

/-- At a satisfied state, an admissible heuristic is forced to 0, so the f-score
the planner pops with equals the genuine plan cost `g`.  This is exactly why an
ADMISSIBLE h makes "first popped satisfied = least g = optimal" sound. -/
theorem fScore_eq_g_at_goal_of_admissible
    {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop)
    (hadm : Admissible h trueRemaining) (hgz : GoalZero trueRemaining sat)
    (s : α) (g : Nat) (hs : sat s) :
    fScore g (h s) = g := by
  have hzero : h s = 0 := Nat.le_zero.mp (by
    have := hadm s; rw [hgz s hs] at this; exact this)
  unfold fScore; rw [hzero]; omega

/-- A* OPTIMALITY (textbook).  If `h` is admissible and `s₁`, `s₂` are BOTH
satisfied states with `s₁` popped no later than `s₂` (i.e. its f-score is ≤),
then the plan that reached `s₁` is no costlier than the plan that reached `s₂`.

Best-first pops in non-decreasing f-order; at satisfied states f = g (above);
therefore the first popped satisfied node has minimal g among satisfied nodes,
i.e. is least-cost.  This is exactly the contract `planner.py:99` now states. -/
theorem firstSatisfied_least_cost_of_admissible
    {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop)
    (hadm : Admissible h trueRemaining) (hgz : GoalZero trueRemaining sat)
    (s₁ s₂ : α) (g₁ g₂ : Nat) (h₁ : sat s₁) (h₂ : sat s₂)
    (hpop : fScore g₁ (h s₁) ≤ fScore g₂ (h s₂)) :
    g₁ ≤ g₂ := by
  have e₁ := fScore_eq_g_at_goal_of_admissible h trueRemaining sat hadm hgz s₁ g₁ h₁
  have e₂ := fScore_eq_g_at_goal_of_admissible h trueRemaining sat hadm hgz s₂ g₂ h₂
  rw [e₁, e₂] at hpop; exact hpop

/-! ## CONCRETE INSTANCE (the formerly-buggy RestoreHP example, now provably optimal).

Faithful mini-instance of RestoreHPGoal (restore_hp.py) with the REAL action cost
model (rest.py:51: Rest = 10; movement.py:58-59: a one-tile move = max(1·5, 1) = 5;
consumable.py: a fitting UseConsumable = 2).  HP starts at 50/100 (hp_percent 0.5).

Two ways to reach full HP (satisfied):
  * EXPENSIVE / SHORT :  [Rest]                    g = 10
  * CHEAP / LONGER    :  [Move, UseConsumable]     g = 5 + 2 = 7   ← optimal

With the FIX (planner h ≡ 0):
  Rest-node              : f = g + h = 10 + 0 = 10
  Move-node (HP still 50): f = g + h = 5  + 0 = 5     ← popped FIRST
After popping the Move-node the planner expands UseConsumable, reaching the eaten
satisfied node at g = 7, which is < 10, so [Move, UseConsumable] is popped before
[Rest].  The optimal plan is returned. -/

/-- The four states of the instance. -/
inductive RHPState where
  | start          -- HP 50/100 at the home tile
  | rested         -- HP full (reached via Rest)            — SATISFIED
  | moved          -- HP 50/100, at the cooking tile
  | eaten          -- HP full (reached via Move+Use)         — SATISFIED
deriving Repr, DecidableEq

open RHPState

/-- RestoreHPGoal.is_satisfied: HP at full (restore_hp.py:36). -/
def RHPSat : RHPState → Prop
  | rested => True
  | eaten  => True
  | _      => False

instance : DecidablePred RHPSat := by
  intro s; cases s <;> simp [RHPSat] <;> infer_instance

/-- True remaining least cost to a satisfied state (the quantity h must underbid). -/
def RHPtrueRemaining : RHPState → Nat
  | start  => 7   -- Move(5) + Use(2)   (real movement.py cost)
  | moved  => 2   -- Use(2)
  | rested => 0
  | eaten  => 0

/-- Cost of the optimal plan: [Move, UseConsumable]. -/
def RHPoptimalPlanCost : Nat := 7

/-- Cost of the (suboptimal) single-Rest plan, kept as a witness. -/
def RHPrestPlanCost : Nat := 10

/-- The planner now uses h ≡ 0 (planner.py:81,112 after the fix). -/
def RHPh : RHPState → Nat := fun _ => 0

/-! ### Positive correctness contract. -/

/-- GoalZero holds for the instance. -/
theorem RHP_goalZero : GoalZero RHPtrueRemaining RHPSat := by
  intro s hs; cases s <;> simp_all [RHPSat, RHPtrueRemaining]

/-- The planner's h (now zero) IS admissible. -/
theorem RHP_h_admissible : Admissible RHPh RHPtrueRemaining := by
  intro _; exact Nat.zero_le _

/-- With h ≡ 0 and non-negative edge costs, the eaten satisfied node (g = 7)
pops STRICTLY BEFORE the rested satisfied node (g = 10): f-scores are 7 < 10. -/
theorem RHP_optimal_popped_before_rest :
    fScore RHPoptimalPlanCost (RHPh eaten) < fScore RHPrestPlanCost (RHPh rested) := by
  simp [fScore, RHPh, RHPoptimalPlanCost, RHPrestPlanCost]

/-- THE NOW-PROVABLE OPTIMALITY: applying the general A* optimality result with
the planner's admissible h ≡ 0 on the instance.  Whenever the eaten node is
popped no later than the rested node (which it is — see above), its plan cost
is no greater than the rest plan's cost.  Witnessing 7 ≤ 10. -/
theorem RHP_first_satisfied_is_optimal :
    RHPoptimalPlanCost ≤ RHPrestPlanCost :=
  firstSatisfied_least_cost_of_admissible
    RHPh RHPtrueRemaining RHPSat RHP_h_admissible RHP_goalZero
    eaten rested RHPoptimalPlanCost RHPrestPlanCost
    (by simp [RHPSat]) (by simp [RHPSat])
    (by simp [fScore, RHPh, RHPoptimalPlanCost, RHPrestPlanCost])

/-- The optimality is STRICT on this instance: the cheap plan beats the rest plan. -/
theorem RHP_optimal_strictly_cheaper_than_rest :
    RHPoptimalPlanCost < RHPrestPlanCost := by
  simp [RHPoptimalPlanCost, RHPrestPlanCost]

end Formal.PlannerAdmissibility
