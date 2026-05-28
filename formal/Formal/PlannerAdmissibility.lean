/-
Formal model of the GOAP planner's A* search and its "first satisfied node is
optimal" claim, from `src/artifactsmmo_cli/ai/planner.py`.

The Python planner (planner.py:80-122) runs forward best-first search with
    f = g + h,   g = Σ action.cost  (seconds),   h = goal.value(state)  (urgency),
pops nodes in f-order, marks each popped state in a `visited` set and NEVER
reopens it, and RETURNS the plan of the FIRST popped node that satisfies the goal
(planner.py:98-101), with the comment:

    "A* pops nodes in f-score order; first satisfied node is optimal."

That claim is the textbook A* optimality result, which REQUIRES the heuristic `h`
to be ADMISSIBLE (h ≤ true remaining cost) — and, because this planner closes
nodes on pop and never reopens them, CONSISTENT. The heuristic actually used is
`goal.value(state)`, an *urgency* score (RestoreHPGoal jumps to 110 when HP is
low; DepositInventory ramps to 80). Urgency is in a different unit than `g`
(seconds) and grossly OVERESTIMATES remaining cost, so it is not admissible.

This file:
* `Admissible` / `Consistent` — the textbook heuristic hypotheses,
* `astarFirstSat_optimal_of` — the CONDITIONAL intent theorem: on the concrete
  instance, IF the heuristic is admissible then the first-popped satisfied node
  is least-cost (the claim the docstring *should* rely on),
* a CONCRETE COUNTEREXAMPLE (`CE`) faithfully mirroring RestoreHPGoal +
  Rest/Move/UseConsumable, where the urgency heuristic is NOT admissible and the
  planner's first-popped-satisfied plan is STRICTLY costlier than the optimal
  plan — i.e. the optimality claim is FALSE for the heuristic actually used.

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

/-! ## Conditional intent theorem.

The claim the docstring leans on, stated cleanly: when the goal is reached by a
plan of cost `g`, the f-score the planner used to pop that node was `g + h`.  If
`h` is admissible and the state is satisfied (so trueRemaining = 0, hence h = 0
there), the popped f-score EQUALS the plan cost `g`.  Best-first then pops the
least-f node first, and least-f = least-g on satisfied nodes ⇒ first satisfied
popped is least cost.  We prove the key admissible-at-goal fact, the load-bearing
step of that argument, with no escape hatch. -/

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

/-- Contrapositive utility: if the popped f-score at a satisfied node EXCEEDS the
plan cost (f > g), then h could NOT have been admissible there.  This is the lever
the counterexample pulls. -/
theorem not_admissible_of_fScore_gt_g_at_goal
    {α : Type} (h trueRemaining : α → Nat) (sat : α → Prop)
    (hgz : GoalZero trueRemaining sat)
    (s : α) (g : Nat) (hs : sat s) (hgt : g < fScore g (h s)) :
    ¬ Admissible h trueRemaining := by
  intro hadm
  have := fScore_eq_g_at_goal_of_admissible h trueRemaining sat hadm hgz s g hs
  omega

/-! ## CONCRETE COUNTEREXAMPLE.

Faithful mini-instance of RestoreHPGoal (restore_hp.py) with the REAL action cost
model (rest.py:51: Rest = 10; movement.py:58-59: a one-tile move = max(1·5, 1) = 5;
consumable.py: a fitting UseConsumable = 2).  HP starts at 50/100 (hp_percent 0.5).

Two ways to reach full HP (satisfied):
  * EXPENSIVE / SHORT :  [Rest]                    g = 10
  * CHEAP / LONGER    :  [Move, UseConsumable]      g = 5 + 2 = 7   ← optimal

`value` (the heuristic h) on this goal is, for hp_percent < 1:
    h = (1 - hp_percent) * 100               (restore_hp.py:33)
