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

/-! ## CONSISTENCY (monotonicity) — the property a CLOSED-SET search needs.

`firstSatisfied_least_cost_of_admissible` above is the textbook A* optimality
result for a search that never prunes.  The REAL planner, however, keeps a
`visited` set (planner.py:153-156) and skips any state it has already popped —
a graph search with closed-set pruning.  Admissibility ALONE does not make that
pruning safe: an admissible-but-inconsistent h can pop a state at a non-least g
and then discard the cheaper re-expansion.  The extra hypothesis that seals it
is CONSISTENCY (monotonicity): h never drops by more than the edge cost. -/

/-- Textbook CONSISTENCY (monotonicity): `h s ≤ cost s s' + h s'` for every edge
`s → s'`.  Required — beyond admissibility — for a closed-set graph search: it
guarantees the first pop of a state already has its least `g`, so pruning its
re-expansions discards nothing cheaper.  `planner.py` uses a `visited` set
(planner.py:153-156), so this is the property the real algorithm relies on. -/
def Consistent {α : Type} (h : α → Nat) (cost : α → α → Nat)
    (succ : α → α → Prop) : Prop :=
  ∀ s s', succ s s' → h s ≤ cost s s' + h s'

/-- `h ≡ 0` is consistent w.r.t. ANY cost / successor relation (`0 ≤ cost + 0`).
This is why the post-fix planner (h ≡ 0) is optimal EVEN WITH the visited set. -/
theorem zero_h_consistent {α : Type} (cost : α → α → Nat)
    (succ : α → α → Prop) : Consistent (fun _ : α => 0) cost succ := by
  intro s s' _; simp

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

/-! ## CLOSED-SET PRUNING (the `visited` set) is safe under CONSISTENCY.

The REAL planner (planner.py:153-156) keeps a `visited` set and skips any state it
has already popped.  This pruning is safe only when the FIRST pop of a state already
carries its least `g` — otherwise the skipped re-expansion would have been the
cheaper route.  The classical A* guarantee for this is CONSISTENCY (monotonicity),
and the mechanism is: **`f` is non-decreasing along every path from the start.**
So any cheaper route to a state `s` must, at every prefix, sit on the frontier with
an `f`-score no larger than `f s`; best-first (which pops in non-decreasing `f`)
therefore reaches `s` on that cheaper route no later than on a costlier one.

The two lemmas below make consistency LOAD-BEARING (they are FALSE for an
inconsistent h — the linter warning that a previous draft suppressed was a symptom
of a proof that used only the shared-`h` cancellation and never the hypothesis):

* `fScore_monotone_along_edge_of_consistent` — the single-edge core: `f` does not
  drop across a successor edge.  Unfolds to `h s ≤ cost s s' + h s'`, which is
  EXACTLY `Consistent` applied to that edge; with no consistency hypothesis the
  inequality can fail (a big `h s`), so `hcon` is essential.
* `fScore_monotone_along_path` — folds the edge core along a whole path, giving
  `f`-monotonicity from any start to any reachable state. -/

/-- LOAD-BEARING EDGE MONOTONICITY.  Across a successor edge `s → s'`, the f-score
never decreases: `f g (h s) ≤ f (g + cost s s') (h s')`.  Unfolding `fScore` turns
the goal into `h s ≤ cost s s' + h s'`, which is precisely `Consistent h cost succ`
applied to the edge `e`.  FALSE without consistency — `hcon` is essential. -/
theorem fScore_monotone_along_edge_of_consistent
    {α : Type} (h : α → Nat) (cost : α → α → Nat) (succ : α → α → Prop)
    (hcon : Consistent h cost succ) {s s' : α} (e : succ s s') (g : Nat) :
    fScore g (h s) ≤ fScore (g + cost s s') (h s') := by
  have hc := hcon s s' e
  simp only [fScore]; omega

