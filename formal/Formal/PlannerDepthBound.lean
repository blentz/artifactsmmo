-- @concept: planner, core @property: safety, reachability
/-
Formal model of the GOAP planner's DEPTH BOUND and the reachability
consequence that justifies a sound pre-plan skip, from
`src/artifactsmmo_cli/ai/planner.py`.

THE CODE FACTS this mirrors (planner.py):
  * L118  `if node.depth >= max_depth: continue`
          — a node at depth ≥ max_depth is NOT expanded (produces no children).
  * L131-139 each expansion pushes a child with
          `depth = node.depth + 1` and `plan = [*node.plan, action]`
          — depth and plan length advance in lockstep, so for every node
          `len(plan) == depth`.
  * L108-116 a satisfied node is RETURNED as `node.plan`.

CONSEQUENCE (load-bearing): the planner can never return a plan longer than
`max_depth`. Hence if EVERY satisfying plan for a goal is longer than that
goal's `max_depth`, the planner provably returns `[]` — and running the full
90s A* search is pure waste.

THE BUG this exposes. `UpgradeEquipmentGoal` inherits base `max_depth = 15`
(goals/base.py:48) but a from-scratch craftable target needs far more steps:
copper_boots = 8·copper_bar, copper_bar = 10·copper_ore ⇒ ≥ 80 GatherActions,
because a gather mints exactly +1 (gather_apply_core.gather_apply_pure). 80 ≫ 15
⇒ provably unreachable ⇒ guaranteed no_plan every cycle.

This module proves:
  * `reachable_planLen_eq_depth`   — the lockstep invariant `planLen = depth`,
  * `reachable_depth_le_maxDepth`  — every reachable node has `depth ≤ maxDepth`,
  * `plan_length_le_max_depth`     — SAFETY INVARIANT: any plan the search can
                                     return has length ≤ maxDepth,
  * `reachable_not_satisfying_when_lb_exceeds_depth` — GATE SOUNDNESS: when a
    sound lower bound on every satisfying plan's length exceeds maxDepth, no
    reachable node is satisfying, so skipping the search loses nothing attainable.

Lean core only — no mathlib.
-/

namespace Formal.PlannerDepthBound

/-- A search node, mirroring planner.py `_Node`: the `depth` and the length of
the `plan` that reached it. We track only what the depth bound needs. -/
structure Node where
  depth   : Nat
  planLen : Nat
deriving Repr, DecidableEq

/-- Nodes the search can actually reach, mirroring the planner loop precisely:

* `root` — the start node `_Node(depth=0, plan=[])` (planner.py:92).
* `step` — expanding a reachable node `n` produces a child ONLY when
  `n.depth < maxDepth` (the `if node.depth >= max_depth: continue` guard,
  planner.py:118), and the child has `depth = n.depth + 1`,
  `planLen = n.planLen + 1` (planner.py:131-139). Branching WIDTH is irrelevant
  to the depth bound — any number of children all share this depth/planLen shape,
  so one representative successor faithfully captures the reachable-node shape. -/
inductive Reachable (maxDepth : Nat) : Node → Prop where
  | root : Reachable maxDepth ⟨0, 0⟩
  | step : ∀ n, Reachable maxDepth n → n.depth < maxDepth →
      Reachable maxDepth ⟨n.depth + 1, n.planLen + 1⟩

/-- **Lockstep invariant.** Every reachable node has `planLen = depth`: each
expansion appends exactly one action while incrementing depth by one. -/
theorem reachable_planLen_eq_depth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.planLen = n.depth := by
  induction h with
  | root => rfl
  | step n _ _ ih => simp [ih]

/-- Every reachable node has `depth ≤ maxDepth`: the root is at depth 0, and a
child is created only from a parent strictly below `maxDepth`, so its depth
(parent + 1) is at most `maxDepth`. -/
theorem reachable_depth_le_maxDepth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.depth ≤ maxDepth := by
  induction h with
  | root => exact Nat.zero_le _
  | step n _ hlt _ => exact hlt

/-- **SAFETY INVARIANT.** Any plan the planner can return has length ≤
`max_depth`. (A returned plan is the `planLen` of some reachable, satisfied
node; combine the two invariants above.) -/
theorem plan_length_le_max_depth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.planLen ≤ maxDepth := by
  rw [reachable_planLen_eq_depth maxDepth n h]
  exact reachable_depth_le_maxDepth maxDepth n h

/-- **GATE SOUNDNESS.** Let `satisfyingLen n` mean "n is a satisfied node" and
suppose every satisfied node needs a plan of length ≥ `lb` (a SOUND lower bound,
e.g. the transitive raw-material gather count `minGathers`). If `lb` exceeds
`maxDepth`, then NO reachable node is satisfied — the planner provably returns no
plan, so skipping the search before running it loses nothing attainable. This is
exactly the justification for `is_plannable` returning False when
`minGathers(target) > goal.max_depth`. -/
theorem reachable_not_satisfying_when_lb_exceeds_depth
    (maxDepth lb : Nat) (satisfyingLen : Node → Prop)
    (hsat_lb : ∀ n, satisfyingLen n → n.planLen ≥ lb)
    (hexceed : maxDepth < lb)
    (n : Node) (hreach : Reachable maxDepth n) :
    ¬ satisfyingLen n := by
  intro hs
  have h1 : n.planLen ≤ maxDepth := plan_length_le_max_depth maxDepth n hreach
  have h2 : n.planLen ≥ lb := hsat_lb n hs
  omega

/-! ## Concrete instance: the copper_boots bug.

A faithful arithmetic witness that the bug is real and non-vacuous: with
`maxDepth = 15` (UpgradeEquipmentGoal's inherited bound) and `lb = 80` (the
≥80 copper_ore gathers a from-scratch copper_boots needs), the hypothesis
`maxDepth < lb` holds, so any reachable node is provably non-satisfying. -/

/-- The bug arithmetic is satisfiable: 15 < 80. -/
theorem copper_boots_exceeds_upgrade_max_depth : (15 : Nat) < 80 := by decide

/-- Instantiated soundness: under UpgradeEquipment's depth bound (15) a
copper_boots search (≥80 gathers) can reach no satisfying node — the planner
will return no_plan, so the gate is right to skip it. -/
theorem copper_boots_unreachable_under_upgrade_depth
    (satisfyingLen : Node → Prop)
    (hsat_lb : ∀ n, satisfyingLen n → n.planLen ≥ 80)
    (n : Node) (hreach : Reachable 15 n) :
    ¬ satisfyingLen n :=
  reachable_not_satisfying_when_lb_exceeds_depth 15 80 satisfyingLen hsat_lb
    copper_boots_exceeds_upgrade_max_depth n hreach

end Formal.PlannerDepthBound