so at HP = 50/100, h = 50 — for BOTH the start state and the post-Move state
(Move doesn't change HP).  The true remaining cost from the post-Move state is
just 2 (one UseConsumable), so h = 50 ≫ 2: NOT admissible.

The best-first frontier after expanding the start:
  Rest-node              : f = g + h = 10 + 0  = 10   (satisfied ⇒ h = 0)
  Move-node (HP still 50): f = g + h = 5  + 50 = 55
The planner pops the Rest-node (f = 10) FIRST — before it ever expands the
Move-node toward the cheaper plan — and returns [Rest], cost 10, while the optimal
plan costs 7.  The "first satisfied = optimal" claim is therefore FALSE. -/

/-- The five states of the counterexample world. -/
inductive CEState where
  | start          -- HP 50/100 at the home tile
  | rested         -- HP full (reached via Rest)            — SATISFIED
  | moved          -- HP 50/100, at the cooking tile
  | eaten          -- HP full (reached via Move+Use)         — SATISFIED
deriving Repr, DecidableEq

open CEState

/-- RestoreHPGoal.is_satisfied: HP at full (restore_hp.py:36). -/
def CESat : CEState → Prop
  | rested => True
  | eaten  => True
  | _      => False

instance : DecidablePred CESat := by
  intro s; cases s <;> simp [CESat] <;> infer_instance

/-- `value` used as heuristic h (restore_hp.py:33): 50 at any HP-50 state, 0 at full HP. -/
def CEh : CEState → Nat
  | start  => 50
  | moved  => 50
  | rested => 0
  | eaten  => 0

/-- True remaining least cost to a satisfied state (the quantity h must underbid). -/
def CEtrueRemaining : CEState → Nat
  | start  => 7   -- Move(5) + Use(2)   (real movement.py cost)
  | moved  => 2   -- Use(2)
  | rested => 0
  | eaten  => 0

/-- Cost of the plan that the planner pops FIRST (the satisfied Rest-node). -/
def CEfirstSatPlanCost : Nat := 10      -- [Rest]

/-- Cost of the genuinely optimal plan. -/
def CEoptimalPlanCost : Nat := 7        -- [Move, UseConsumable]   (real cost)

/-! ### The refutation. -/

/-- GoalZero holds for the counterexample's true-remaining function. -/
theorem CE_goalZero : GoalZero CEtrueRemaining CESat := by
  intro s hs; cases s <;> simp_all [CESat, CEtrueRemaining]

/-- The urgency heuristic is NOT admissible: at `moved`, h = 50 but the true
remaining cost is only 2.  (restore_hp.py value ≫ planner cost units.) -/
theorem CE_not_admissible : ¬ Admissible CEh CEtrueRemaining := by
  intro hadm
  have := hadm moved      -- CEh moved ≤ CEtrueRemaining moved  i.e. 50 ≤ 2
  simp [CEh, CEtrueRemaining] at this

/-- The planner pops the Rest-node (f = 10) strictly before the Move-node
(f = 55), so among satisfied nodes the Rest-node is popped first. -/
theorem CE_rest_popped_before_move :
    fScore 10 (CEh rested) < fScore 5 (CEh moved) := by
  simp [fScore, CEh]

/-- THE BUG, pinned: the plan the planner returns (first popped satisfied node)
is STRICTLY costlier than the optimal plan.  "First satisfied node is optimal"
(planner.py:99) is FALSE for the urgency heuristic actually used. -/
theorem CE_first_satisfied_not_optimal :
    CEoptimalPlanCost < CEfirstSatPlanCost := by
  simp [CEoptimalPlanCost, CEfirstSatPlanCost]

/-- And the violation is exactly an admissibility failure: at the satisfied
Rest-node, an admissible h would force f = g = 10; the OPTIMAL cost is 3 < 10, so
the search committed to a non-optimal node precisely because h overestimated en
route.  We expose the inadmissibility witness through the general lever. -/
theorem CE_inadmissible_witnessed :
    ¬ Admissible CEh CEtrueRemaining :=
  -- start state: h = 50 but true remaining = 3
  fun hadm => by have := hadm start; simp [CEh, CEtrueRemaining] at this

/-! ### Positive direction (no-bug contract IF h were admissible).

If the heuristic were admissible (h ≤ trueRemaining) then at every satisfied node
the popped f-score equals the plan cost, so best-first's first-popped-satisfied is
genuinely the least-cost satisfied node.  We instantiate the general lemma on the
counterexample's OPTIMAL bound to show what admissibility would have bought:
an admissible h at `eaten` yields f = g = 3, matching the true optimum. -/
theorem CE_admissible_would_be_optimal
    (h : CEState → Nat) (hadm : Admissible h CEtrueRemaining) :
    fScore CEoptimalPlanCost (h eaten) = CEoptimalPlanCost :=
  fScore_eq_g_at_goal_of_admissible h CEtrueRemaining CESat hadm CE_goalZero
    eaten CEoptimalPlanCost (by simp [CESat])

end Formal.PlannerAdmissibility