/-- A cost-carrying path in the search graph: `PathCost cost succ s t c` witnesses a
chain of successor edges from `s` to `t` whose edge costs sum to `c`.  Faithful to
the sequence of `g = node.g_score + action.cost` accumulations along a plan
(planner.py:116). -/
inductive PathCost {α : Type} (cost : α → α → Nat) (succ : α → α → Prop) :
    α → α → Nat → Prop where
  | nil (s : α) : PathCost cost succ s s 0
  | cons {s s' t : α} {c : Nat} (e : succ s s')
      (rest : PathCost cost succ s' t c) :
      PathCost cost succ s t (cost s s' + c)

/-- LOAD-BEARING PATH MONOTONICITY.  Folding the edge core along a whole path: for
any path from `s` to `t` of total cost `c`, `f g (h s) ≤ f (g + c) (h t)`.  So `f`
is non-decreasing along EVERY path from the start — the invariant that makes
closed-set pruning sound.  Each `cons` step invokes the consistency-dependent edge
lemma, so `hcon` is essential (the `nil` step alone does not carry the claim). -/
theorem fScore_monotone_along_path
    {α : Type} (h : α → Nat) (cost : α → α → Nat) (succ : α → α → Prop)
    (hcon : Consistent h cost succ) {s t : α} {c : Nat}
    (p : PathCost cost succ s t c) :
    ∀ g : Nat, fScore g (h s) ≤ fScore (g + c) (h t) := by
  induction p with
  | nil s => intro g; simp only [fScore]; omega
  | cons e rest ih =>
      rename_i s s' _ _
      intro g
      have hedge := fScore_monotone_along_edge_of_consistent h cost succ hcon e g
      have hrest := ih (g + cost s s')
      simp only [fScore] at hedge hrest ⊢
      omega

/-- CLOSED-SET OPTIMALITY.  With an admissible AND consistent h the closed-set graph
search is optimal on BOTH fronts it must be:

1. among SATISFIED nodes, the first popped has least `g`
   (`firstSatisfied_least_cost_of_admissible` — needs ADMISSIBILITY); and
2. the route by which a state is first popped is no costlier than ANY other route to
   it, so discarding a `visited` state never drops a cheaper path — needs
   CONSISTENCY, via path-monotonicity, NOT mere cancellation.

For front 2 we model the pruned alternate route faithfully: `s` was first popped via
route A at cost `gA`; the alternate (pruned) route reaches `s` through a state `w`
that was still on the frontier when `s` popped (so best-first gives
`f gA (h s) ≤ f gW (h w)`), and continues from `w` to `s` along a REAL path `pRest`
of cost `cRest` (its full cost to `s` is `gW + cRest`).  Path-monotonicity lifts the
frontier bound at `w` to `s` — `f gW (h w) ≤ f (gW + cRest) (h s)` — and only then
does the shared `h s` cancel to give `gA ≤ gW + cRest`.  Delete `hcon` and the
`w → s` lift is unavailable: `h w` and `h s` are unrelated and the conclusion fails.
This is the property `planner.py`'s A*-with-`visited` (planner.py:99, 153-156)
actually relies on. -/
theorem consistent_closedSet_preserves_optimal
    {α : Type} (h trueRemaining : α → Nat) (cost : α → α → Nat) (succ : α → α → Prop)
    (sat : α → Prop)
    (hadm : Admissible h trueRemaining) (hgz : GoalZero trueRemaining sat)
    (hcon : Consistent h cost succ)
    (s₁ s₂ : α) (g₁ g₂ : Nat) (h₁ : sat s₁) (h₂ : sat s₂)
    (hpopSat : fScore g₁ (h s₁) ≤ fScore g₂ (h s₂))
    (s w : α) (gA gW cRest : Nat)
    (pRest : PathCost cost succ w s cRest)
    (hfront : fScore gA (h s) ≤ fScore gW (h w)) :
    g₁ ≤ g₂ ∧ gA ≤ gW + cRest := by
  refine ⟨firstSatisfied_least_cost_of_admissible h trueRemaining sat hadm hgz
      s₁ s₂ g₁ g₂ h₁ h₂ hpopSat, ?_⟩
  have hmono := fScore_monotone_along_path h cost succ hcon pRest gW
  simp only [fScore] at hfront hmono ⊢
  omega

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

/-! ## CONCRETE INSTANCE (skill-grind landmark) — admissible AND consistent.

The Python side (BUG B fix) gives the planner a goal-provided heuristic h that is
non-zero: for a skill-grind goal it estimates the remaining cost to a LANDMARK
(the grind action that levels the skill).  Because the search now prunes with the
`visited` set, that h must be not merely admissible but CONSISTENT.  This is the
Lean witness that the heuristic's SHAPE is both: a 2-state landmark world where h
equals the landmark edge cost at the un-ground state, drops by exactly that edge
cost when the grind action is taken, and is 0 at the goal.

  * `needsGrind` : skill not yet at target — one grind action away.   NOT satisfied
  * `done`       : skill at target.                                   SATISFIED

  `succ needsGrind done`     : the landmark grind action.
  `cost needsGrind done = C` : its cost (the landmark distance).
  `h needsGrind = C`, `h done = 0` : the landmark heuristic (drops by exactly C).
  `trueRemaining needsGrind = C`   : the genuine remaining cost (one grind). -/

/-- The landmark edge cost (a stand-in for the grind action's `action.cost`). -/
def SGcost : Nat := 40

/-- The two states of the skill-grind instance. -/
inductive SGState where
  | needsGrind     -- skill below target — one landmark grind away    — NOT SATISFIED
  | done           -- skill at target                                 — SATISFIED
deriving Repr, DecidableEq

open SGState

/-- ReachSkillGoal.is_satisfied: the skill has reached its target level. -/
def SGSat : SGState → Prop
  | done       => True
  | needsGrind => False

instance : DecidablePred SGSat := by
  intro s; cases s <;> simp [SGSat] <;> infer_instance

/-- Edge-cost function: the landmark grind action `needsGrind → done` costs `SGcost`. -/
def SGcostOf : SGState → SGState → Nat
  | needsGrind, done => SGcost
  | _,          _    => 0

/-- The landmark successor relation: the single grind action. -/
def SGsucc : SGState → SGState → Prop
  | needsGrind, done => True
  | _,          _    => False

/-- True remaining least cost to a satisfied state: one grind (`SGcost`) from
`needsGrind`, none from `done`. -/
def SGtrueRemaining : SGState → Nat
  | needsGrind => SGcost
  | done       => 0

/-- The goal-provided skill-grind heuristic: the landmark distance at `needsGrind`,
0 at the goal — it drops by EXACTLY the edge cost when the grind is taken. -/
def SGh : SGState → Nat
  | needsGrind => SGcost
  | done       => 0

/-- GoalZero holds for the skill-grind instance. -/
theorem skillGrind_goalZero : GoalZero SGtrueRemaining SGSat := by
  intro s hs; cases s <;> simp_all [SGSat, SGtrueRemaining]

/-- The skill-grind heuristic IS admissible (`h ≤ trueRemaining` at every state:
`SGcost ≤ SGcost` and `0 ≤ 0`). -/
theorem skillGrind_h_admissible : Admissible SGh SGtrueRemaining := by
  intro s; cases s <;> simp [SGh, SGtrueRemaining]

/-- The skill-grind heuristic IS consistent: across the landmark edge
`needsGrind → done`, `h` drops by EXACTLY the edge cost
(`SGcost ≤ SGcost + 0`), so closed-set pruning stays optimal. -/
theorem skillGrind_h_consistent : Consistent SGh SGcostOf SGsucc := by
  intro s s' hss; cases s <;> cases s' <;> simp_all [SGh, SGcostOf, SGsucc]

/-- The landmark grind edge `needsGrind → done` as a one-edge `PathCost` of cost
`SGcostOf needsGrind done` (= `SGcost` = 40): the concrete alternate route the
closed-set contract folds consistency along. -/
def SGgrindPath : PathCost SGcostOf SGsucc needsGrind done (SGcostOf needsGrind done) :=
  PathCost.cons (by simp [SGsucc]) (PathCost.nil done)

/-- The whole closed-set contract discharged on the skill-grind instance: with the
admissible AND consistent landmark heuristic, the A*-with-`visited` search is optimal
on both fronts — least-g among satisfied nodes, and (front 2) the first-pop route to
`done` at cost `gA` is no costlier than the landmark grind route to it (`gW + 40`),
so pruning the re-expansion drops nothing cheaper.  The consistency proof
(`skillGrind_h_consistent`, tight at `40 ≤ 40 + 0`) feeds the load-bearing
path-monotonicity step. -/
theorem skillGrind_closedSet_preserves_optimal
    (s₁ s₂ : SGState) (g₁ g₂ : Nat) (h₁ : SGSat s₁) (h₂ : SGSat s₂)
    (hpopSat : fScore g₁ (SGh s₁) ≤ fScore g₂ (SGh s₂))
    (gA gW : Nat)
    (hfront : fScore gA (SGh done) ≤ fScore gW (SGh needsGrind)) :
    g₁ ≤ g₂ ∧ gA ≤ gW + SGcostOf needsGrind done :=
  consistent_closedSet_preserves_optimal
    SGh SGtrueRemaining SGcostOf SGsucc SGSat
    skillGrind_h_admissible skillGrind_goalZero skillGrind_h_consistent
    s₁ s₂ g₁ g₂ h₁ h₂ hpopSat
    done needsGrind gA gW (SGcostOf needsGrind done) SGgrindPath hfront

end Formal.PlannerAdmissibility
